# RAG用チャンク（Wikipedia抜粋・基本情報・施設情報）。FTS5全文検索の元データ。
from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Chunk(Base):
    """data/processed/chunks.json（旧RAGフェーズで収集済み・460件）をそのまま投入する。

    station_idはstations.station_idに対応するが、厳密なFK制約は張らない
    （load_chunks.pyとseed.pyの実行順序に依存させないため）。
    """

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    chunk_type: Mapped[str] = mapped_column(String, nullable=False)  # basic / facilities / wikipedia
    content: Mapped[str] = mapped_column(Text, nullable=False)
