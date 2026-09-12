# 訪問記録（購入品・食事・感想などのログ。1駅に複数回分の記録が積み重なる想定）
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.station import Station
    from app.models.visit_photo import VisitPhoto


class VisitRecord(Base):
    """訪問記録"""

    __tablename__ = "visit_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"), nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    purchased_items: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON配列
    food: Mapped[str] = mapped_column(Text, nullable=False, default="[]")  # JSON配列
    impression: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    want_revisit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    next_memo: Mapped[str | None] = mapped_column(Text, nullable=True)

    station: Mapped["Station"] = relationship(back_populates="visit_records")
    photos: Mapped[list["VisitPhoto"]] = relationship(
        back_populates="record", cascade="all, delete-orphan"
    )
