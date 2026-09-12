from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from math import ceil

from sqlalchemy.orm import Session

from app.models.station import Station
from app.schemas.route import ManualRouteRequest, ManualRouteResponse, RouteStopRead, RouteTotals
from app.services.distance.base import DistanceProvider, TravelEstimate
from app.services.distance.cache import get_station_travel
from app.services.distance.factory import get_distance_provider
from app.services.route.auto_order import OrderableStation, auto_order_stations
from app.services.route.business_hours import is_closed_day, resolve_open_time, weekday_code
from app.services.route.gmaps import MapPoint, build_google_maps_url
from app.services.route.mountain_factor import apply_mountain_correction
from app.services.route.planner import to_minutes
from app.services.route.timetable import (
    TimetableOrigin,
    TimetableStation,
    TimetableStop,
    calculate_origin_latest_departure,
    calculate_timetable,
)


# 高速道路を使う区間の所要時間係数（DESIGN.md 13-1章）。
# 既定の下道見積り（時速40km換算）に対し 0.55倍 ≒ 実効時速73km相当。距離は変えない
HIGHWAY_DURATION_FACTOR = 0.55


class StationsNotFoundError(ValueError):
    def __init__(self, station_ids: list[int]) -> None:
        self.station_ids = station_ids
        super().__init__(f"道の駅（id={station_ids}）が見つかりません")


class MissingCoordinatesError(ValueError):
    """訪問対象に座標未取得の駅が含まれる場合の業務エラー。"""


class InvalidHighwayLegError(ValueError):
    """highway_legs に存在しない区間インデックスが含まれる場合の業務エラー。"""


def _as_highway(estimate: TravelEstimate) -> TravelEstimate:
    """1区間分の見積りを高速道路利用の所要時間に置き換える。"""
    return TravelEstimate(
        distance_km=estimate.distance_km,
        duration_min=estimate.duration_min * HIGHWAY_DURATION_FACTOR,
        source=f"{estimate.source}+highway",
    )


def _apply_highway_legs(
    estimates: list[TravelEstimate],
    return_estimate: TravelEstimate | None,
    highway_legs: list[int],
) -> tuple[list[TravelEstimate], TravelEstimate | None]:
    """指定された区間インデックスに高速係数を適用する。

    区間インデックス: 0 = 出発地→1駅目、i = i駅目→i+1駅目、駅数 = 帰路（帰着ありのみ）。
    """
    legs = set(highway_legs)
    max_leg = len(estimates) - 1 + (1 if return_estimate is not None else 0)
    invalid = sorted(leg for leg in legs if leg < 0 or leg > max_leg)
    if invalid:
        raise InvalidHighwayLegError(
            f"存在しない区間インデックスが指定されています: {invalid}（有効範囲: 0〜{max_leg}）"
        )
    adjusted = [
        _as_highway(estimate) if index in legs else estimate
        for index, estimate in enumerate(estimates)
    ]
    adjusted_return = return_estimate
    if return_estimate is not None and len(estimates) in legs:
        adjusted_return = _as_highway(return_estimate)
    return adjusted, adjusted_return


