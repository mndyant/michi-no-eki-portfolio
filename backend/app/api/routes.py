from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.route import (
    ManualRouteRequest,
    ManualRouteResponse,
    SuggestRouteRequest,
    SuggestRouteResponse,
    WhatIfRouteRequest,
    WhatIfRouteResponse,
)
from app.services.route.manual import (
    InvalidHighwayLegError,
    MissingCoordinatesError,
    StationsNotFoundError,
    calculate_manual_route,
)
from app.services.route.suggest import suggest_routes
from app.services.route.whatif import AllStationsExcludedError, calculate_what_if

router = APIRouter(prefix="/api/routes", tags=["routes"])


@router.post("/manual", response_model=ManualRouteResponse)
def create_manual_route(
    payload: ManualRouteRequest, db: Session = Depends(get_db)
) -> ManualRouteResponse:
    """指定された駅順を変えず、到着時刻・締切警告・地図URLを計算する。"""
    try:
        return calculate_manual_route(db, payload)
    except StationsNotFoundError as exc:
        ids = ", ".join(str(station_id) for station_id in exc.station_ids)
        raise HTTPException(
            status_code=404, detail=f"道の駅（id={ids}）が見つかりません"
        ) from exc
    except MissingCoordinatesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidHighwayLegError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/suggest", response_model=SuggestRouteResponse)
def create_suggested_routes(
    payload: SuggestRouteRequest, db: Session = Depends(get_db)
) -> SuggestRouteResponse:
    """条件に合う駅から、評価の重みを変えた複数プランを自動生成する。"""
    return suggest_routes(db, payload)


@router.post("/what-if", response_model=WhatIfRouteResponse)
def create_what_if_route(
    payload: WhatIfRouteRequest, db: Session = Depends(get_db)
) -> WhatIfRouteResponse:
    """遅延・駅除外・滞在変更を適用して再計算し、各駅の最遅出発時刻を返す。"""
    try:
        return calculate_what_if(db, payload)
    except AllStationsExcludedError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except InvalidHighwayLegError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StationsNotFoundError as exc:
        ids = ", ".join(str(station_id) for station_id in exc.station_ids)
        raise HTTPException(
            status_code=404, detail=f"道の駅（id={ids}）が見つかりません"
        ) from exc
    except MissingCoordinatesError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
