# chunks投入スクリプト
# data/processed/chunks.json（旧RAGフェーズで収集済み・460件）をchunksテーブル＋
# chunks_fts（FTS5全文検索テーブル）へ投入する。
#
# 注意: GML未収録駅（新規登録駅）のchunkを駅名でstationsテーブルと突き合わせるため、
# 先に scripts/seed.py を実行して stations テーブルにデータを入れておくこと。
#
# 実行方法（backend/ ディレクトリで、seed.py実行後）:
#   .venv/Scripts/python.exe scripts/load_chunks.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402,F401  モデルをBase.metadataに登録するために必要
from app.db.session import Base, SessionLocal, create_fts_tables, engine  # noqa: E402
from app.models.chunk import Chunk  # noqa: E402
from app.models.station import Station  # noqa: E402

# このスクリプトは backend/scripts/ にあるので、2階層上（リポジトリルート）から
# data/processed/chunks.json を参照する
CHUNKS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "chunks.json"


def main() -> None:
    Base.metadata.create_all(bind=engine)
    create_fts_tables(engine)

    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks_data = json.load(f)

    db = SessionLocal()
    try:
        # 冪等にするため、既存のchunks/chunks_ftsを全削除してから入れ直す
        db.execute(text("DELETE FROM chunks_fts"))
        db.query(Chunk).delete()
        db.commit()

        # chunks.jsonにはGML未収録駅（新規登録駅、約16件）のchunkでstation_idがNoneのものが
        # 混じっている。これらはseed_transform.pyがNOID_xxxという仮IDを振っているため、
        # 駅名で突き合わせて仮IDへ差し替える（駅名は159駅で重複が無いことを確認済み）。
        name_to_station_id = {s.name: s.station_id for s in db.query(Station).all()}

        chunks = []
        skipped = 0
        for c in chunks_data:
            station_id = c["station_id"] or name_to_station_id.get(c["name"])
            if not station_id:
                skipped += 1
                continue
            chunks.append(Chunk(station_id=station_id, chunk_type=c["chunk_type"], content=c["content"]))
        db.add_all(chunks)
        db.commit()
        if skipped:
            print(f"station_idを特定できず投入をスキップしたchunk: {skipped}件")

        # chunks_ftsのrowidをchunks.idに合わせて投入する（session.pyのcontent_rowid設定と対応）
        for chunk in chunks:
            db.execute(
                text("INSERT INTO chunks_fts(rowid, content) VALUES (:id, :content)"),
                {"id": chunk.id, "content": chunk.content},
            )
        db.commit()

        print(f"chunks投入完了: {len(chunks)}件（chunks_fts含む）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
