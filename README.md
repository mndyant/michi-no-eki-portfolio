# 近畿道の駅スタンプラリー 巡回計画AI

> **ポートフォリオ確認用コピー（Private）**
>
> このコピーは応募前の目視確認用です。第三者データの配布条件を確認中のため、
> `data/raw/stations_kinki.json` と `data/processed/chunks.json` は意図的に含めていません。
> 下記の159駅・460チャンクの説明は元アプリの設計範囲を示すもので、このコピーで同梱される件数ではありません。
> 現在の再現手順は、`backend/scripts/seed_demo.py` が作る自作の架空8駅データを対象にします。

[![CI](https://github.com/mndyant/michi-no-eki/actions/workflows/ci.yml/badge.svg)](https://github.com/mndyant/michi-no-eki/actions/workflows/ci.yml)

近畿道の駅スタンプラリー（大阪・京都・兵庫・奈良・和歌山・滋賀・福井、全159駅）における
**実際の巡回計画の課題を解決するための意思決定支援アプリ**です。

施設の営業時間、スタンプ受付終了時刻、移動時間、滞在目的（昼食・スイーツ・土産）、
再訪問しにくさ、施設の魅力を考慮して、「どこを・どの順番で・何時に巡るか」を決めます。

単純な最短ルートではなく——

- **閉店時刻の早い施設を優先する**（スタンプは営業時間内しか押せない）
- **山間部など別日に再訪問しにくい施設を、多少の遠回りでも同日に組み込む**
- **予定遅延時に「どの駅を諦めるべきか」を再計算する**

——といった複雑な条件を考慮し、複数の代替案を提示します。
最終的なナビゲーションはGoogleマップに委譲し、本アプリはその**前段の計画立案**に特化しています。

## スクリーンショット

**自動ルート提案**: 自然文入力（方面・時間帯・高速利用の指定）の解釈結果とともに3プランを比較表示
（画面画像は目視確認後に追加）

**手動ルート計算結果**: 到着/出発時刻表・スタンプ受付締切までの余裕・What-ifシミュレーションパネル
（画面画像は目視確認後に追加）

**道の駅一覧**: 159駅の訪問管理・特徴タグ・再訪問しにくさスコア
（画面画像は目視確認後に追加）

## なぜ作ったか

スタンプラリー参加者（開発者自身）が毎週末直面する現実の課題:

> 「今日は4駅回りたい。でもEは17時にスタンプ受付が終わる山間の駅で、今日を逃すと
> 次に来られるのはいつになるか分からない。Cでの昼食を20分短縮すればEに間に合うのか？」

この判断を地図アプリだけで行うのは難しく、営業時間・締切・滞在時間・再訪問コストを
まとめて扱う専用ツールが必要でした。

## 主な機能

全フェーズ実装済みです。

| 機能 | 状態 |
|---|---|
| 道の駅一覧・訪問管理・滞在時間管理（159駅） | ✅ フェーズ1 |
| 手動ルート計算（到着/出発時刻・スタンプ締切判定・Google Mapsリンク・逆算出発時刻） | ✅ フェーズ2・4.5 |
| 自動ルート提案（最大効率/軽め/グルメ重視/再訪困難優先/遠方から戻る、5案比較） | ✅ フェーズ3・4.5 |
| What-ifシミュレーション（遅延・滞在延長・訪問駅除外の再計算、最遅出発時刻の逆算） | ✅ フェーズ4 |
| 訪問記録（購入品・感想・写真タグ付きアップロード） | ✅ フェーズ4.5 |
| 高速道路利用の区間選択、方面・時間帯を自然文で指定した自動提案 | ✅ フェーズ4.5 |
| AI機能（自然文での条件入力、プランごとの推薦理由生成） | ✅ フェーズ5 |
| RAG検索基盤（SQLite FTS5）による名産・特徴のルールベース抽出 | ✅ フェーズ5 |

各フェーズの実装・検証の詳細は [PROGRESS.md](PROGRESS.md) を参照してください。

## 技術スタック

| レイヤー | 技術 | 選定理由 |
|---|---|---|
| フロントエンド | Next.js (App Router) + TypeScript + Tailwind CSS | 型安全なUI開発とレスポンシブ対応 |
| バックエンド | Python 3.14 + FastAPI + SQLAlchemy 2.x | ロジック層をAPI層から分離し単体テスト可能に |
| DB | SQLite（将来PostgreSQL移行可能な設計） | セットアップ不要で第三者が即座に動かせる |
| 検索（RAG） | SQLite FTS5（trigramトークナイザ） | 依存ゼロで日本語の部分一致検索が可能。ベクトル検索は非対応 |
| 移動時間 | Haversine距離×道路係数（既定）/ OSRM（任意） | 有料APIに依存しない |
| LLM | Anthropic Claude API（**任意**） | キー未設定でも全機能がルールベースで動作（`app/services/ai/llm_provider.py`） |
| 最終ナビ | Google Maps ディープリンクURL | APIキー不要・無料 |
| CI | GitHub Actions | PRごとにbackend pytest・frontend lint/buildを自動実行 |

**設計方針: APIキーが1つも無くても全機能が動く。** 外部連携はすべてプロバイダインター
フェースで抽象化し、モック/フォールバック実装を備えています。

## セットアップ

### 必要なもの

- Python 3.11+（開発環境は3.14）
- Node.js 20+（開発環境はv24）
- APIキーは**不要**（任意でAnthropic APIキーを設定可能）

### バックエンド

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

# DB初期化（ポートフォリオ確認用）
python scripts/init_db.py
# PowerShell: $env:MICHI_DB_PATH = "$PWD\demo-portfolio.db"; python scripts/seed_demo.py
# Mac/Linux:  MICHI_DB_PATH=./demo-portfolio.db python scripts/seed_demo.py

# RAG検索・名産抽出データの投入（第三者データの許諾確認後のみ）
python scripts/load_chunks.py
python scripts/extract_specialties.py

# 起動（http://localhost:8000、API仕様は /docs で確認可）
uvicorn app.main:app --reload --port 8000
```

Windowsで `python` コマンドがMicrosoft Storeにリダイレクトされる場合は、venv作成のみ
`%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe` のような実行環境のフルパスを使い、
以降は `.venv\Scripts\python.exe` を使ってください。

### フロントエンド

```bash
cd frontend
npm install
copy .env.local.example .env.local   # Windows（Mac/Linuxは cp）
npm run dev
# → http://localhost:3000
```

### 環境変数（任意）

ルートの `.env.example` を参照。すべて未設定でも動作します。

## プロジェクト構成

```
michi-no-eki/
├── docs/
│   ├── DESIGN.md          # 設計書（要件・データモデル・API・ルート計算方針）
│   └── ER_DIAGRAM.md      # ER図・システム構成図（Mermaid）
├── data/                  # 第三者データは権利確認まで同梱しない。説明はdata/README.mdを参照
├── backend/
│   ├── app/
│   │   ├── api/           # ルーティング層（薄く保つ）
│   │   ├── services/
│   │   │   ├── route/     # 手動/自動ルート計算・What-if・時刻表（純粋関数中心）
│   │   │   ├── distance/  # 移動時間プロバイダ（haversine既定 / OSRM任意）
│   │   │   ├── ai/        # 自然文解釈・推薦理由生成・llm_provider抽象化
│   │   │   └── rag/       # FTS5全文検索・名産のルールベース抽出
│   │   ├── models/        # SQLAlchemyモデル
│   │   ├── schemas/       # Pydanticスキーマ
│   │   └── data_pipeline/ # データ収集・チャンキング（GML/Wikipedia）
│   ├── scripts/           # DB初期化・シード投入・chunks投入・名産抽出
│   └── tests/             # pytest（サービス層・API、検証時192件）
└── frontend/
    └── src/app/
        ├── stations/      # 道の駅一覧（訪問管理・名産表示・訪問記録）
        └── routes/
            ├── new/       # 手動ルート作成・What-ifパネル
            └── suggest/   # 自動ルート提案（自然文入力対応）
```

## データについて

- このポートフォリオコピーには、第三者データの再配布条件を確認するまで、
  `stations_kinki.json` と `chunks.json` を同梱しません。実データを使う場合は、
  取得時点の条件・出典表示・配布形態を確認し、許諾確認後に別途投入してください。
  目視確認とCIは `backend/scripts/seed_demo.py` の自作・架空8駅で再現できます。
- `scripts/seed.py` はupsert方式のため、**再実行しても訪問済みフラグ・滞在時間カスタム・
  訪問記録・口コミ等のユーザーデータは失われません**（実行前にdata.dbを自動バックアップもします）
- **1次情報（元アプリの設計上の参照先）**: [国土数値情報（道の駅データ）](https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P35.html) — 公開前に個別利用条件を確認する
- **2次情報**: Wikipedia API（CC BY-SA 4.0） — 概要・特産品（460チャンクをSQLite FTS5に投入し、
  「名産」「名物」等のキーワードを含む文をルールベースで抽出。作文はしない方針）
- 出典・ライセンス・引用範囲の確認状況は [data/README.md](data/README.md) を参照してください
- 営業時間・スタンプ受付時刻は初期値として仮値（09:00-17:00）を投入し、画面上で
  「未確認」ラベルを表示。確認済みの駅から順次上書きする運用です
- 再訪問しにくさスコア・クラスタは座標から機械的に初期算出し、算出根拠を保存・表示します

## 設計ドキュメント

- [docs/DESIGN.md](docs/DESIGN.md) — 要件・データモデル・API一覧・ルート計算ロジック・リスクと対策
- [docs/ER_DIAGRAM.md](docs/ER_DIAGRAM.md) — ER図・システム構成図（Mermaid）
- API仕様は起動後 `http://localhost:8000/docs`（Swagger UI）で確認できます

## 開発の進め方

- Issue単位のfeatureブランチ → Pull Request → mainへマージ
- 進捗は [PROGRESS.md](PROGRESS.md)、設計判断は [docs/DESIGN.md](docs/DESIGN.md) に記録
- 2026年5月まではRAG検索アプリとして開発し、同7月に巡回計画支援へ全面ピボット
  （旧実装はタグ `pre-pivot-streamlit-rag` に保存。データ収集資産は継続利用）

## ライセンス・利用上の注意

- コードは [MITライセンス](LICENSE) です
- 同梱データ（道の駅基本データ・Wikipedia由来チャンク）の出典・利用条件は
  [data/README.md](data/README.md) を参照してください
- OSRM公開デモサーバは個人学習・ポートフォリオ用途に限定して利用しています
- 口コミ・名産品情報は要約のみを扱い、取得元と確認日を記録します
