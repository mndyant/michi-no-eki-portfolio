from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.station import Station
from app.models.station_distance import StationDistance
from app.services.distance.base import DistanceProvider, TravelEstimate


def normalize_station_pair(first_id: int, second_id: int) -> tuple[int, int]:
    """AB間とBA間を同じキャッシュ行として扱える順序にそろえる。"""
    return (first_id, second_id) if first_id < second_id else (second_id, first_id)


def get_station_travel(
    db: Session,
    from_station: Station,
    to_station: Station,
    provider: DistanceProvider,
) -> TravelEstimate:
    """駅間キャッシュを確認し、未登録の場合だけプロバイダを呼び出す。"""
    if from_station.id == to_station.id:
        return TravelEstimate(distance_km=0.0, duration_min=0.0, source="haversine")
    if from_station.lat is None or from_station.lon is None:
        raise ValueError("出発駅の座標がありません")
    if to_station.lat is None or to_station.lon is None:
        raise ValueError("到着駅の座標がありません")

    first_id, second_id = normalize_station_pair(from_station.id, to_station.id)
    cached = (
        db.query(StationDistance)
        .filter(
            StationDistance.from_station_id == first_id,
            StationDistance.to_station_id == second_id,
        )
        .first()
    )
    if cached is not None:
        return TravelEstimate(cached.distance_km, cached.duration_min, cached.source)

    estimate = provider.get_travel(
        from_station.lat, from_station.lon, to_station.lat, to_station.lon
    )
    db.add(
        StationDistance(
            from_station_id=first_id,
            to_station_id=second_id,
            distance_km=estimate.distance_km,
            duration_min=estimate.duration_min,
            source=estimate.source,
            updated_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    db.commit()
    return estimate
