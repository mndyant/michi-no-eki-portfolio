# 駅間移動時間キャッシュ
# OSRM等の移動時間API呼び出し回数を抑えるためのキャッシュテーブル。
# 対称な関係（AB間とBA間は同じ）なので from_station_id < to_station_id に正規化して1行のみ保持する
# （正規化のルール自体はservices層で実装し、モデル側では制約しない）
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class StationDistance(Base):
    """駅間の距離・移動時間キャッシュ"""

    __tablename__ = "station_distances"
    __table_args__ = (
        UniqueConstraint("from_station_id", "to_station_id", name="uq_station_distance_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    from_station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    to_station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    duration_min: Mapped[float] = mapped_column(Float, nullable=False)
    # "osrm" or "haversine"
    source: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
