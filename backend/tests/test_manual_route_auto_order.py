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
from tests.route_test_data import make_station  # noqa: E402

# 出発地(0)-A(1)-B(2)-C(3)が一直線上に並ぶが、Bだけ大きく離れているケース。
# 選択順C,A,Bのまま計算すると総移動時間が長いが、auto_order=trueなら
# 出発地から近い順（A→B→C）に並べ替えて短縮する。
LINE_MATRIX = {
    (0.0, 1.0): 10.0,  # 出発地→A
    (0.0, 2.0): 20.0,  # 出発地→B
    (0.0, 3.0): 100.0,  # 出発地→C（Cは締切に絶対間に合わないほど遠い）
    (1.0, 2.0): 15.0,  # A→B
    (1.0, 3.0): 90.0,  # A→C
    (2.0, 3.0): 85.0,  # B→C
}


class LineProvider(DistanceProvider):
    """緯度を駅の識別子として使い、固定表で所要時間を返すテスト用プロバイダ。"""

    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        if from_lat == to_lat:
            return TravelEstimate(distance_km=0.0, duration_min=0.0, source="test")
        key = (from_lat, to_lat) if (from_lat, to_lat) in LINE_MATRIX else (to_lat, from_lat)
        return TravelEstimate(distance_km=10.0, duration_min=LINE_MATRIX[key], source="test")


