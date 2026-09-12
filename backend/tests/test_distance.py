from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import app.models  # noqa: E402,F401  SQLAlchemyへ全モデルを登録する
from app.db.session import Base  # noqa: E402
from app.models.station import Station  # noqa: E402
from app.models.station_distance import StationDistance  # noqa: E402
from app.services.distance.base import DistanceProvider, TravelEstimate  # noqa: E402
from app.services.distance.cache import get_station_travel  # noqa: E402
from app.services.distance.factory import get_distance_provider  # noqa: E402
from app.services.distance.haversine_provider import HaversineProvider  # noqa: E402
from app.services.distance.osrm_provider import OSRMProvider  # noqa: E402


class CountingProvider(DistanceProvider):
    def __init__(self) -> None:
        self.calls = 0

    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        self.calls += 1
        return TravelEstimate(distance_km=12.5, duration_min=25.0, source="test")


def test_haversine_provider_osaka_to_kyoto() -> None:
    osaka = (34.7025, 135.4959)
    kyoto = (34.9858, 135.7588)
    estimate = HaversineProvider().get_travel(*osaka, *kyoto)

    # 直線約39kmに道路係数1.3を掛けるため、プロバイダ値は約51kmになる。
    assert estimate.distance_km == pytest.approx(51.5, abs=0.5)
    assert estimate.duration_min == pytest.approx(77.2, abs=1.0)
    assert estimate.source == "haversine"


def test_station_distance_cache_miss_then_reverse_hit() -> None:
    # テスト終了時に消えるインメモリSQLiteを使い、実DBには触れない。
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    provider = CountingProvider()
    first = Station(id=1, lat=34.7, lon=135.5)
    second = Station(id=2, lat=35.0, lon=135.8)

    with Session(engine) as db:
        miss = get_station_travel(db, second, first, provider)
        hit = get_station_travel(db, first, second, provider)
        cached = db.query(StationDistance).one()

    assert miss == hit
    assert provider.calls == 1
    assert (cached.from_station_id, cached.to_station_id) == (1, 2)
    assert cached.source == "test"


def test_osrm_provider_converts_meters_and_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"routes": [{"distance": 12345, "duration": 1800}]}

    def fake_get(url: str, params: dict, timeout: int) -> Response:
        assert timeout == 5
        return Response()

    monkeypatch.setattr("app.services.distance.osrm_provider.requests.get", fake_get)
    estimate = OSRMProvider().get_travel(34.7, 135.5, 35.0, 135.8)
    assert estimate == TravelEstimate(12.345, 30.0, "osrm")


def test_osrm_provider_falls_back_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import requests

    def raise_timeout(*args: object, **kwargs: object) -> None:
        raise requests.Timeout("timeout")

    monkeypatch.setattr("app.services.distance.osrm_provider.requests.get", raise_timeout)
    estimate = OSRMProvider().get_travel(34.7, 135.5, 35.0, 135.8)
    assert estimate.source == "haversine"


def test_factory_selects_provider_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DISTANCE_PROVIDER", raising=False)
    assert isinstance(get_distance_provider(), HaversineProvider)
    monkeypatch.setenv("DISTANCE_PROVIDER", "osrm")
    assert isinstance(get_distance_provider(), OSRMProvider)
