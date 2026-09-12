# 訪問記録に添付する写真（1記録に複数枚。タグでなんの写真かを記録する）
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.visit_record import VisitRecord


class VisitPhoto(Base):
    """訪問記録の写真。実ファイルは data/photos/ に置き、DBにはファイル名とタグを持つ"""

    __tablename__ = "visit_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    visit_record_id: Mapped[int] = mapped_column(
        ForeignKey("visit_records.id"), nullable=False, index=True
    )
    # data/photos/ 配下のファイル名（例: 12_a1b2c3.jpg）。URLは /photos/{file_name}
    file_name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    # なんの写真かを表すタグ（JSON配列文字列。例: ["名産品", "みかんジュース"]）
    tags: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    record: Mapped["VisitRecord"] = relationship(back_populates="photos")
