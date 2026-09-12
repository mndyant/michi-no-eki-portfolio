# clusters に対するDB操作をまとめたロジック層
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.cluster import Cluster


def list_clusters(db: Session) -> list[Cluster]:
    """クラスタ一覧を取得する"""
    return db.query(Cluster).order_by(Cluster.id).all()
