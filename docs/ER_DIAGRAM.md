# ER図・システム構成図

`backend/app/models/` の実際のSQLAlchemyモデル定義から起こしている。
データモデルの各カラムの意味・仮値の扱いは [DESIGN.md 5章](DESIGN.md#5-データモデルsqlite--sqlalchemy) を参照。

## ER図

```mermaid
erDiagram
    CLUSTERS ||--o{ STATIONS : "contains"
    STATIONS ||--o{ VISIT_RECORDS : "has"
    VISIT_RECORDS ||--o{ VISIT_PHOTOS : "has"
    STATIONS ||--o{ STATION_DISTANCES : "from_station_id"
    STATIONS ||--o{ STATION_DISTANCES : "to_station_id"
    STATIONS ||--o{ CHUNKS : "station_id（FK制約なし）"

    CLUSTERS {
        int id PK
        text name
        text description
    }
    STATIONS {
        int id PK
        string station_id UK "GML由来ID。例 P35_483"
        string name
        string pref
        string city
        string address
        float lat
        float lon
        string official_url
        text business_hours "JSON、曜日別"
        string stamp_start "HH:MM"
        string stamp_end "HH:MM"
        string closed_days
        bool visited
        date visited_date
        int stay_time_min_default
        string facility_scale "small/medium/large"
        bool good_for_lunch
        bool good_for_sweets
        bool good_for_souvenir
        bool has_spa
        int scenery_score "1-5、NULL可"
        bool is_mountainous
        int revisit_difficulty_score "1-5"
        text revisit_difficulty_reason
        int cluster_id FK
        text reputation_items "JSON配列"
        text local_specialty "JSON配列、Issue #51で抽出"
        text seasonal_specialty "JSON配列"
        text user_memo
        string source
        date last_verified_at
    }
    STATION_DISTANCES {
        int id PK
        int from_station_id FK
        int to_station_id FK
        float distance_km
        float duration_min
        string source "osrm/haversine"
        datetime updated_at
    }
    VISIT_RECORDS {
        int id PK
        int station_id FK
        date visit_date
        text purchased_items "JSON配列"
        text food "JSON配列"
        text impression
        string photo_url
        bool want_revisit
        text next_memo
    }
    VISIT_PHOTOS {
        int id PK
        int visit_record_id FK
        string file_name UK
        text tags "JSON配列"
    }
    CHUNKS {
        int id PK
        string station_id "stations.station_idに対応、FK制約なし"
        string chunk_type "basic/facilities/wikipedia"
        text content
    }
```

**補足:**
- `chunks` は `stations.station_id`（文字列）に対応するが、`load_chunks.py` と `seed.py` の
  実行順序に依存させないため、SQLAlchemyレベルでのFK制約は張っていない。
- `chunks_fts` はSQLite FTS5の仮想テーブル（`content='chunks', content_rowid='id'`）で、
  ER図には現れないが `chunks.content` の全文検索インデックスとして存在する
  （`app/db/session.py` の `create_fts_tables()` 参照）。トークナイザは日本語の分かち書き問題を
  避けるため3文字n-gramの `trigram` を使用（`app/services/rag/search.py`）。
- `routes` / `route_stops` テーブルは存在しない。ルートは保存せず、リクエストごとに
  `services/route/*` が動的に計算する設計（DESIGN.md 5章で構想されていたが未実装のまま確定）。

## システム構成図

```mermaid
flowchart LR
    subgraph Browser
        UI["Next.js App Router UI\n(stations / routes/new / routes/suggest)"]
    end

    subgraph Backend["FastAPI Backend"]
        API["API層 app/api/*\n(薄いルーティング)"]
        SVC_ROUTE["services/route\n(手動/自動ルート・What-if・時刻表)"]
        SVC_DIST["services/distance\n(haversine既定 / OSRM任意)"]
        SVC_AI["services/ai\n(自然文解釈・推薦理由・llm_provider)"]
        SVC_RAG["services/rag\n(FTS5検索・名産抽出)"]
    end

    DB[("SQLite\nstations/clusters/visit_records/\nvisit_photos/station_distances/chunks")]
    OSRM[["OSRM 公開デモ\n(任意・オフライン既定)"]]
    CLAUDE[["Anthropic Claude API\n(任意・キー無しでもルールベース動作)"]]
    GMAPS[["Google Maps\nディープリンクURL"]]

    UI -->|"REST/JSON"| API
    API --> SVC_ROUTE
    API --> SVC_AI
    API --> SVC_RAG
    SVC_ROUTE --> SVC_DIST
    SVC_ROUTE --> DB
    SVC_AI --> DB
    SVC_RAG --> DB
    SVC_DIST -.任意.-> OSRM
    SVC_AI -.任意.-> CLAUDE
    UI -->|"ルート確定後に遷移"| GMAPS
```

**設計方針（DESIGN.mdと同一）:** 外部連携（OSRM・Claude API）はすべて任意のプロバイダとして
抽象化され、未設定時はオフライン/ルールベースにフォールバックする。APIキーが1つも無くても
全機能が動作する。
