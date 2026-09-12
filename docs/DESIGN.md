# 近畿道の駅スタンプラリー巡回計画AI — 設計書

> 本ドキュメントはコーディング開始前の要件整理・設計合意用。
> 既存のRAGプロジェクト（データ収集済み・158駅）を土台に、
> Next.js + FastAPI + SQLite のフルスタックへ全面移行する前提で書いている。
> 移行判断の経緯は git 履歴とは別に、このドキュメントが正とする。

---

## 1. 要件の整理

**目的**: 近畿道の駅スタンプラリー参加者（大阪在住、車、土日利用、1日4〜5件）が
「どこを・どの順で・何時に巡るか」を決める意思決定支援ツールを作る。
最終ナビゲーションはGoogleマップに委譲し、本アプリはその前段の巡回計画に特化する。

**中核となる価値**:

- 単純な最短距離ではなく、営業時間・スタンプ締切・滞在目的・再訪問しにくさを
  考慮した「現実的に回れる」プランを複数案で提示する
- 予定が崩れた場合（遅延・延泊・道の駅を諦める等）にリアルタイムで代替案を出す
- 名産品・口コミ・季節情報を、断定を避けつつ要約して提示する

**既存資産の活用**:

- 近畿7府県158駅の基本情報（GML由来: 名称・住所・座標・施設フラグ）
- Wikipedia由来の説明文（158/159件取得済み）
- チャンク化済みテキスト460件（basic/facilities/wikipedia種別）

これらは巡回計画に必須の「営業時間」「スタンプ締切」「滞在目的」「名産品」
「口コミ」を含んでいないため、**フェーズ1でスキーマ拡張とサンプル値の仮置きが必要**。

---

## 2. MVPの範囲（フェーズ1）

- Next.js（TypeScript）+ FastAPI の初期構成
- SQLiteへの移行（158駅データを新スキーマへマイグレーション）
- 道の駅CRUD（一覧・詳細・編集）
- 訪問済み／未訪問の管理
- 営業時間・スタンプ受付時間の管理（仮データ→個別上書き可能）
- 滞在時間モデル（目的別デフォルト値＋ユーザー編集）
- サンプルデータ投入（158駅、既存収集データを変換）

フェーズ1終了時点で「一覧を見て、訪問済みをチェックし、滞在時間を調整できる」
状態がゴール。ルート計算・AI機能は含めない。

---

## 3. 非MVP機能（フェーズ2以降）

| フェーズ | 内容 |
|---|---|
| 2 | 手動選択した複数駅の順序→到着/出発時刻計算、締切警告、Googleマップ URL生成 |
| 3 | 自動ルート提案（締切優先・クラスタ考慮・複数プラン） |
| 4 | What-ifシミュレーション（遅延・滞在延長・駅除外の再計算） |
| 5 | AI機能（自然文条件解釈、推薦理由生成、口コミ/名産要約、季節情報） |
| 6 | 就活向け整備（README、ER図、API仕様、テスト、CI、PR運用） |

---

## 4. システム構成

> Mermaid形式の最新図（ER図・システム構成図）は [ER_DIAGRAM.md](ER_DIAGRAM.md) 参照。

```
[Next.js (TS/React)]  ←REST/JSON→  [FastAPI (Python)]  ←→  [SQLite]
        │                                  │
        │                                  ├→ services/route  … 巡回計画ロジック（純粋関数、DB非依存）
        │                                  ├→ services/rag    … 検索（埋め込み類似度）
        │                                  ├→ services/ai     … LLM呼び出し + ルールベースfallback
        │                                  └→ services/distance … 移動時間取得（OSRM or haversine fallback）
        │
        └→ Googleマップ ディープリンク（APIキー不要のURL方式、遷移のみ）
```

**フロントエンド**: Next.js App Router、TypeScript、レスポンシブ（Tailwind CSS想定）。
**バックエンド**: FastAPI。`api/`（ルーティング）と `services/`（ロジック）を分離し、
ロジック層は単体テスト可能な純粋関数中心にする。
**DB**: 初期はSQLite（ファイル1本、セットアップ不要）。将来PostgreSQL移行を見据え、
SQLAlchemy経由でアクセスし生SQLに依存しない。
**外部連携は全て抽象化**: `distance_provider` / `llm_provider` インターフェースを切り、
APIキー未設定時はモック実装（haversine距離、ルールベース文章生成）に自動フォールバック。

