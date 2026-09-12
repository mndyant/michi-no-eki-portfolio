# クラスタ一覧API（ルーティング層）
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.cluster import ClusterRead
from app.services import cluster_service

router = APIRouter(prefix="/api/clusters", tags=["clusters"])


@router.get("", response_model=list[ClusterRead])
def list_clusters(db: Session = Depends(get_db)) -> list:
    """クラスタ一覧を取得する"""
    return cluster_service.list_clusters(db)