@pytest.fixture()
def auto_order_client(monkeypatch: pytest.MonkeyPatch):
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
                make_station(1, "A", 1.0, 0.0),
                make_station(2, "B", 2.0, 0.0),
                # Cは締切09:00。出発08:00からは直行でも100分かかり、どの順でも必ず間に合わない
                make_station(3, "C", 3.0, 0.0, stamp_end="09:00"),
            ]
        )
        db.commit()
    monkeypatch.setattr(
        "app.services.route.manual.get_distance_provider", lambda: LineProvider()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict:
    payload = {
        "origin": {"lat": 0.0, "lon": 0.0, "label": "出発地"},
        "departure_time": "08:00",
        "station_ids": [3, 1, 2],  # わざと悪い順（C, A, B）で選択
    }
    payload.update(overrides)
    return payload


def test_auto_order_false_keeps_selection_order_as_is(auto_order_client: TestClient) -> None:
    """auto_order未指定（デフォルトFalse）は、従来通り選択順のまま並べ替えない（後方互換）。"""
    response = auto_order_client.post("/api/routes/manual", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert [stop["station_id"] for stop in body["stops"]] == [3, 1, 2]
    # 選択順のまま: 出発地→C(100) + C→A(90) + A→B(15) = 205分
    assert body["totals"]["travel_min"] == 205


def test_auto_order_true_reorders_and_keeps_all_stations(auto_order_client: TestClient) -> None:
    """auto_order=trueなら、全駅を含んだまま総移動時間の短い順(A→B→C)に並べ替える。"""
    response = auto_order_client.post(
        "/api/routes/manual", json=_payload(auto_order=True)
    )
    assert response.status_code == 200
    body = response.json()
    assert [stop["station_id"] for stop in body["stops"]] == [1, 2, 3]
    assert {stop["station_id"] for stop in body["stops"]} == {1, 2, 3}
    # 並べ替え後: 出発地→A(10) + A→B(15) + B→C(85) = 110分（選択順205分より短い）
    assert body["totals"]["travel_min"] == 110


def test_auto_order_true_still_includes_station_that_misses_deadline(
    auto_order_client: TestClient,
) -> None:
    """2-optは締切による棄却をしないため、並べ替えても間に合わない駅は含めたまま警告を出す。"""
    response = auto_order_client.post(
        "/api/routes/manual", json=_payload(auto_order=True)
    )
    assert response.status_code == 200
    body = response.json()
    station_ids = [stop["station_id"] for stop in body["stops"]]
    assert station_ids == [1, 2, 3]  # Cが間引かれずに含まれている
    stop_c = body["stops"][-1]
    assert stop_c["station_id"] == 3
    assert "stamp_deadline_missed" in stop_c["warnings"]


def test_auto_order_true_with_return_to_origin_considers_return_leg(
    auto_order_client: TestClient,
) -> None:
    """return_to_origin=trueの場合、帰路区間も並べ替えの評価対象に含まれる。"""
    response = auto_order_client.post(
        "/api/routes/manual",
        json=_payload(auto_order=True, return_to_origin=True, station_ids=[1, 2, 3]),
    )
    assert response.status_code == 200
    body = response.json()
    # 全駅を含んだままGoogle Mapsの帰着先が出発地になっていることを確認する
    assert {stop["station_id"] for stop in body["stops"]} == {1, 2, 3}
    assert "destination=0.000000,0.000000" in body["google_maps_url"]


def test_auto_order_with_highway_legs_is_422(auto_order_client: TestClient) -> None:
    """高速区間のインデックスは並び順依存のため、auto_orderとの併用は入口で拒否する。"""
    response = auto_order_client.post(
        "/api/routes/manual", json=_payload(auto_order=True, highway_legs=[0])
    )
    assert response.status_code == 422
    assert "併用できません" in response.text


def test_auto_order_with_latest_mode_is_422(auto_order_client: TestClient) -> None:
    """逆算モードは最適化が締切・滞在を考慮しないため併用未対応（Issue #83で対応予定）。"""
    payload = _payload(auto_order=True, departure_mode="latest")
    del payload["departure_time"]
    response = auto_order_client.post("/api/routes/manual", json=payload)
    assert response.status_code == 422
    assert "逆算と自動最適順の併用は未対応" in response.text


# --- 山間係数（Issue #73）を最適化コストに反映する検証 ---
# 出発地(0)-A(1)-B(2)。Aは山間駅（is_mountainous=True）。
# 生の所要時間: O→A=10 / O→B=12 / A→B=10（対称）
#   補正なし: A→B順 = 10+10 = 20 < B→A順 = 12+10 = 22 → A先行が「最適」に見える
#   補正あり（Aが絡む区間は×1.6/1.3≒1.2308）:
#     A→B順 = 12.31+12.31 = 24.62 > B→A順 = 12+12.31 = 24.31 → B先行が本当の最短
MOUNTAIN_MATRIX = {
    (0.0, 1.0): 10.0,
    (0.0, 2.0): 12.0,
    (1.0, 2.0): 10.0,
}


class MountainCaseProvider(DistanceProvider):
    """source="haversine"を名乗り、山間補正の対象になるテスト用プロバイダ。"""

    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        if from_lat == to_lat:
            return TravelEstimate(distance_km=0.0, duration_min=0.0, source="haversine")
        key = (
            (from_lat, to_lat) if (from_lat, to_lat) in MOUNTAIN_MATRIX else (to_lat, from_lat)
        )
        return TravelEstimate(
            distance_km=10.0, duration_min=MOUNTAIN_MATRIX[key], source="haversine"
        )


@pytest.fixture()
def mountain_client(monkeypatch: pytest.MonkeyPatch):
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
        station_a = make_station(1, "A（山間）", 1.0, 0.0)
        station_a.is_mountainous = True
        db.add_all([station_a, make_station(2, "B", 2.0, 0.0)])
        db.commit()
    monkeypatch.setattr(
        "app.services.route.manual.get_distance_provider", lambda: MountainCaseProvider()
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_auto_order_optimization_accounts_for_mountain_factor(
    mountain_client: TestClient,
) -> None:
    """山間補正込みのコストで最適化する: 生値ならA先行だが、補正後はB先行が最短になる。"""
    response = mountain_client.post(
        "/api/routes/manual", json=_payload(auto_order=True, station_ids=[1, 2])
    )
    assert response.status_code == 200
    body = response.json()
    assert [stop["station_id"] for stop in body["stops"]] == [2, 1]
    # 最終計算も同じ補正を使う: O→B=12分 + B→A=ceil(10×1.6/1.3)=13分 = 25分
    assert body["totals"]["travel_min"] == 25
