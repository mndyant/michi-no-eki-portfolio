# 近畿道の駅スタンプラリー 巡回計画AI

> **ポートフォリオ確認用コピー（Private）**
>
> このコピーは応募前の目視確認用です。第三者データの配布条件を確認中のため、
> `data/raw/stations_kinki.json` と `data/processed/chunks.json` は意図的に含めていません。
> 下記の159駅・460チャンクの説明は元アプリの設計範囲を示すもので、このコピーで同梱される件数ではありません。
> 現在の再現手順は、`backend/scripts/seed_demo.py` が作る自作の架空8駅データを対象にします。

[![CI](https://github.com/mndyant/michi-no-eki-portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/mndyant/michi-no-eki-portfolio/actions/workflows/ci.yml)

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

**自動ルート提案**: 自然文入力（方面・時間帯・高速利用の指定）の解釈結果とともに最大5プランを比較表示
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

巡回計画・訪問記録・条件入力の機能を実装しています。現在の同梱デモは架空8駅です。

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

機能とデータモデルは [設計書](docs/DESIGN.md) を参照してください。実施設での所要時間・営業時間の精度検証は今後の課題です。

## 技術スタック

| レイヤー | 技術 | 選定理由 |
|---|---|---|
| フロントエンド | Next.js (App Router) + TypeScript + Tailwind CSS | 型安全なUI開発とレスポンシブ対応 |
| バックエンド | Python 3.14 + FastAPI + SQLAlchemy 2.x | ロジック層をAPI層から分離し単体テスト可能に |
| DB | SQLite（将来PostgreSQL移行可能な設計） | セットアップ不要で第三者が即座に動かせる |
| 検索（RAG） | SQLite FTS5（trigramトークナイザ） | 依存ゼロで日本語の部分一致検索が可能。ベクトル検索は非対応 |
| 移動時間 | Haversine距離×道路係数（既定）/ OSRM（任意） | 有料APIに依存しない |
| LLM | Anthropic Claude API（**任意**） | キー未設定時はルールによる条件解釈・推薦理由を使用 |
| 最終ナビ | Google Maps ディープリンクURL | APIキー不要・無料 |
| CI | GitHub Actions | PRごとにbackend pytest・frontend lint/buildを自動実行 |

APIキーなしでルート計算・訪問記録のデモを動かせます。LLMによる自由文の解釈とルールによる解釈では対応範囲が異なります。
検索チャンクは同梱していないため、実データの名産検索はこのデモの対象外です。

## セットアップ

### 必要なもの

- Python 3.14（Windows検証環境）
- Node.js 22以上（CIは22）
- APIキーは**不要**（任意でAnthropic APIキーを設定可能）

### バックエンド

PowerShellの例です。リポジトリのルートから実行します。

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# 初回だけ実行。既存の駅があるDBへの再投入は拒否します。
$env:MICHI_DB_PATH = Join-Path $PWD 'demo-portfolio.db'
$env:DISTANCE_PROVIDER = 'haversine'
$env:ANTHROPIC_API_KEY = ''
.\.venv\Scripts\python.exe scripts/seed_demo.py

# 同じPowerShellで起動して同じDBを使用
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

再起動するときも同じ `MICHI_DB_PATH` を指定し、シード投入を省略してください。
API仕様は `http://127.0.0.1:8000/docs` で確認できます。
Mac/Linuxでは `export MICHI_DB_PATH="$PWD/demo-portfolio.db"` と設定し、Python実行パスを `.venv/bin/python` に読み替えます。

### フロントエンド

別のPowerShellで、リポジトリのルートから実行します。

```powershell
cd frontend
npm ci
$env:NEXT_PUBLIC_API_BASE_URL = 'http://127.0.0.1:8000'
npm run dev
# → http://localhost:3000
```

### テスト

```powershell
# backend/ で実行。実APIへの接続は不要です。
.\.venv\Scripts\python.exe -m pytest tests -q
# frontend/ で実行
npm test
npm run lint
npm run build
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
  画面確認は `backend/scripts/seed_demo.py` の自作・架空8駅で再現できます。CIは独立したテストデータを使います。
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
- 設計判断は [docs/DESIGN.md](docs/DESIGN.md) に記録
- 既存の個人開発から導入したコピーです。このリポジトリの履歴は導入時点からの整備・修正を記録します。

## ライセンス・利用上の注意

- コードは [MITライセンス](LICENSE) です
- 非同梱の第三者データの出典・利用条件の確認状況は
  [data/README.md](data/README.md) を参照してください
- OSRM公開デモサーバは個人学習・ポートフォリオ用途に限定して利用しています
- 口コミ・名産品情報は要約のみを扱い、取得元と確認日を記録します
