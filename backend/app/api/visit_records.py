from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.station import Station
from app.models.visit_record import VisitRecord
from app.schemas.visit_record import VisitRecordCreate, VisitRecordRead, VisitRecordUpdate

# 訪問記録API（DESIGN.md 13-3章）。
# 駅にぶら下がる一覧・作成は /api/stations/{id}/visit-records、
# 個別の更新・削除は /api/visit-records/{id} で受ける
router = APIRouter(prefix="/api", tags=["visit-records"])


def _to_read(record: VisitRecord) -> VisitRecordRead:
    """DBモデル（JSON文字列）をAPIスキーマ（文字列配列）に変換する。"""
    from app.api.photos import _to_read as photo_to_read

    return VisitRecordRead(
        id=record.id,
        station_id=record.station_id,
        visit_date=record.visit_date,
        purchased_items=json.loads(record.purchased_items),
        food=json.loads(record.food),
        impression=record.impression,
        photo_url=record.photo_url,
        want_revisit=record.want_revisit,
        next_memo=record.next_memo,
        photos=[photo_to_read(photo) for photo in sorted(record.photos, key=lambda p: p.id)],
    )


def _get_station(db: Session, station_id: int) -> Station:
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail=f"道の駅（id={station_id}）が見つかりません")
    return station


def _get_record(db: Session, record_id: int) -> VisitRecord:
    record = db.get(VisitRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"訪問記録（id={record_id}）が見つかりません")
    return record


@router.get("/stations/{station_id}/visit-records", response_model=list[VisitRecordRead])
def list_visit_records(station_id: int, db: Session = Depends(get_db)) -> list[VisitRecordRead]:
    """指定した道の駅の訪問記録を新しい順に返す。"""
    _get_station(db, station_id)
    records = (
        db.query(VisitRecord)
        .filter(VisitRecord.station_id == station_id)
        .order_by(VisitRecord.visit_date.desc(), VisitRecord.id.desc())
        .all()
    )
    return [_to_read(record) for record in records]


@router.post(
    "/stations/{station_id}/visit-records",
    response_model=VisitRecordRead,
    status_code=201,
)
def create_visit_record(
    station_id: int, payload: VisitRecordCreate, db: Session = Depends(get_db)
) -> VisitRecordRead:
    """訪問記録を作成する。記録した駅は訪問済みに自動更新される（13-3章）。"""
    station = _get_station(db, station_id)
    record = VisitRecord(
        station_id=station_id,
        visit_date=payload.visit_date,
        purchased_items=json.dumps(payload.purchased_items, ensure_ascii=False),
        food=json.dumps(payload.food, ensure_ascii=False),
        impression=payload.impression,
        photo_url=payload.photo_url,
        want_revisit=payload.want_revisit,
        next_memo=payload.next_memo,
    )
    db.add(record)
    # 記録があるのに未訪問はあり得ないため自動で訪問済みにする（手動切替も従来どおり可能）
    station.visited = True
    if station.visited_date is None or station.visited_date < payload.visit_date:
        station.visited_date = payload.visit_date
    db.commit()
    db.refresh(record)
    return _to_read(record)


@router.put("/visit-records/{record_id}", response_model=VisitRecordRead)
def update_visit_record(
    record_id: int, payload: VisitRecordUpdate, db: Session = Depends(get_db)
) -> VisitRecordRead:
    """訪問記録を部分更新する（渡されたフィールドのみ上書き）。"""
    record = _get_record(db, record_id)
    data = payload.model_dump(exclude_unset=True)
    if "purchased_items" in data and data["purchased_items"] is not None:
        record.purchased_items = json.dumps(data.pop("purchased_items"), ensure_ascii=False)
    if "food" in data and data["food"] is not None:
        record.food = json.dumps(data.pop("food"), ensure_ascii=False)
    for field, value in data.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return _to_read(record)


@router.delete("/visit-records/{record_id}", status_code=204)
def delete_visit_record(record_id: int, db: Session = Depends(get_db)) -> None:
    """訪問記録を削除する。訪問済みフラグは変更しない（手動で管理）。"""
    record = _get_record(db, record_id)
    db.delete(record)
    db.commit()
