# 名産・特徴の一括抽出スクリプト
# chunksテーブル（load_chunks.py投入済み前提）から駅ごとに名産候補をルールベース抽出し、
# stations.local_specialty（JSON配列文字列）へ書き込む。候補が無い駅はそのまま"[]"（未変更）。
#
# 実行方法（backend/ ディレクトリで、load_chunks.py実行後）:
#   .venv/Scripts/python.exe scripts/extract_specialties.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import SessionLocal  # noqa: E402
from app.models.chunk import Chunk  # noqa: E402
from app.models.station import Station  # noqa: E402
from app.services.rag.specialty_extractor import extract_specialty_candidates  # noqa: E402


def main() -> None:
    db = SessionLocal()
    try:
        stations = db.query(Station).all()
        updated = 0
        for station in stations:
            contents = [
                c.content
                for c in db.query(Chunk).filter(Chunk.station_id == station.station_id).all()
            ]
            candidates = extract_specialty_candidates(contents)
            if candidates:
                station.local_specialty = json.dumps(candidates, ensure_ascii=False)
                updated += 1
        db.commit()
        print(f"local_specialty更新: {updated}/{len(stations)}駅（候補が見つかった駅のみ更新）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
