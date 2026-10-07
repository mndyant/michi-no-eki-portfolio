"""Public demo: Osaka data + original route services, with no durable writes."""
from datetime import date
import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import Field, model_validator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
import app.models  # noqa: F401: register relationships before creating tables
from app.api import clusters, routes
from app.schemas.route import ManualRouteRequest, ManualRouteResponse, SuggestRouteRequest, SuggestRouteResponse, WhatIfRouteRequest, WhatIfRouteResponse
from app.schemas.station import StationRead
from app.services.seed_transform import transform_stations
from app.services.seed_service import run_seed
from app.services import station_service

# This deployment deliberately uses deterministic estimates, never a routing API.
os.environ["DISTANCE_PROVIDER"] = "haversine"
ROOT = Path(__file__).resolve().parents[2]
RAW = json.loads((ROOT / "data/demo/stations_osaka.json").read_text(encoding="utf-8"))
STATION_ROWS, CLUSTER_ROWS = transform_stations(RAW)
for row in STATION_ROWS:
    row["source"] = "作成者提供の簡易JSONから大阪府のみ抽出。営業時間・スコアはデモ用仮値"


def demo_db():
    # Route services write a distance cache; a separate in-memory DB per request
    # preserves that behavior without shared state or serverless filesystem writes.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            run_seed(db, STATION_ROWS, CLUSTER_ROWS)
            yield db
    finally:
        engine.dispose()


class DemoStation(StationRead):
    last_verified_at: date | None = None


def read_station(station):
    data = station_service.to_read_dict(station)
    # The seed transform's legacy date is not evidence of current verification.
    data["last_verified_at"] = None
    return data


def validate_plan(payload):
    if len(payload.station_ids) > 10 or len(set(payload.station_ids)) != len(payload.station_ids):
        raise ValueError("道の駅は重複なしで10駅以内を指定してください")
    if len(payload.stay_overrides) > 10 or any(v > 480 for v in payload.stay_overrides.values()):
        raise ValueError("滞在時間は各駅0〜480分、10駅以内で指定してください")
    if len(payload.highway_legs) > 11:
        raise ValueError("区間は11件以内で指定してください")
    return payload


class DemoManual(ManualRouteRequest):
    @model_validator(mode="after")
    def bounded(self):
        return validate_plan(self)


class DemoWhatIf(WhatIfRouteRequest):
    @model_validator(mode="after")
    def bounded(self):
        if len(self.excluded_station_ids) > 10:
            raise ValueError("除外駅は10駅以内で指定してください")
        return validate_plan(self)


class DemoSuggest(SuggestRouteRequest):
    free_text: str | None = Field(default=None, max_length=500)


app = FastAPI(title="大阪 道の駅巡回計画 — 公開デモ", docs_url=None, redoc_url=None, openapi_url=None)
app.dependency_overrides[get_db] = demo_db


@app.middleware("http")
async def public_boundary(request: Request, call_next):
    # Count streamed bytes as well as Content-Length, before JSON parsing.
    if request.method == "POST":
        size = 0
        chunks = []
        async for chunk in request.stream():
            size += len(chunk)
            if size > 16_384:
                return JSONResponse({"detail": "入力は16KB以内にしてください"}, status_code=413)
            chunks.append(chunk)
        request._body = b"".join(chunks)
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


DB = Annotated[Session, Depends(get_db)]


@app.get("/api/stations", response_model=list[DemoStation])
def stations_list(db: DB):
    return [read_station(s) for s in station_service.list_stations(db)]


@app.get("/api/stations/{station_id}", response_model=DemoStation)
def station_detail(station_id: int, db: DB):
    station = station_service.get_station(db, station_id)
    if station is None:
        raise HTTPException(404, "道の駅が見つかりません")
    return read_station(station)


@app.post("/api/routes/manual", response_model=ManualRouteResponse)
def manual(payload: DemoManual, db: DB):
    return routes.create_manual_route(payload, db)


@app.post("/api/routes/what-if", response_model=WhatIfRouteResponse)
def what_if(payload: DemoWhatIf, db: DB):
    return routes.create_what_if_route(payload, db)


@app.post("/api/routes/suggest", response_model=SuggestRouteResponse)
def suggest(payload: DemoSuggest, db: DB):
    return routes.create_suggested_routes(payload, db)


app.include_router(clusters.router)

# Vercel discovers StaticFiles mounts after the build and promotes them to CDN.
# API-only tests also work before the frontend has been built.
from fastapi.staticfiles import StaticFiles
if (ROOT / "site").is_dir():
    app.mount("/", StaticFiles(directory=ROOT / "site", html=True), name="frontend")
