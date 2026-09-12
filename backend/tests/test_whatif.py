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
from app.services.distance.base import DistanceProvider, TravelEstimate  # noqa: E402
from app.services.route.whatif import (  # noqa: E402
    calculate_latest_departures,
    shift_time,
)
from tests.route_test_data import make_station  # noqa: E402

# --- 純粋関数: 最遅出発時刻の逆算 ---


def test_latest_departure_matches_skill_example() -> None:
    """SKILL.mdの例: 「13:00までにCを出ればEに間に合う」。

    C→E の移動が60分、Eの締切が14:00なら、Cの最遅出発は13:00になる。
    """
    latest = calculate_latest_departures(
        deadlines_min=[17 * 60, 14 * 60],  # C: 17:00 / E: 14:00
        stays_min=[15, 15],
        travels_min=[30, 60],  # 出発地→C: 30分 / C→E: 60分
        return_travel_min=None,
        return_by_min=None,
    )
    assert latest == [13 * 60, None]  # C: 13:00、Eは以降に制約なし


def test_latest_departure_propagates_through_chain() -> None:
    """次の駅の最遅出発（滞在込み）の方が締切より厳しい場合はそちらが効く。"""
    latest = calculate_latest_departures(
        deadlines_min=[17 * 60, 17 * 60, 12 * 60],
        stays_min=[15, 15, 15],
        travels_min=[30, 30, 30],
        return_travel_min=None,
        return_by_min=None,
    )
    # 駅2の締切12:00 → 駅1の最遅出発 11:30 → 駅0は 11:30 - 15 - 30 = 10:45
    assert latest == [645, 690, None]


def test_latest_departure_uses_return_deadline_for_last_stop() -> None:
    latest = calculate_latest_departures(
        deadlines_min=[17 * 60],
        stays_min=[15],
        travels_min=[30],
        return_travel_min=40,
        return_by_min=18 * 60,
    )
    assert latest == [18 * 60 - 40]  # 17:20までに出れば18:00に帰着できる


def test_latest_departure_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        calculate_latest_departures([600], [15, 15], [30], None, None)


def test_shift_time_adds_delay() -> None:
    assert shift_time("09:00", 75) == "10:15"
    assert shift_time("09:00", 0) == "09:00"


# --- API: /api/routes/what-if ---


class FixedProvider(DistanceProvider):
    """全区間60分・10kmで固定し、時刻計算を検証しやすくする。"""

    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        return TravelEstimate(distance_km=10.0, duration_min=60.0, source="test")


@pytest.fixture()
def whatif_client(monkeypatch: pytest.MonkeyPatch):
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


def test_what_if_delay_shifts_arrivals(whatif_client: TestClient) -> None:
    response = whatif_client.post("/api/routes/what-if", json=_payload(delay_min=60))
    assert response.status_code == 200
    body = response.json()
    assert body["applied_delay_min"] == 60
    # 08:00発が09:00発になり、最初の駅到着は10:00（移動60分）
    assert body["stops"][0]["arrival"] == "10:00"


def test_what_if_exclusion_removes_station(whatif_client: TestClient) -> None:
    response = whatif_client.post(
        "/api/routes/what-if", json=_payload(excluded_station_ids=[2])
    )
    assert response.status_code == 200
    body = response.json()
    assert [stop["name"] for stop in body["stops"]] == ["A", "C"]
    assert body["excluded_station_ids"] == [2]
    # Bを飛ばすためCの到着が早まる（A出発09:15 + 60分 = 10:15）
    assert body["stops"][1]["arrival"] == "10:15"


def test_what_if_reports_latest_departure(whatif_client: TestClient) -> None:
    response = whatif_client.post("/api/routes/what-if", json=_payload())
    assert response.status_code == 200
    stops = response.json()["stops"]
    # 締切は全駅17:00。B(2番目)の最遅出発は「Cに17:00までに着ける」16:00
    assert stops[1]["latest_departure"] == "16:00"
    # A(1番目)は「Bの最遅出発16:00 - 滞在15分 - 移動60分」= 14:45
    assert stops[0]["latest_departure"] == "14:45"
    assert stops[0]["departure_slack_min"] == 14 * 60 + 45 - (9 * 60 + 15)
    # 最終駅は帰着締切がないため制約なし
    assert stops[2]["latest_departure"] is None


def test_what_if_return_deadline_missed_warning(whatif_client: TestClient) -> None:
    response = whatif_client.post(
        "/api/routes/what-if",
        json=_payload(return_to_origin=True, return_by="10:00"),
    )
    assert response.status_code == 200
    body = response.json()
    assert "return_deadline_missed" in body["warnings"]
    # 最終駅の最遅出発は 10:00 - 帰路60分 = 09:00
    assert body["stops"][2]["latest_departure"] == "09:00"
    assert body["stops"][2]["departure_slack_min"] < 0


def test_what_if_all_excluded_is_422(whatif_client: TestClient) -> None:
    response = whatif_client.post(
        "/api/routes/what-if", json=_payload(excluded_station_ids=[1, 2, 3])
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "すべての駅が除外されています"
