# 道の駅マスタ（docs/DESIGN.md 5章参照）
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.cluster import Cluster
    from app.models.visit_record import VisitRecord


class Station(Base):
    """道の駅マスタ。GML由来の基本情報＋巡回計画用の仮値項目を持つ"""

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    # GML由来ID（例: P35_483）。既存収集データのキーをそのまま引き継ぐ
    station_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    pref: Mapped[str] = mapped_column(String, nullable=False, index=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    # 座標未取得の駅があるためNULL許容
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    official_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # 営業時間はJSON文字列で保存（例: {"mon": "09:00-17:00", ...}）。仮値は全曜日09:00-17:00
    business_hours: Mapped[str] = mapped_column(Text, nullable=False)
    stamp_start: Mapped[str] = mapped_column(String, nullable=False)  # "HH:MM"形式
    stamp_end: Mapped[str] = mapped_column(String, nullable=False)
    closed_days: Mapped[str] = mapped_column(String, nullable=False, default="")

    visited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visited_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    stay_time_min_default: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    # small / medium / large
    facility_scale: Mapped[str] = mapped_column(String, nullable=False)

    good_for_lunch: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    good_for_sweets: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    good_for_souvenir: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_spa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    scenery_score: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5、未評価はNULL
    is_mountainous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    revisit_difficulty_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    revisit_difficulty_reason: Mapped[str] = mapped_column(Text, nullable=False)

    cluster_id: Mapped[int | None] = mapped_column(ForeignKey("clusters.id"), nullable=True)
    cluster: Mapped["Cluster | None"] = relationship(back_populates="stations")

    # JSON配列文字列。初期値は空配列
    reputation_items: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    local_specialty: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    seasonal_specialty: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    user_memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    last_verified_at: Mapped[date] = mapped_column(Date, nullable=False)

    visit_records: Mapped[list["VisitRecord"]] = relationship(
        back_populates="station", cascade="all, delete-orphan"
    )