def _auto_order_stations(
    payload: ManualRouteRequest,
    stations: list[Station],
    provider: DistanceProvider,
) -> list[Station]:
    """auto_order=Trueの場合に、出発地から最近傍法+2-optで訪問順を並べ替える（Issue #78）。

    ユーザーが選んだ駅は1件も間引かず、順序だけを変える。同じ2点間の所要時間を
    2-optの反復中に何度も問い合わせるため、リクエスト内だけで使い捨てるキャッシュを持つ。
    """
    # 最終計算（_get_estimates）と同じコストで最適化するため、山間駅が絡む区間には
    # 同じ道路係数補正（Issue #73）をかける。補正なしの生値で最適化すると、
    # 「最適」と判定した順序が最終的な所要時間では最短でないズレが生じる
    mountainous_coords = {
        (station.lat, station.lon) for station in stations if station.is_mountainous
    }
    travel_cache: dict[tuple[float, float, float, float], float] = {}

    def travel_min_fn(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
        key = (from_lat, from_lon, to_lat, to_lon)
        if key not in travel_cache:
            estimate = provider.get_travel(from_lat, from_lon, to_lat, to_lon)
            is_mountainous = (
                (from_lat, from_lon) in mountainous_coords
                or (to_lat, to_lon) in mountainous_coords
            )
            travel_cache[key] = apply_mountain_correction(estimate, is_mountainous).duration_min
        return travel_cache[key]

    orderable = [OrderableStation(station.id, station.lat, station.lon) for station in stations]
    ordered = auto_order_stations(
        payload.origin.lat,
        payload.origin.lon,
        orderable,
        travel_min_fn,
        payload.return_to_origin,
    )
    by_id = {station.id: station for station in stations}
    return [by_id[item.station_id] for item in ordered]


def _load_stations(db: Session, station_ids: list[int]) -> list[Station]:
    found = db.query(Station).filter(Station.id.in_(set(station_ids))).all()
    by_id = {station.id: station for station in found}
    missing = sorted(set(station_ids) - by_id.keys())
    if missing:
        raise StationsNotFoundError(missing)
    stations = [by_id[station_id] for station_id in station_ids]
    if any(station.lat is None or station.lon is None for station in stations):
        raise MissingCoordinatesError("座標未取得の駅が含まれています")
    return stations


def _get_estimates(
    db: Session,
    payload: ManualRouteRequest,
    stations: list[Station],
    provider: DistanceProvider,
) -> tuple[list[TravelEstimate], TravelEstimate | None]:
    """各区間の距離・所要時間を取得する。山間駅が絡む区間は道路係数を1.6相当に補正する（Issue #73）。"""
    first = stations[0]
    first_estimate = provider.get_travel(payload.origin.lat, payload.origin.lon, first.lat, first.lon)
    estimates = [apply_mountain_correction(first_estimate, first.is_mountainous)]
    estimates.extend(
        apply_mountain_correction(
            get_station_travel(db, previous, current, provider),
            previous.is_mountainous or current.is_mountainous,
        )
        for previous, current in zip(stations, stations[1:])
    )
    return_estimate = None
    if payload.return_to_origin:
        last = stations[-1]
        raw_return = provider.get_travel(
            last.lat, last.lon, payload.origin.lat, payload.origin.lon
        )
        return_estimate = apply_mountain_correction(raw_return, last.is_mountainous)
    return estimates, return_estimate


@dataclass(frozen=True, slots=True)
class RouteComputation:
    """手動ルート計算の結果一式。What-if等の派生計算が中間値を再利用できるように持つ。"""

    response: ManualRouteResponse
    estimates: list[TravelEstimate]  # 出発地→駅0、駅0→駅1、…（駅数と同数）
    return_estimate: TravelEstimate | None  # 最終駅→出発地（帰着ありのみ）
    timetable: list[TimetableStop]


def compute_route(
    db: Session,
    payload: ManualRouteRequest,
    provider: DistanceProvider | None = None,
) -> RouteComputation:
    """DB取得・距離取得・純粋な時刻計算を組み合わせ、中間値ごと返す。"""
    stations = _load_stations(db, payload.station_ids)
    actual_provider = provider or get_distance_provider()
    if payload.auto_order:
        stations = _auto_order_stations(payload, stations, actual_provider)
    estimates, return_estimate = _get_estimates(db, payload, stations, actual_provider)
    estimates, return_estimate = _apply_highway_legs(
        estimates, return_estimate, payload.highway_legs
    )
    # 訪問日が指定されていれば曜日を特定し、曜日別営業時間・定休日を制約に反映する（Issue #71）。
    # 未指定時はNone/Falseのまま＝従来通り曜日を考慮しない（後方互換）
    weekday = weekday_code(date.fromisoformat(payload.visit_date)) if payload.visit_date else None
    timetable_stations = [
        TimetableStation(
            station.id, station.name, station.lat, station.lon, station.stamp_end,
            payload.stay_overrides.get(station.id, station.stay_time_min_default),
            open_time=resolve_open_time(station.business_hours, weekday) if weekday else None,
            is_closed_day=is_closed_day(station.closed_days, weekday) if weekday else False,
        )
        for station in stations
    ]
    # 逆算モード: 締切（と帰着締切）に間に合う最も遅い出発時刻を計算して使う（Issue #46）
    extra_warnings: list[str] = []
    if payload.departure_mode == "latest":
        origin_latest = calculate_origin_latest_departure(
            deadlines_min=[to_minutes(station.stamp_deadline) for station in timetable_stations],
            stays_min=[station.stay_min for station in timetable_stations],
            travels_min=[ceil(item.duration_min) for item in estimates],
            return_travel_min=(
                ceil(return_estimate.duration_min) if return_estimate is not None else None
            ),
            return_by_min=to_minutes(payload.return_by) if payload.return_by else None,
        )
        if origin_latest < 0:
            # 0時に出ても間に合わない組み合わせ。0:00開始で計算し、各駅の警告に委ねる
            origin_latest = 0
            extra_warnings.append("no_feasible_departure")
        departure_time = f"{origin_latest // 60:02d}:{origin_latest % 60:02d}"
    else:
        departure_time = payload.departure_time
    timetable = calculate_timetable(
        TimetableOrigin(payload.origin.lat, payload.origin.lon),
        departure_time,
        timetable_stations,
        [item.duration_min for item in estimates],
    )
    origin = MapPoint(payload.origin.lat, payload.origin.lon, payload.origin.label)
    points = [MapPoint(station.lat, station.lon, station.name) for station in stations]
    maps_url, warnings = build_google_maps_url(origin, points, payload.return_to_origin)
    all_estimates = estimates + ([return_estimate] if return_estimate is not None else [])
    response = ManualRouteResponse(
        stops=[RouteStopRead(**asdict(stop)) for stop in timetable],
        totals=RouteTotals(
            travel_min=sum(ceil(item.duration_min) for item in all_estimates),
            distance_km=round(sum(item.distance_km for item in all_estimates), 2),
            stay_min=sum(stop.stay_min for stop in timetable),
        ),
        google_maps_url=maps_url,
        warnings=warnings + extra_warnings,
        departure_time=departure_time,
    )
    return RouteComputation(
        response=response,
        estimates=estimates,
        return_estimate=return_estimate,
        timetable=timetable,
    )


def calculate_manual_route(
    db: Session,
    payload: ManualRouteRequest,
    provider: DistanceProvider | None = None,
) -> ManualRouteResponse:
    """DB取得・距離取得・純粋な時刻計算を組み合わせて手動ルートを作る。"""
    return compute_route(db, payload, provider).response
