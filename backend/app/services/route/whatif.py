from __future__ import annotations

from datetime import datetime, timedelta
from math import ceil

from sqlalchemy.orm import Session

from app.schemas.route import (
    ManualRouteRequest,
    WhatIfRouteRequest,
    WhatIfRouteResponse,
    WhatIfStopRead,
)
from app.services.distance.base import DistanceProvider
from app.services.route.manual import compute_route
from app.services.route.planner import to_minutes
# 互換のため再エクスポート（実体はtimetable.pyへ移動。既存のimport元を壊さない）
from app.services.route.timetable import calculate_latest_departures  # noqa: F401

# What-ifシミュレーション（DESIGN.md 3章 フェーズ4）。
# 「出発が遅れたら」「この駅を飛ばしたら」を再計算し、
# 各駅の最遅出発時刻（何時までに出れば以降の締切に間に合うか）を逆算する。


class AllStationsExcludedError(ValueError):
    """除外指定によって訪問する駅が1件も残らない場合の業務エラー。"""


def shift_time(hhmm: str, delay_min: int) -> str:
    """"HH:MM" にdelay_min分を加算した時刻を返す（日をまたいでも時刻表記のまま）。"""
    shifted = datetime.strptime(hhmm, "%H:%M") + timedelta(minutes=delay_min)
    return shifted.strftime("%H:%M")


def _format_minutes(total_min: int) -> str:
    """0時からの分数を "HH:MM" にする（日またぎは24時間表記に折り返す）。"""
    return f"{(total_min // 60) % 24:02d}:{total_min % 60:02d}"


def calculate_what_if(
    db: Session,
    payload: WhatIfRouteRequest,
    provider: DistanceProvider | None = None,
) -> WhatIfRouteResponse:
    """遅延・駅除外を適用して再計算し、各駅の最遅出発時刻を付けて返す。"""
    excluded = set(payload.excluded_station_ids)
    effective_ids = [sid for sid in payload.station_ids if sid not in excluded]
    if not effective_ids:
        raise AllStationsExcludedError("すべての駅が除外されています")

    computation = compute_route(
        db,
        ManualRouteRequest(
            origin=payload.origin,
            # What-ifは常に確定した出発時刻からの再計算（逆算モードはmanual側の機能）
            departure_mode="fixed",
            departure_time=shift_time(payload.departure_time, payload.delay_min),
            station_ids=effective_ids,
            stay_overrides=payload.stay_overrides,
            return_to_origin=payload.return_to_origin,
            # 注意: 区間インデックスは除外適用後のルートに対するもの
            highway_legs=payload.highway_legs,
            visit_date=payload.visit_date,
        ),
        provider,
    )
    base = computation.response

    return_travel_min = (
        ceil(computation.return_estimate.duration_min)
        if computation.return_estimate is not None
        else None
    )
    latest_departures = calculate_latest_departures(
        deadlines_min=[to_minutes(stop.stamp_deadline) for stop in computation.timetable],
        stays_min=[stop.stay_min for stop in computation.timetable],
        travels_min=[ceil(item.duration_min) for item in computation.estimates],
        return_travel_min=return_travel_min,
        return_by_min=to_minutes(payload.return_by) if payload.return_by else None,
    )

    stops: list[WhatIfStopRead] = []
    for stop, latest_min in zip(base.stops, latest_departures, strict=True):
        slack = latest_min - to_minutes(stop.departure) if latest_min is not None else None
        stops.append(
            WhatIfStopRead(
                **stop.model_dump(),
                latest_departure=_format_minutes(latest_min) if latest_min is not None else None,
                departure_slack_min=slack,
            )
        )

    warnings = list(base.warnings)
    # 帰着締切チェック: 最終駅出発（＋帰路）の時刻が締切を超えたら警告する
    if payload.return_by is not None and stops:
        finish_min = to_minutes(stops[-1].departure) + (return_travel_min or 0)
        if finish_min > to_minutes(payload.return_by):
            warnings.append("return_deadline_missed")

    return WhatIfRouteResponse(
        stops=stops,
        totals=base.totals,
        google_maps_url=base.google_maps_url,
        warnings=warnings,
        applied_delay_min=payload.delay_min,
        excluded_station_ids=sorted(excluded & set(payload.station_ids)),
    )