**既存Streamlit/pgvector/LangChain実装の扱い**（2026-07-11 ユーザー合意済み）:
`src/data/collectors`・`src/data/processors`・`src/data/models.py` はデータ収集ロジックとして
そのまま `backend/app/data_pipeline/` 等に移植・再利用する。
旧実装のアーカイブは別管理の凍結スナップショット（同一コミット 2f02426）を充てる。
応募用コピーにはローカルの保存場所を記録しない。
保険として本体リポジトリの現HEADに `pre-pivot-streamlit-rag` タグを打った上で、
`src/ui`・`src/rag`・`docker-compose.yml` 等の旧スタック専用ファイルは本体から削除する
（git履歴＋タグ＋アーカイブクローンの三重に残るため `legacy/` フォルダは作らない）。

---

## 5. データモデル（SQLite / SQLAlchemy）

### stations（道の駅マスタ）

| カラム | 型 | 備考 |
|---|---|---|
| id | INTEGER PK | |
| station_id | TEXT UNIQUE | GML由来ID（例: P35_483）。既存データを継続利用 |
| name | TEXT | |
| pref | TEXT | |
| city | TEXT | 住所から分離（既存addressは市町村までしかない駅もあり、後で補完） |
| address | TEXT | |
| lat / lon | REAL | |
| official_url | TEXT | |
| business_hours | TEXT(JSON) | 曜日別。仮値: 全駅 `09:00-17:00`、定休日なし |
| stamp_start / stamp_end | TEXT(HH:MM) | 仮値: `09:00` / `17:00` |
| closed_days | TEXT | 仮値: 空（不明） |
| visited | BOOLEAN | デフォルトFalse |
| visited_date | DATE NULL | |
| stay_time_min_default | INTEGER | 仮値15分（スタンプ＋軽く店内） |
| facility_scale | TEXT | small/medium/large。仮値: GMLの施設数から簡易推定 |
| good_for_lunch / good_for_sweets / good_for_souvenir | BOOLEAN | 仮値: `facilities.restaurant`等から推定、未確認は3項目ともFalse |
| has_spa | BOOLEAN | `facilities.spa`をそのまま利用 |
| scenery_score | INTEGER NULL | 1-5、未評価はNULL |
| is_mountainous | BOOLEAN | 仮値: 住所・座標からの簡易判定（後述7章） |
| revisit_difficulty_score | INTEGER | 1-5、算出ロジックは7章 |
| revisit_difficulty_reason | TEXT | スコア算出根拠を文章化して保存 |
| cluster_id | INTEGER NULL FK→clusters | |
| reputation_items | TEXT(JSON) | 口コミで評判の商品。初期は空配列 |
| local_specialty | TEXT(JSON) | 地域の名産品。初期は空配列（Wikipedia抽出候補あり） |
| seasonal_specialty | TEXT(JSON) | 季節の名産品。初期は空配列 |
| user_memo | TEXT | |
| source | TEXT | 例: `国土数値情報+Wikipedia(2026-05-17)` |
| last_verified_at | DATE | |

### clusters（近隣クラスタ）

| id | name | description |
|---|---|---|
| INTEGER PK | TEXT | TEXT |

初期は府県＋距離の粗いグルーピングで仮登録（8章参照）。

### station_distances（駅間移動時間キャッシュ）

`from_station_id, to_station_id, distance_km, duration_min, source(osrm/haversine), updated_at`
移動時間APIの呼び出し回数を抑えるためのキャッシュテーブル。対称なので `from < to` で正規化して1行のみ保持。

### visit_records（訪問記録）

`id, station_id, visit_date, purchased_items(JSON), food(JSON), impression(TEXT), photo_url, want_revisit(BOOLEAN), next_memo(TEXT)`

### routes / route_stops（フェーズ2以降で追加）

保存済みルートプラン。フェーズ1では未作成（テーブル設計のみ本書に記載し、実装は先送り）。

---

## 6. API一覧（全フェーズ実装済み。フェーズ6で最新化）

Swagger UI（`/docs`）が実行時の正だが、全体像をここにまとめる。

