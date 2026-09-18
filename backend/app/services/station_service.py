# stations に対するDB操作をまとめたロジック層
# APIルーター（app/api/stations.py）からはこのモジュールの関数だけを呼び出し、
# SQLAlchemyのクエリ組み立てはここに閉じ込める
from __future__ import annotations

import json
from datetime import date

from sqlalchemy.orm import Session

from app.models.station import Station
from app.schemas.station import StationCreate, StationUpdate

# DB上はTEXT列（JSON文字列）で持っているが、API入出力ではdict/listとして扱う項目
JSON_FIELDS = ("business_hours", "reputation_items", "local_specialty", "seasonal_specialty")


def to_read_dict(station: Station) -> dict:
    """StationモデルをAPIレスポンス用dictに変換する（JSON文字列カラムをパースする）"""
    data = {column.name: getattr(station, column.name) for column in station.__table__.columns}
    for field in JSON_FIELDS:
        raw = data.get(field)
        if raw:
            data[field] = json.loads(raw)
        else:
            data[field] = {} if field == "business_hours" else []
    return data


def _dump_json_fields(data: dict) -> dict:
    """StationCreate/StationUpdateのdict/list項目をDB保存用のJSON文字列に変換する"""
    for field in JSON_FIELDS:
        if field in data and data[field] is not None:
            data[field] = json.dumps(data[field], ensure_ascii=False)
    return data


def list_stations(
    db: Session,
    pref: str | None = None,
    visited: bool | None = None,
    cluster_id: int | None = None,
) -> list[Station]:
    """道の駅一覧を取得する。pref/visited/cluster_idはNoneなら絞り込みしない"""
    query = db.query(Station)
    if pref is not None:
        query = query.filter(Station.pref == pref)
    if visited is not None:
        query = query.filter(Station.visited == visited)
    if cluster_id is not None:
        query = query.filter(Station.cluster_id == cluster_id)
    return query.order_by(Station.id).all()


def get_station(db: Session, station_pk: int) -> Station | None:
    """内部PK（id）で1件取得する。無ければNone"""
    return db.get(Station, station_pk)


def get_station_by_station_id(db: Session, station_id: str) -> Station | None:
    """GML由来のstation_id（例: P35_483）で1件取得する。無ければNone"""
    return db.query(Station).filter(Station.station_id == station_id).first()


def create_station(db: Session, payload: StationCreate) -> Station:
    """新規登録（基本CRUD確認用。通常はseed.pyでの投入で足りる）"""
    data = _dump_json_fields(payload.model_dump())
    station = Station(**data)
    db.add(station)
    db.commit()
    db.refresh(station)
    return station


def update_station(db: Session, station: Station, payload: StationUpdate) -> Station:
    """渡された項目だけを上書きする（滞在時間・メモ・営業時間の個別上書き等を想定）"""
    data = _dump_json_fields(payload.model_dump(exclude_unset=True))
    # 部分更新の必須列へのnullは変更なし。任意列のnullは削除として保持する。
    for column in Station.__table__.columns:
        if not column.nullable and data.get(column.name, ...) is None:
            data.pop(column.name)
    for key, value in data.items():
        setattr(station, key, value)
    db.commit()
    db.refresh(station)
    return station


def delete_station(db: Session, station: Station) -> None:
    db.delete(station)
    db.commit()


def set_visit_status(db: Session, station: Station, visited: bool, visited_date: date | None) -> Station:
    """訪問済みフラグと訪問日をまとめて更新する"""
    station.visited = visited
    station.visited_date = visited_date
    db.commit()
    db.refresh(station)
    return station
