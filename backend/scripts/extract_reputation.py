# -*- coding: utf-8 -*-
# Googleマップ口コミからAIを用いて人気商品を抽出し、DBへ一括書き込みを行うスクリプト。
#
# 実行方法（backend/ ディレクトリで）:
#   .venv/Scripts/python.exe scripts/extract_reputation.py
import json
import re
import sys
from pathlib import Path

# プロジェクトルートをインポートパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal
from app.models.station import Station
from app.services.ai import llm_provider


def clean_json_response(text: str) -> list[str]:
    """LLMの応答からJSON配列部分をパースしてリストで返す。
    ```json ... ``` などのマークダウン装飾がある場合も考慮する。
    """
    text = text.strip()
    # ```json ... ``` または ``` ... ``` を取り除く
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        json_content = match.group(1)
    else:
        json_content = text

    try:
        data = json.loads(json_content)
        if isinstance(data, list):
            return [str(item) for item in data]
    except Exception:
        pass
    return []


def main() -> None:
    raw_reviews_path = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "reviews" / "raw_reviews.json"
    if not raw_reviews_path.exists():
        print(f"エラー: {raw_reviews_path} が見つかりません。")
        sys.exit(1)

    with open(raw_reviews_path, encoding="utf-8") as f:
        reviews_list = json.load(f)

    reviews_data = {r["station_id"]: r["reviews"] for r in reviews_list}

    db = SessionLocal()
    try:
        stations = db.query(Station).all()
        updated_count = 0

        for station in stations:
            reviews = reviews_data.get(station.station_id)
            if not reviews:
                continue

            # クチコミ文をプロンプト用に整形
            reviews_text = "\n".join([f"- {r}" for r in reviews])

            prompt = (
                f"以下の道の駅のGoogleマップ口コミから、特におすすめされている具体的な商品、食べ物、お土産を最大5つ抽出してください。\n"
                f"一般的な形容詞や感想（「美味しい」「おすすめ」など）は含めず、純粋な商品名・料理名・名産品名のみを抽出してください。\n\n"
                f"道の駅名: {station.name}\n"
                f"口コミ:\n{reviews_text}\n\n"
                f"出力は以下のJSON配列フォーマットのみで返してください。マークダウンや説明テキストは含めないでください。\n"
                f'例: ["生しらす丼", "淡路牛バーガー", "玉ねぎスープ"]\n'
            )

            print(f"{station.name} の口コミを解析中...")

            # APIキーが無い場合はルールベース（口コミ文から名詞抽出や静的割り当て）などのモック動作へフォールバック
            response = llm_provider.complete(prompt, max_tokens=150)

            items = []
            if response:
                items = clean_json_response(response)

            # フォールバック処理: LLMが使えない、またはパースエラーの時
            if not items:
                # 口コミに含まれる簡易的な重要ワードマッチング
                fallback_keywords = ["梅干し", "梅ソフト", "まいたけ弁当", "まいたけコロッケ", "海鮮丼"]
                items = [kw for kw in fallback_keywords if any(kw in r for r in reviews)]

            if items:
                station.reputation_items = json.dumps(items, ensure_ascii=False)
                updated_count += 1
                print(f"-> 抽出結果: {items}")
            else:
                print("-> おすすめ商品を抽出できませんでした")

        db.commit()
        print(f"\n処理完了: {updated_count}/{len(stations)} 駅の人気商品を更新しました。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
