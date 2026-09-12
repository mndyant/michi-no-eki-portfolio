# 道の駅CRUD API（ルーティング層。ロジックはapp/services/station_service.pyに委譲する薄い層）
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.station import Station
from app.schemas.station import StationCreate, StationRead, StationUpdate, StationVisitUpdate
from app.services import station_service

router = APIRouter(prefix="/api/stations", tags=["stations"])


def _get_station_or_404(db: Session, station_pk: int) -> Station:
    """idで道の駅を取得する。無ければ404エラーを日本語メッセージで返す"""
    station = station_service.get_station(db, station_pk)
    if station is None:
        raise HTTPException(status_code=404, detail=f"道の駅（id={station_pk}）が見つかりません")
    return station


@router.get("", response_model=list[StationRead])
def list_stations(
    pref: str | None = Query(default=None, description="府県名で絞り込み（例: 大阪府）"),
    visited: bool | None = Query(default=None, description="訪問済みかどうかで絞り込み"),
    cluster_id: int | None = Query(default=None, description="クラスタIDで絞り込み"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """道の駅一覧を取得する。pref・visited・cluster_idで絞り込み可能"""
    stations = station_service.list_stations(db, pref=pref, visited=visited, cluster_id=cluster_id)
    return [station_service.to_read_dict(s) for s in stations]


@router.get("/{station_pk}", response_model=StationRead)
def get_station(station_pk: int, db: Session = Depends(get_db)) -> dict:
    """道の駅の詳細を取得する"""
    station = _get_station_or_404(db, station_pk)
    return station_service.to_read_dict(station)


@router.post("", response_model=StationRead, status_code=201)
def create_station(payload: StationCreate, db: Session = Depends(get_db)) -> dict:
    """道の駅を新規登録する（基本CRUD確認用。通常はシード投入で足りる）"""
    if station_service.get_station_by_station_id(db, payload.station_id) is not None:
        raise HTTPException(
            status_code=400, detail=f"station_id={payload.station_id} は既に登録されています"
        )
    station = station_service.create_station(db, payload)
    return station_service.to_read_dict(station)


@router.put("/{station_pk}", response_model=StationRead)
def update_station(station_pk: int, payload: StationUpdate, db: Session = Depends(get_db)) -> dict:
    """道の駅の情報を更新する（滞在時間・メモ・営業時間の上書き等。渡された項目だけ更新）"""
    station = _get_station_or_404(db, station_pk)
    station = station_service.update_station(db, station, payload)
    return station_service.to_read_dict(station)


@router.delete("/{station_pk}", status_code=204)
def delete_station(station_pk: int, db: Session = Depends(get_db)) -> None:
    """道の駅を削除する"""
    station = _get_station_or_404(db, station_pk)
    station_service.delete_station(db, station)


@router.patch("/{station_pk}/visit", response_model=StationRead)
def update_visit_status(
    station_pk: int, payload: StationVisitUpdate, db: Session = Depends(get_db)
) -> dict:
    """訪問済みフラグを切り替え、訪問日を記録する"""
    station = _get_station_or_404(db, station_pk)
    station = station_service.set_visit_status(db, station, payload.visited, payload.visited_date)
    return station_service.to_read_dict(station)
