from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.route import ManualRouteRequest, RouteOrigin  # noqa: E402
from app.services.distance.base import DistanceProvider, TravelEstimate  # noqa: E402
from app.services.distance.haversine_provider import HaversineProvider  # noqa: E402
from app.services.route.manual import compute_route  # noqa: E402
from app.services.route.mountain_factor import MOUNTAIN_CORRECTION_RATIO  # noqa: E402
from tests.route_test_data import make_station  # noqa: E402


class FixedProvider(DistanceProvider):
    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        return TravelEstimate(distance_km=10.0, duration_min=60.0, source="test")


@pytest.fixture()
def route_client(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with testing_session() as db:
        db.add_all(
            [
                make_station(1, "A", 35.0, 135.0),
                make_station(2, "B", 35.1, 135.1),
                make_station(3, "C", 35.2, 135.2),
                make_station(4, "座標なし", None, None),
            ]
        )
        db.commit()
    monkeypatch.setattr(
        "app.services.route.manual.get_distance_provider", lambda: FixedProvider()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict:
    payload = {
        "origin": {"lat": 34.7, "lon": 135.5, "label": "出発地"},
        "departure_time": "08:00",
        "station_ids": [1, 2, 3],
    }
    payload.update(overrides)
    return payload


def test_manual_route_applies_stay_override(route_client: TestClient) -> None:
    response = route_client.post(
        "/api/routes/manual", json=_payload(stay_overrides={"2": 30})
    )
    assert response.status_code == 200
    body = response.json()
    assert [stop["stay_min"] for stop in body["stops"]] == [15, 30, 15]
    assert body["totals"] == {"travel_min": 180, "distance_km": 30.0, "stay_min": 60}


def test_manual_route_return_to_origin_adds_return_leg(route_client: TestClient) -> None:
    response = route_client.post(
        "/api/routes/manual", json=_payload(return_to_origin=True)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["totals"]["travel_min"] == 240
    assert "destination=34.700000,135.500000" in body["google_maps_url"]


def test_manual_route_unknown_station_is_404(route_client: TestClient) -> None:
    response = route_client.post("/api/routes/manual", json=_payload(station_ids=[999]))
    assert response.status_code == 404
    assert "見つかりません" in response.json()["detail"]


def test_manual_route_missing_coordinates_is_422(route_client: TestClient) -> None:
    response = route_client.post("/api/routes/manual", json=_payload(station_ids=[4]))
    assert response.status_code == 422
    assert response.json()["detail"] == "座標未取得の駅が含まれています"


def test_manual_route_highway_leg_shortens_duration(route_client: TestClient) -> None:
    """高速区間（60分×0.55→切り上げ33分）が最初の区間にだけ効く。"""
    response = route_client.post("/api/routes/manual", json=_payload(highway_legs=[0]))
    assert response.status_code == 200
    body = response.json()
    # 08:00発 + 33分 = 08:33着（下道なら09:00着）
    assert body["stops"][0]["arrival"] == "08:33"
    assert body["stops"][1]["arrival"] == "09:48"  # 2区間目は下道60分のまま
    assert body["totals"]["travel_min"] == 33 + 60 + 60
    assert body["totals"]["distance_km"] == 30.0  # 距離は変わらない


def test_manual_route_highway_return_leg(route_client: TestClient) -> None:
    """帰路（区間インデックス=駅数）にも高速係数を適用できる。"""
    response = route_client.post(
        "/api/routes/manual", json=_payload(return_to_origin=True, highway_legs=[3])
    )
    assert response.status_code == 200
    assert response.json()["totals"]["travel_min"] == 60 * 3 + 33


def test_manual_route_invalid_highway_leg_is_422(route_client: TestClient) -> None:
    """帰着なしの3駅ルートで区間3（帰路）は存在しないため422。"""
    response = route_client.post("/api/routes/manual", json=_payload(highway_legs=[3]))
    assert response.status_code == 422
    assert "存在しない区間インデックス" in response.json()["detail"]


def test_manual_route_latest_mode_computes_departure(route_client: TestClient) -> None:
    """逆算モード: 締切17:00×3駅（各60分移動・15分滞在）なら最遅出発は13:30。"""
    payload = _payload(departure_mode="latest")
    del payload["departure_time"]
    response = route_client.post("/api/routes/manual", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["departure_time"] == "13:30"
    # 最遅出発なので、最後の駅には締切ちょうど（余裕0分）に到着する
    assert body["stops"][-1]["arrival"] == "17:00"
    assert body["stops"][-1]["margin_min"] == 0
    assert all("stamp_deadline_missed" not in stop["warnings"] for stop in body["stops"])


def test_manual_route_latest_mode_with_return_by(route_client: TestClient) -> None:
    """逆算モード+帰着締切: 18:00帰着（帰路60分）を含めて逆算すると出発は13:15。"""
    payload = _payload(departure_mode="latest", return_to_origin=True, return_by="18:00")
    del payload["departure_time"]
    response = route_client.post("/api/routes/manual", json=payload)
    assert response.status_code == 200
    assert response.json()["departure_time"] == "13:15"


def test_manual_route_fixed_mode_requires_departure_time(route_client: TestClient) -> None:
    payload = _payload()
    del payload["departure_time"]
    response = route_client.post("/api/routes/manual", json=payload)
    assert response.status_code == 422


def test_manual_route_invalid_visit_date_is_422(route_client: TestClient) -> None:
    response = route_client.post(
        "/api/routes/manual", json=_payload(visit_date="2026/07/16")
    )
    assert response.status_code == 422


def test_manual_route_without_visit_date_ignores_business_hours(
    route_client: TestClient,
) -> None:
    """visit_date未指定なら曜日別営業時間を見ない（後方互換）。"""
    response = route_client.post("/api/routes/manual", json=_payload())
    assert response.status_code == 200
    assert all("wait_for_open" not in stop["warnings"] for stop in response.json()["stops"])


@pytest.fixture()
def hours_route_client(monkeypatch: pytest.MonkeyPatch):
    """曜日別営業時間・定休日を仕込んだ駅で、visit_date関連の警告を検証するための専用フィクスチャ。"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)

    def override_get_db():
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with testing_session() as db:
        db.add_all(
            [
                # 2026-07-16(木)は10:00開店。08:00発+60分移動=09:00着なので開店待ちが発生する
                make_station(
                    1, "A", 35.0, 135.0,
                    business_hours='{"thu": "10:00-17:00"}',
                ),
                # 同じ木曜が定休日
                make_station(2, "B", 35.1, 135.1, closed_days="thu,fri"),
            ]
        )
        db.commit()
    monkeypatch.setattr(
        "app.services.route.manual.get_distance_provider", lambda: FixedProvider()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


# --- 山間部の道路係数補正（Issue #73） ---
# route_clientフィクスチャはget_distance_providerをFixedProvider（source="test"）に
# 差し替えており補正対象外のため、ここではcompute_routeをHaversineProviderで直接呼ぶ。


def _compute_single_station_route(*, is_mountainous: bool, return_to_origin: bool = False):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with testing_session() as db:
        # 大阪駅→京都: test_distance.pyと同じ座標（直線約39km、道路係数1.3で約51.5km）
        station = make_station(1, "対象駅", 34.9858, 135.7588)
        station.is_mountainous = is_mountainous
        db.add(station)
        db.commit()
        payload = ManualRouteRequest(
            origin=RouteOrigin(lat=34.7025, lon=135.4959, label="大阪駅"),
            departure_time="09:00",
            station_ids=[1],
            return_to_origin=return_to_origin,
        )
        return compute_route(db, payload, provider=HaversineProvider())


def test_manual_route_visit_date_adds_wait_for_open_warning(
    hours_route_client: TestClient,
) -> None:
    response = hours_route_client.post(
        "/api/routes/manual",
        json=_payload(station_ids=[1], visit_date="2026-07-16"),
    )
    assert response.status_code == 200
    stop = response.json()["stops"][0]
    assert stop["arrival"] == "09:00"
    assert "wait_for_open" in stop["warnings"]
    # 10:00開店を待って15分滞在するため出発は10:15
    assert stop["departure"] == "10:15"


def test_manual_route_visit_date_adds_closed_day_warning(
    hours_route_client: TestClient,
) -> None:
    response = hours_route_client.post(
        "/api/routes/manual",
        json=_payload(station_ids=[2], visit_date="2026-07-16"),
    )
    assert response.status_code == 200
    stop = response.json()["stops"][0]
    assert "closed_day" in stop["warnings"]
    # 定休日でもプランからは自動除外されず、時刻は通常通り計算される
    assert stop["arrival"] == "09:00"


def test_manual_route_mountain_flag_scales_distance_and_duration() -> None:
    """山間駅が絡む区間は、距離・所要時間ともに道路係数1.6/1.3倍相当に補正される。"""
    flat = _compute_single_station_route(is_mountainous=False)
    mountain = _compute_single_station_route(is_mountainous=True)

    assert flat.estimates[0].source == "haversine"
    assert mountain.estimates[0].source == "haversine+mountain"
    assert mountain.estimates[0].distance_km == pytest.approx(
        flat.estimates[0].distance_km * MOUNTAIN_CORRECTION_RATIO
    )
    assert mountain.estimates[0].duration_min == pytest.approx(
        flat.estimates[0].duration_min * MOUNTAIN_CORRECTION_RATIO
    )


def test_manual_route_mountain_flag_scales_return_leg() -> None:
    """帰路（最終駅→出発地）区間も、最終駅が山間駅なら同様に補正される。"""
    flat = _compute_single_station_route(is_mountainous=False, return_to_origin=True)
    mountain = _compute_single_station_route(is_mountainous=True, return_to_origin=True)

    assert flat.return_estimate is not None and mountain.return_estimate is not None
    assert flat.return_estimate.source == "haversine"
    assert mountain.return_estimate.source == "haversine+mountain"
    assert mountain.return_estimate.duration_min == pytest.approx(
        flat.return_estimate.duration_min * MOUNTAIN_CORRECTION_RATIO
    )


def test_manual_route_osrm_provider_is_not_mountain_corrected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSRM等、実道路距離を返すプロバイダの結果は山間駅でも補正しない。"""

    class FakeOsrmProvider(DistanceProvider):
        def get_travel(
            self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
        ) -> TravelEstimate:
            return TravelEstimate(distance_km=42.0, duration_min=42.0, source="osrm")

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with testing_session() as db:
        station = make_station(1, "山間の駅", 34.9858, 135.7588)
        station.is_mountainous = True
        db.add(station)
        db.commit()
        payload = ManualRouteRequest(
            origin=RouteOrigin(lat=34.7025, lon=135.4959, label="大阪駅"),
            departure_time="09:00",
            station_ids=[1],
        )
        result = compute_route(db, payload, provider=FakeOsrmProvider())
    assert result.estimates[0] == TravelEstimate(42.0, 42.0, "osrm")
