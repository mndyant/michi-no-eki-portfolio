# シード投入スクリプト
# data/raw/stations_kinki.json（リポジトリルート直下、159件）を
# app/services/seed_transform.py の変換ロジックで加工し、stations / clusters テーブルへ投入する。
#
# 実行方法（backend/ ディレクトリで）:
#   .venv/Scripts/python.exe scripts/seed.py
#
# 何度実行しても安全なupsert方式（Issue #82）:
#   GML由来IDの駅はstation_id一致のみ、NOID_駅（駅名由来の安定ハッシュID）はname一致のみで
#   既存駅を照合し（詳細はapp/services/seed_service.py）、シード由来フィールドのみ上書きする。
#   visited/visited_date/stay_time_min_default/reputation_items/訪問記録などのユーザーデータは
#   一切削除・上書きしない（実処理は app/services/seed_service.py に切り出し済み）。
#   実行前にdata.dbが存在すればdata.db.bakへ自動バックアップする。
import collections
import json
import shutil
import sys
from pathlib import Path

# backend/ をモジュール検索パスに追加し、"app" パッケージをimportできるようにする
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

# リポジトリルート直下の data/raw/stations_kinki.json を参照する
REPO_ROOT = BACKEND_DIR.parent
STATIONS_JSON_PATH = REPO_ROOT / "data" / "raw" / "stations_kinki.json"

from app.db.session import Base, DB_PATH, SessionLocal, engine  # noqa: E402
from app import models  # noqa: E402,F401  Base.metadataへのモデル登録に必要
from app.services.seed_service import SeedMatchConflictError, run_seed  # noqa: E402
from app.services.seed_transform import transform_stations  # noqa: E402


def load_raw_stations() -> list[dict]:
    """data/raw/stations_kinki.json を読み込む"""
    with STATIONS_JSON_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def backup_db_if_exists() -> None:
    """再シードでユーザーデータを壊す事故に備え、実行前にdata.dbをバックアップする（Issue #82）。
    上書きコピーなので、実行するたびに直前の状態がdata.db.bakに残る（1世代のみ保持）。
    """
    if DB_PATH.exists():
        backup_path = DB_PATH.with_name(DB_PATH.name + ".bak")
        shutil.copy2(DB_PATH, backup_path)
        print(f"既存DBをバックアップしました: {backup_path}")


def main() -> None:
    backup_db_if_exists()

    # テーブルが無い場合に備えて作成しておく（Issue #3のinit_db.pyと同じ処理）
    Base.metadata.create_all(bind=engine)

    raw_stations = load_raw_stations()
    print(f"読み込んだ生データ件数: {len(raw_stations)}")

    station_rows, cluster_rows = transform_stations(raw_stations)

    db = SessionLocal()
    try:
        result = run_seed(db, station_rows, cluster_rows)
    except SeedMatchConflictError as exc:
        # 対応関係が一意に決まらない場合はfail-fastし、更新は一切コミットしない
        # （db.commit()前に例外が飛ぶので、db.close()でトランザクションは破棄される）
        print("エラー: シード投入を中断しました。DBへの変更はコミットされていません。")
        print(str(exc))
        sys.exit(1)
    finally:
        db.close()

    print(f"新規投入: {len(result.inserted)}件 / 更新: {len(result.updated)}件")
    if result.distance_cache_invalidated:
        print(
            f"座標変更に伴い駅間距離キャッシュを{result.distance_cache_invalidated}行失効させました"
        )
    if result.missing_in_seed:
        print(
            f"警告: シードデータに存在しないがDBに残っている駅が{len(result.missing_in_seed)}件"
            "あります（削除はしていません）:"
        )
        for station_id in result.missing_in_seed:
            print(f"  - {station_id}")

    # 府県別の内訳を表示（検証用）
    pref_counts = collections.Counter(row["pref"] for row in station_rows)
    print("府県別内訳（シードデータ側）:")
    for pref, count in sorted(pref_counts.items()):
        print(f"  {pref}: {count}件")


if __name__ == "__main__":
    main()
