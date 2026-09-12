"""Wikipedia APIで道の駅の記事を取得して data/raw/wiki/ に保存する。

カテゴリ「{府県名}の道の駅」から正確な記事タイトルを取得し、
バッチ処理でextractを取得する。
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
from pathlib import Path

import requests

WIKI_API = "https://ja.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "michi-no-eki-rag/1.0 (educational project)"}
SLEEP_SEC = 1.0
TIMEOUT_SEC = 10
BATCH_SIZE = 5   # 429対策: 小さめに設定
RETRY_WAIT_SEC = 15

# 近畿7府県の道の駅カテゴリ
KINKI_CATEGORIES = [
    "Category:福井県の道の駅",
    "Category:滋賀県の道の駅",
    "Category:京都府の道の駅",
    "Category:大阪府の道の駅",
    "Category:兵庫県の道の駅",
    "Category:奈良県の道の駅",
    "Category:和歌山県の道の駅",
]


def fetch_category_titles() -> list[str]:
    """近畿7府県カテゴリから道の駅記事タイトル一覧を取得する"""
    titles = []
    for cat in KINKI_CATEGORIES:
        resp = requests.get(WIKI_API, params={
            "action": "query",
            "list": "categorymembers",
            "cmtitle": cat,
            "cmlimit": "200",
            "cmtype": "page",
            "format": "json",
        }, headers=HEADERS, timeout=TIMEOUT_SEC)
        resp.raise_for_status()
        members = resp.json()["query"]["categorymembers"]
        titles.extend(m["title"] for m in members)
        time.sleep(SLEEP_SEC)
    return titles


def _norm(name: str) -> str:
    """マッチング用正規化: 全角英数→半角、スペース除去、括弧内除去"""
    name = unicodedata.normalize("NFKC", name)   # 全角英数→半角
    name = re.sub(r"\s", "", name)                # スペース全除去
    name = re.sub(r"[（(][^）)]*[）)]", "", name)  # 括弧内除去
    return name


def build_name_map(wiki_titles: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """駅名 → Wikipedia記事タイトル のマッピングを2種類作成する。

    返り値:
        exact_map:  正確な駅名 → タイトル
        norm_map:   正規化した駅名 → タイトル（表記ゆれ吸収用）
    """
    exact_map: dict[str, str] = {}
    norm_map: dict[str, str] = {}
    for title in wiki_titles:
        name = re.sub(r"^道の駅", "", title)
        name = re.sub(r"\s*（.+?）|\s*\(.+?\)$", "", name).strip()
        exact_map[name] = title
        norm_map[_norm(name)] = title
    return exact_map, norm_map


def fetch_extracts_batch(titles: list[str]) -> dict[str, str]:
    """記事タイトルリストをバッチでextract取得する"""
    results: dict[str, str] = {}
    total = len(titles)
    for i in range(0, total, BATCH_SIZE):
        batch = titles[i: i + BATCH_SIZE]
        print(f"  バッチ取得中 {i + 1}〜{min(i + BATCH_SIZE, total)}/{total}件...")
        resp = None
        for attempt in range(5):
            try:
                resp = requests.get(WIKI_API, params={
                    "action": "query",
                    "titles": "|".join(batch),
                    "prop": "extracts",
                    "explaintext": True,
                    "exintro": True,   # 導入部のみ取得（バッチ制限を回避）
                    "redirects": True,
                    "format": "json",
                }, headers=HEADERS, timeout=TIMEOUT_SEC)
                if resp.status_code == 429:
                    wait = RETRY_WAIT_SEC * (attempt + 1)
                    print(f"  429 レート制限 - {wait}秒待機 (試行{attempt + 1}/5)...")
                    time.sleep(wait)
                    resp = None
                    continue
                resp.raise_for_status()
                break
            except requests.RequestException:
                if attempt == 4:
                    raise
                time.sleep(RETRY_WAIT_SEC)
        if resp is None:
            raise RuntimeError("429 Too Many Requests: リトライ上限に達しました")
        data = resp.json()["query"]
        # リダイレクト元タイトル → 実際のタイトル のマッピングを取得
        redirect_map = {r["from"]: r["to"] for r in data.get("redirects", [])}
        pages = data["pages"]
        for page in pages.values():
            if page.get("missing") is None:
                results[page["title"]] = page.get("extract", "")
        # リダイレクト元タイトルでも参照できるようにする
        for from_t, to_t in redirect_map.items():
            if to_t in results:
                results[from_t] = results[to_t]
        time.sleep(SLEEP_SEC)
    return results


def _safe_filename(name: str) -> str:
    return name.replace(" ", "_").replace("/", "_").replace("\\", "_")


def collect_all(stations_json: Path, output_dir: Path) -> None:
    """全道の駅のWikipedia記事をカテゴリAPIベースで取得する"""
    output_dir.mkdir(parents=True, exist_ok=True)
    stations = json.loads(stations_json.read_text(encoding="utf-8"))

    print("カテゴリからタイトル一覧を取得中...")
    wiki_titles = fetch_category_titles()
    print(f"  {len(wiki_titles)}件のWikipedia記事タイトルを取得")

    exact_map, norm_map = build_name_map(wiki_titles)

    print("extractをバッチ取得中...")
    all_titles = list(exact_map.values())
    extracts = fetch_extracts_batch(all_titles)
    print(f"  {len(extracts)}件のextractを取得")

    found = not_found = 0
    for station in stations:
        name = station["name"]
        pref = station["pref"]
        fname = output_dir / f"{_safe_filename(name)}.json"

        # 完全一致 → 正規化一致 の順でマッチング
        wiki_title = exact_map.get(name) or norm_map.get(_norm(name))
        extract = extracts.get(wiki_title, "") if wiki_title else ""

        record = {
            "name": name,
            "pref": pref,
            "wiki_title": wiki_title or "",
            "extract": extract,
            "found": bool(extract),
        }
        fname.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")

        if record["found"]:
            found += 1
            print(f"[OK] {name}({pref}) - {wiki_title}")
        else:
            not_found += 1
            print(f"[--] {name}({pref}) - タイトル未マッチ")

    print(f"\n完了: 取得={found}, 未マッチ={not_found} / 全{len(stations)}件")


if __name__ == "__main__":
    root = Path(__file__).parents[3]
    collect_all(
        stations_json=root / "data" / "raw" / "stations_kinki.json",
        output_dir=root / "data" / "raw" / "wiki",
    )
