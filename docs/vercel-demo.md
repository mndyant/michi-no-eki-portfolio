# 大阪府の道の駅 — Vercel公開デモ

URL: https://michi-no-eki-portfolio.vercel.app

## 体験する

1. ホームの「3駅のサンプルで試す」を開く。
2. 大阪駅発、しらとりの郷・羽曳野 → 近つ飛鳥の里太子 → かなん の条件で計算する。
3. 駅・訪問順・滞在時間を変えて再計算する。結果下のWhat-ifで遅延や駅除外も比較できる。
4. 「自動提案」では上限3駅を既定として、5つの評価方針の候補を比較する。

## データと限界

`data/demo/stations_osaka.json` は、作成者が用意した `stations_kinki.json` から本人の明示指示で大阪府だけを抽出した10駅。
名称・住所・座標・駅リンクなどの値はそのまま使用。施設の紹介文や写真、訪問記録、検索チャンクは追加していない。
`provenance.json` に抽出条件と元ファイルのSHA-256を記録。抽出スクリプトは `scripts/extract_osaka_demo.py`。

- 営業・スタンプ受付は全曜日09:00〜17:00という計算用仮値。休業日・現時点の営業状況は未確認。
- 最終確認日を捏造しないため、公開APIの `last_verified_at` はnull。
- 施設の目的・規模・再訪困難度は既存の変換ルールによる推定。大阪10駅だけでクラスタを再構成する。
- 移動はHaversine距離と係数による概算。道路・渋滞・高速道路の実際の接続を保証しない。
- 日付未指定時の既存計算はスタンプ終了時刻を基準とする。訪問時の最新情報は各駅の案内で確認する。
- 自然文の解釈・提案理由はルールベース。LLM呼び出しはない。

## 公開構成

VercelのFastAPI Python Functionで、既存のmanual / suggest / what-ifサービスを呼ぶ。
Next.js画面は `NEXT_PUBLIC_DEMO=1` で静的exportし、同じプロジェクトの `site/` をFastAPIのStaticFilesとして配信する。
生成後のStaticFilesをCDNへ昇格できるVercelの仕様に合わせて登録しているが、今回の配信確認はFunction経由も含めて行った。
APIは同一オリジン。外部DB・APIキーは不要。

`backend/app/public_demo.py` は公開専用の読取・計算API。SQLiteをリクエストごとにメモリ上に生成して10駅を投入し、終了時に破棄する。
既存サービスの距離キャッシュ書込みもそのリクエスト内に閉じる。サーバーのファイル・DBへ入力を永続保存しない。
駅更新・訪問記録・写真APIは登録しない。ルートは重複なし10駅以内、滞在0〜480分、POST本文16KB以内。
API応答はno-store。従来の `backend/app/main.py` によるローカル運用は別の起動経路として保持する。

## 起動・公開

```powershell
# リポジトリのルートで、PythonとNode.jsを準備
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python scripts/build_public.py
.\.venv\Scripts\python -m uvicorn index:app --port 8000

# http://localhost:8000 を確認後
vercel link
vercel deploy
vercel deploy --prod
```

VercelではPython3.12を指定。ビルドコマンドが `npm ci` → `next build` → `site/`へのコピーを実行。
公式仕様: https://vercel.com/docs/frameworks/backend/fastapi

## 検証記録（2026-10-03）

- 公開API・既存手動/提案/What-if/並べ替え回帰テスト: 52 passed。バックエンド全体: 212 passed, 3 skipped（元の近畿全体データが必要なテスト）。
- フロントエンド既存テスト: 8 passed。ESLint、TypeScript、Next静的ビルド成功。
- ローカル画面: 3駅43.0km、移動67分。出発60分遅延で最初の到着08:41→09:41へ変化。
- 5種類の自動提案を画面で確認。個人データ更新APIは404/405。
- 並行計算の同一結果と、別リクエストのDB隔離をテスト。
- 公開環境: 匿名アクセス、10駅検索、3駅計算、60分遅延を確認。390px幅のホーム・計画画面で横はみ出しなし。コンソールエラーなし。
- Claude Opusで構成、SonnetでUIを独立レビュー。データパスと静的配信を修正し、提案駅数ラベル・チップのフォーカス表示・結果の計算条件の説明を改善。
- 初回の静的出力が404になる問題は、ビルド生成物を `site/` のStaticFilesとして明示登録して解消。
