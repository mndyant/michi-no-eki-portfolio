# 近隣クラスタ（半径15km程度の貪欲法でグルーピングした道の駅の集まり）
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    # 循環import回避のため型チェック時のみimportする
    from app.models.station import Station


class Cluster(Base):
    """近隣クラスタ（府県名+連番で仮登録。後で手動編集可能）"""

    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # このクラスタに属する道の駅一覧（逆参照）
    stations: Mapped[list["Station"]] = relationship(back_populates="cluster")