### 道の駅・クラスタ（フェーズ1）

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/api/stations` | 一覧取得（pref・visited・clusterでフィルタ可） |
| GET | `/api/stations/{id}` | 詳細取得（local_specialty含む） |
| POST | `/api/stations` | 新規登録 |
| PUT | `/api/stations/{id}` | 部分更新（滞在時間・メモ・営業時間の上書きなど） |
| DELETE | `/api/stations/{id}` | 削除 |
| PATCH | `/api/stations/{id}/visit` | 訪問済みフラグ切替＋訪問日記録 |
| GET | `/api/clusters` | クラスタ一覧 |
| GET | `/health` | ヘルスチェック |

### ルート計算（フェーズ2〜4.5）

| メソッド | パス | 内容 |
|---|---|---|
| POST | `/api/routes/manual` | 手動選択した駅の時刻表・締切判定・Maps URL計算。`departure_mode=latest`で逆算出発時刻も算出 |
| POST | `/api/routes/suggest` | 自動ルート提案（5プロファイル比較）。`free_text`で自然文条件解釈も可（フェーズ5） |
| POST | `/api/routes/what-if` | 遅延・駅除外・帰着締切変更を反映した再計算、最遅出発時刻の逆算 |

### 訪問記録・写真（フェーズ4.5）

| メソッド | パス | 内容 |
|---|---|---|
| GET | `/api/stations/{station_id}/visit-records` | 訪問記録一覧（新しい順） |
| POST | `/api/stations/{station_id}/visit-records` | 訪問記録作成（駅が自動で訪問済みになる） |
| PUT | `/api/visit-records/{record_id}` | 訪問記録の部分更新 |
| DELETE | `/api/visit-records/{record_id}` | 訪問記録削除 |
| POST | `/api/visit-records/{record_id}/photos` | 写真アップロード（multipart、タグ付き、8MB上限） |
| PUT | `/api/photos/{photo_id}` | 写真のタグ更新 |
| DELETE | `/api/photos/{photo_id}` | 写真削除 |

`/photos/{file_name}` で写真ファイルを静的配信（`data/photos/` 配下）。

---

## 7. 画面一覧（フェーズ1で実装する範囲）

- **道の駅一覧画面**: 訪問済み/未訪問、営業時間、スタンプ受付時間、特徴タグ、
  再訪問しにくさスコア、クラスタ、名産品、メモを一覧・フィルタ表示
- （詳細編集は一覧画面上のインライン編集 or モーダルで、フェーズ1では簡易実装）

ルート作成／プラン結果／What-if／訪問記録画面はフェーズ2以降。

---

## 8. ルート計算ロジックの基本方針（フェーズ3で実装、設計のみ先出し）

1. **候補抽出**: 未訪問優先、指定エリア／クラスタでフィルタ
2. **締切考慮の並び替え**: スタンプ受付終了時刻が早い駅を後半に残さない
   （EDF: Earliest Deadline First に距離コストを加味した貪欲法）
3. **移動時間見積り**: `station_distances` キャッシュ→なければ距離プロバイダ呼び出し
4. **局所探索による改善**: 2-opt的な入れ替えで総移動時間を短縮しつつ、
   締切・営業時間・帰着時刻の制約を満たすか都度検証
5. **加点要素**: 再訪問しにくさスコアが高い駅、クラスタ内で回りきれる駅に
   優先度ボーナスを加える（7章のスコアを重みとして使用）
6. **複数プラン生成**: 評価関数の重み（移動時間最小化／締切余裕最大化／
   グルメ・買い物時間確保／再訪問しにくさ優先）を変えて4案生成
7. **制約が満たせない場合**: 訪問件数を1件減らして再計算し、
   除外候補（＝再訪問しやすい駅から優先的に）を提示

例（7章の設計そのまま踏襲）: C→E→Dのように遠回りでも締切の早いEを先に組み込む。

---

## 9. 無料で利用できる技術・サービス候補

| 用途 | 候補 | 備考 |
|---|---|---|
| フロントホスティング | Vercel（無料枠） | Next.jsとの親和性が高い |
| バックエンドホスティング | Render / Fly.io（無料枠） | コールドスタートあり、ポートフォリオ用途では許容 |
| DB | SQLite | ファイルベース、無料。将来Render PostgreSQL無料枠へ移行可 |
| 移動時間・距離 | Haversine距離×道路係数(1.3)を**既定**とし、OSRM公開デモサーバ（project-osrm.org）を任意の精度向上プロバイダとする | OSRMはAPIキー不要だがレート制限・SLA無し。**候補ルートに含まれる駅ペアのみオンデマンド取得**し `station_distances` にキャッシュ。158駅×157駅/2≒1.2万ペアの一括事前計算は行わない（デモサーバへの負荷・時間の両面で非現実的） |
| ルート表示（最終ナビ） | Google Maps ディープリンクURL | `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&waypoints=...` 形式。APIキー不要、遷移のみなので無料。Directions APIを使わない理由: (1)ナビ自体はGoogleマップアプリに委譲する設計 (2)有料APIはクレカ登録必須で「無料前提」要件に反する。**waypointsは最大9件**の制限あり（1日4〜5駅の想定利用では問題なし、UIでは9駅超の選択時に警告） |
| 検索（RAG用） | **SQLite FTS5（全文検索）を常時利用可能なベースライン**とし、ベクトル検索は任意の強化オプション | 本環境はPython 3.14のみで、sentence-transformersが依存するPyTorchの3.14対応が不確実（Windows）。FTS5はSQLite組込みで依存ゼロ・確実に動く。ベクトル検索を足す場合はONNXベース（fastembed等）またはCohere API（キー任意）をプロバイダとして後付け。既存chunks.json（460件）はFTS5テーブルへそのまま投入して流用 |
| LLM | Anthropic Claude API（任意） | キー未設定時はルールベース文章生成にフォールバック |
| 地図表示（自駅一覧のプレビュー等） | Leaflet + OpenStreetMapタイル | 無料・APIキー不要 |

---

## 10. 実装ステップ（全体、フェーズ1に集中して着手）

1. リポジトリ構成の切り替え（`frontend/` `backend/` を新設、既存データ収集コードを移植）
2. FastAPI初期化（`backend/app/main.py`、`/health`）
3. SQLiteスキーマ定義（SQLAlchemyモデル）とマイグレーションスクリプト
4. 既存 `stations_kinki.json` + `wiki/*.json` から新スキーマへの変換スクリプト（仮値の適用含む）
5. 道の駅CRUD API実装
6. Next.js初期化、一覧画面実装（API接続）
7. 訪問済み切替・滞在時間編集のUI実装
8. フェーズ1の動作確認（一覧表示→フィルタ→訪問済み切替→保存）

---

## 11. GitHub Issues案（フェーズ1分）

- `#1` chore: リポジトリ構成をfrontend/backendに再編成し、既存データ収集コードを移植する
- `#2` feat(backend): FastAPI初期構成と `/health` エンドポイント
- `#3` feat(backend): SQLiteスキーマ定義（stations/clusters/visit_records）
- `#4` feat(backend): 既存収集データ→新スキーマへの変換・投入スクリプト
- `#5` feat(backend): 道の駅CRUD API（一覧/詳細/更新/削除/訪問切替）
- `#6` feat(frontend): Next.js初期構成とレイアウト
- `#7` feat(frontend): 道の駅一覧画面（フィルタ・訪問済み切替・滞在時間編集）
- `#8` docs: README刷新（アプリの位置づけを16章の説明方針に合わせる）

各Issueは feature ブランチ（例: `feature/2-fastapi-init`）で作業し、PRでmainへマージする運用。

---

## 12. 不明点と仮置きする条件

| 項目 | 仮置き内容 | 理由 |
|---|---|---|
| 出発地（自宅） | ユーザーが画面上で緯度経度を指定できる任意地点として扱う。デフォルト値は大阪駅座標 | 個人情報を含めない方針（14章）と、想定利用シーン（大阪在住）に合わせた |
| 営業時間・スタンプ受付時間 | 全駅仮値 `09:00-17:00` を投入し、個別確認済みの駅から順次上書き | 現状の収集データに含まれておらず、全駅を今すぐ実地確認するのは非現実的 |
| 定休日 | 仮値「不明（空欄）」 | 同上。UI上で「未確認」ラベルを出す |
| 山間部フラグ | 初期は住所文字列に「山」「峠」「渓」等のキーワードが含まれるか、または近隣駅密度が低いかで簡易自動判定し、後で手動修正可能にする | 正確な地形判定は範囲外。簡易ヒューリスティックで仮置き |
| 再訪問しにくさスコア | 初期は「自宅からの距離」「クラスタ内未訪問駅数」「山間部フラグ」の3要素から機械的に算出し、算出根拠を`revisit_difficulty_reason`に文章化。手動上書き可 | 7章の評価要素を全部実装するのはフェーズ3以降 |
| クラスタ | 初期は府県＋座標の近接性（例: 半径15km以内）で粗く自動グルーピングし、名称は仮に「県名+方角」等を付与。後で手動編集可能 | 手動登録は158駅分だと非現実的なため、自動仮登録から始める |
| 名産品・口コミ | 初期は空、またはWikipedia抜粋から機械的に抽出できた場合のみ暫定表示し「要確認」ラベルを付ける | 口コミ転載はしない方針（11章）のため、要約ロジックはフェーズ5のAI機能待ち |
| OSRM公開デモサーバの扱い | 個人学習・ポートフォリオ用途に限定する旨をREADMEに明記し、失敗時はHaversineフォールバックで機能を止めない | 商用利用不可の利用規約のため |
| 既存Streamlit/pgvector資産の扱い | `dev/projects/michi-no-eki` クローンを凍結アーカイブとし、本体はタグを打った上で旧ファイルを削除 | 2026-07-11 ユーザー合意済み（4章参照） |
| `data/raw` `data/processed` の置き場所 | リポジトリルート直下のまま維持し、`backend/` から相対参照する | 既存スクリプト・ドキュメントとの整合を保ち、移動によるパス修正を避ける。フロントはAPIを通してのみデータに触れるため配置は影響しない |

---

## 13. 実利用フィードバックによる追加要件（2026-07-12、フェーズ4.5）

フェーズ2〜4をUIで実際に使ったユーザーからのフィードバック。訪問済みが増えてきた
実運用段階の需要（「こっち方面に行くから未訪問に寄りたい」「未訪問の多い地域を最大効率で回りたい」）に対応する。

### 13-1. 高速道路利用の区間選択（Issue #36・#39）

- 現在の移動時間見積りは**下道想定**（Haversine×1.3、時速40km換算）。これを既定のまま維持
- 区間（出発地→駅1、駅i→駅i+1、帰路）ごとに「高速を使う」を選択できるようにする
  - 例: 大阪府内は下道、帰りの和歌山県内は高速
- モデル: 高速区間は所要時間に係数（`HIGHWAY_DURATION_FACTOR = 0.55` ≒ 実効時速73km）を適用。距離は同一
- `highway_legs: list[int]`（区間インデックス）を manual / what-if リクエストに追加。
  suggest には全区間一括の `use_highway: bool` を追加（ルート確定前に区間指定はできないため）
- 正確な有料道路経路が必要になったらOSRMプロバイダ側で対応（当面は係数近似で十分）

### 13-2. 時間・地域・方面主導の自動提案 v2（Issue #37・#39）

「駅数を決めて回る」から「**時間・地域・方面を決めると未訪問の推奨ルートが出る**」への転換。

- 検索例: 「大阪7:00発、最後の駅に17:30到着、和歌山方面、未訪問」「地域だけ選んで未訪問攻略のおすすめ」
- suggest リクエスト追加項目:
  - `last_arrival_by: HH:MM | null` … 最後の駅への到着締切（全駅の到着がこれ以前）
  - `directions: list[8方位] | []` … 出発地から見た方面（±45°の扇形でフィルタ）。府県・クラスタと併用可
  - `max_stations` は既定9（Maps上限）に変更し「何駅回れるか」は結果側の情報にする
- プラン構成の変更（駅数は入力でなく出力）:
  - **最大効率**: 時間内に未訪問をできるだけ多く回る（上限9）
  - **軽め**: 最大4駅・締切余裕30分以上のゆったり案
  - **グルメ重視** / **再訪困難優先**: 従来どおり
  - **遠方から戻る**（2026-07-12追加要望）: 最も遠い駅（例: なち）を最初に訪ね、
    出発地方面へ戻りながら回る。先頭は実行可能な最遠駅、以降は「出発地に近づく駅」に加点
    （係数はw_travel未満にして駅飛ばしを防ぐ）。遠→近の並びを保つため2-optは適用しない。
    **ユーザー要望によりこのプランを先頭（デフォルト表示）にする**（Issue #47）
- 各プランに帰着（または最終駅出発）時刻 `finish_time` を含め、UIで「何駅・何時終わり」を並べて比較できるようにする

### 13-3. 訪問記録（Issue #38・#40、写真は #48）

道の駅ごとの感想・特色・買ってよかったものを記録したい（5章の visit_records を実装する）。

- API: `GET/POST /api/stations/{id}/visit-records`、`PUT/DELETE /api/visit-records/{id}`
- 記録項目: 訪問日・購入品（JSON配列）・食事（JSON配列）・感想・また行きたいか・次回メモ
- 訪問記録を作成した駅は `visited=True`・`visited_date` を自動更新する（手動切替も従来どおり可）
- UI: 道の駅一覧から駅ごとの記録モーダルを開き、過去の記録一覧＋新規追加。駅の「特色」は既存の `user_memo`（自由記入）を同モーダルで編集
- **写真（2026-07-12追加、Issue #48）**: 1記録に複数枚の写真をタグ付きで登録できる。
  `visit_photos` テーブル（file_name・tags）、実ファイルは `data/photos/`（git管理外）に保存し
  `/photos/{file_name}` で静的配信。multipartアップロード（8MB上限・画像拡張子のみ）

### 13-4. 逆算モード（Issue #46）

行きたい駅を先に選び、「何時までに出発すれば間に合うか」を逆算するモード。

- `POST /api/routes/manual` に `departure_mode: "fixed" | "latest"` を追加
- latest時は各駅のスタンプ締切（と任意の帰着締切 `return_by`）から**最遅出発時刻**を後ろ向きに計算し、
  その時刻で時刻表を作る。レスポンスの `departure_time` に採用した出発時刻が入る
- 0時に出ても間に合わない組み合わせは `no_feasible_departure` 警告を返し0:00起点で計算
- UI: ルート作成画面に「出発時刻を逆算する」トグル。結果に出発時刻・最終駅到着をタイル表示

### 13-5. 名産・おすすめ情報の扱い（Issue #49）

「Google口コミを参考に人気商品をピックアップしたい」という要望への対応方針:

- **Google口コミの機械取得は行わない**: スクレイピングは規約違反、Places APIは有料で
  「無料前提」（9章）に反する。口コミの転載をしない方針（12章）とも整合
- 代替1（実装済み）: 記録モーダルに各駅の**Google Maps口コミページへのリンク**と公式サイトリンクを設置
- 代替2（フェーズ5）: 収集済みWikipediaデータ（chunks 460件）から名産・特徴をFTS5＋ルール抽出し、
  Claude API（キー任意）で要約して `local_specialty` を埋める

---

## 既知のリスクと対策（2026-07-11 環境確認済み）

| リスク | 事実 | 対策 |
|---|---|---|
| PyTorch系ライブラリが入らない可能性 | 本環境のPythonは**3.14のみ**。sentence-transformers→PyTorchのWindows/3.14対応は不確実 | RAG検索はSQLite FTS5（依存ゼロ）をベースラインに変更済み。ベクトル検索はONNX系かCohere APIの任意オプション |
| OSRMデモサーバの不安定さ | レート制限あり・SLA無し | Haversine×1.3を既定とし、OSRMは候補ペアのみオンデマンド＋キャッシュ |
| Google Mapsディープリンクの経由地上限 | waypointsは最大9件 | 想定利用（1日4〜5駅）では到達しない。9駅超選択時はUIで警告 |
| `python`コマンドがStoreリダイレクトで失敗 | Windows既知問題（exit code 49） | venv作成後は `.venv/Scripts/python.exe` を使用。venv作成時のみ `%LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe` のようなフルパスを使う |
| アーカイブクローンのgit所有権警告 | 別管理の凍結スナップショットで所有者が異なる場合がある | 応募用コピーからは参照せず、必要なら安全な別作業場所で確認する |

確認済み環境: Node v24.14.1 / npm 11.11.0 / Python 3.14.3（他バージョンなし）
