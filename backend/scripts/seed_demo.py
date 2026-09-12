"""自作の架空8駅を空のDBへ投入する。既存の駅があるDBには書き込まない。"""
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app import models  # noqa: F401,E402
from app.db.session import Base, SessionLocal, engine, create_fts_tables  # noqa: E402
from app.models.station import Station  # noqa: E402
from app.services.seed_service import run_seed  # noqa: E402
from app.services.seed_transform import transform_stations  # noqa: E402


def demo_rows():
    """駅名・施設・座標は動作確認用の創作。実施設の情報ではない。"""
    names = ["デモ青空広場", "デモ川辺市場", "デモ木陰テラス", "デモ山の茶屋",
             "デモ夕日広場", "デモ若葉市場", "デモ渓谷テラス", "デモ星空広場"]
    raw = [dict(station_id=f"DEMO_{i+1:02}", name=name, pref="大阪府" if i < 4 else "京都府",
                address="架空の施設・案内には使用不可", lat=34.75+i*0.04, lon=135.50+(i%3)*0.05,
                facilities=dict(restaurant=i%2 == 0, coffee_shop=i%3 == 0, shop=True))
           for i, name in enumerate(names)]
    rows, clusters = transform_stations(raw)
    for row in rows:
        row["source"] = "自作の架空データ（施設・位置・営業時間は実在情報ではありません）"
        row["last_verified_at"] = date(2026, 9, 12)
    return rows, clusters


def main():
    Base.metadata.create_all(engine)
    create_fts_tables(engine)
    with SessionLocal() as db:
        if db.scalar(select(Station.id).limit(1)) is not None:
            raise SystemExit("駅が存在するDBには投入しません。MICHI_DB_PATHで新しいDBを指定してください。")
        rows, clusters = demo_rows()
        run_seed(db, rows, clusters)
        db.commit()
    print("架空デモ8駅を投入しました。実際の旅行案内には使用できません。")


if __name__ == "__main__":
    main()
