# stations/clusters CRUD APIの結合テスト
# 本物のbackend/data.dbは使わず、テスト用のインメモリSQLiteにDB接続を差し替えて検証する
import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# backend/ をパスに通す
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.cluster import Cluster  # noqa: E402
from app.models.station import Station  # noqa: E402


@pytest.fixture()
def client():
    """テストケースごとにまっさらなインメモリSQLiteを用意し、FastAPIのDB依存を差し替える"""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # インメモリDBを複数接続で共有するために必要
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # テスト用の初期データ（クラスタ1件・道の駅1件）を投入
    db = TestingSessionLocal()
    cluster = Cluster(name="大阪府1", description=None)
    db.add(cluster)
    db.commit()
    db.refresh(cluster)

    station = Station(
        station_id="TEST_001",
        name="テスト道の駅",
        pref="大阪府",
        city=None,
        address="大阪市北区",
        lat=34.70,
        lon=135.50,
        official_url=None,
        business_hours='{"mon": "09:00-17:00"}',
        stamp_start="09:00",
        stamp_end="17:00",
        closed_days="",
        visited=False,
        visited_date=None,
        stay_time_min_default=15,
        facility_scale="medium",
        good_for_lunch=True,
        good_for_sweets=False,
        good_for_souvenir=True,
        has_spa=False,
        scenery_score=None,
        is_mountainous=False,
        revisit_difficulty_score=2,
        revisit_difficulty_reason="基準1点のみ（加点要因なし）。",
        cluster_id=cluster.id,
        reputation_items="[]",
        local_specialty="[]",
        seasonal_specialty="[]",
        user_memo=None,
        source="test",
        last_verified_at=date(2026, 5, 17),
    )
    db.add(station)
    db.commit()
    db.close()

    yield TestClient(app)

    app.dependency_overrides.clear()


def test_health_check(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_list_stations_returns_seeded_station(client: TestClient):
    res = client.get("/api/stations")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["name"] == "テスト道の駅"
    # JSON文字列カラムがdict/listとして返ること
    assert body[0]["business_hours"] == {"mon": "09:00-17:00"}
    assert body[0]["reputation_items"] == []


def test_list_stations_filter_by_pref(client: TestClient):
    assert len(client.get("/api/stations", params={"pref": "大阪府"}).json()) == 1
    assert len(client.get("/api/stations", params={"pref": "京都府"}).json()) == 0


def test_list_stations_filter_by_visited(client: TestClient):
    assert len(client.get("/api/stations", params={"visited": "false"}).json()) == 1
    assert len(client.get("/api/stations", params={"visited": "true"}).json()) == 0


def test_list_stations_filter_by_cluster_id(client: TestClient):
    station_id = client.get("/api/stations").json()[0]["cluster_id"]
    assert len(client.get("/api/stations", params={"cluster_id": station_id}).json()) == 1
    assert len(client.get("/api/stations", params={"cluster_id": 999}).json()) == 0


def test_get_station_detail(client: TestClient):
    station_pk = client.get("/api/stations").json()[0]["id"]
    res = client.get(f"/api/stations/{station_pk}")
    assert res.status_code == 200
    assert res.json()["station_id"] == "TEST_001"


def test_get_station_not_found_returns_japanese_404(client: TestClient):
    res = client.get("/api/stations/9999")
    assert res.status_code == 404
    assert "見つかりません" in res.json()["detail"]


def test_create_station(client: TestClient):
    payload = {
        "station_id": "TEST_002",
        "name": "新規道の駅",
        "pref": "京都府",
        "business_hours": {"mon": "09:00-17:00"},
        "stamp_start": "09:00",
        "stamp_end": "17:00",
        "facility_scale": "small",
        "revisit_difficulty_score": 1,
        "revisit_difficulty_reason": "基準1点のみ（加点要因なし）。",
        "source": "test",
        "last_verified_at": "2026-05-17",
    }
    res = client.post("/api/stations", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["station_id"] == "TEST_002"
    assert body["visited"] is False

    # 一覧に反映されていること
    assert len(client.get("/api/stations").json()) == 2


def test_create_station_duplicate_station_id_returns_400(client: TestClient):
    payload = {
        "station_id": "TEST_001",  # 既存と重複
        "name": "重複道の駅",
        "pref": "京都府",
        "business_hours": {},
        "stamp_start": "09:00",
        "stamp_end": "17:00",
        "facility_scale": "small",
        "revisit_difficulty_score": 1,
        "revisit_difficulty_reason": "-",
        "source": "test",
        "last_verified_at": "2026-05-17",
    }
    res = client.post("/api/stations", json=payload)
    assert res.status_code == 400
    assert "既に登録されています" in res.json()["detail"]


def test_update_station_partial(client: TestClient):
    station_pk = client.get("/api/stations").json()[0]["id"]
    res = client.put(f"/api/stations/{station_pk}", json={"user_memo": "売店が良かった"})
    assert res.status_code == 200
    body = res.json()
    assert body["user_memo"] == "売店が良かった"
    assert body["name"] == "テスト道の駅"  # 指定していない項目は変わらない


def test_update_station_not_found_returns_404(client: TestClient):
    res = client.put("/api/stations/9999", json={"user_memo": "x"})
    assert res.status_code == 404


def test_patch_visit_status(client: TestClient):
    station_pk = client.get("/api/stations").json()[0]["id"]
    res = client.patch(
        f"/api/stations/{station_pk}/visit",
        json={"visited": True, "visited_date": "2026-07-11"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["visited"] is True
    assert body["visited_date"] == "2026-07-11"

    # 未訪問フィルタから外れ、訪問済みフィルタに現れること
    assert len(client.get("/api/stations", params={"visited": "false"}).json()) == 0
    assert len(client.get("/api/stations", params={"visited": "true"}).json()) == 1


def test_delete_station(client: TestClient):
    station_pk = client.get("/api/stations").json()[0]["id"]
    res = client.delete(f"/api/stations/{station_pk}")
    assert res.status_code == 204
    assert client.get("/api/stations").json() == []


def test_delete_station_not_found_returns_404(client: TestClient):
    res = client.delete("/api/stations/9999")
    assert res.status_code == 404


def test_list_clusters(client: TestClient):
    res = client.get("/api/clusters")
    assert res.status_code == 200
    body = res.json()
    assert len(body) == 1
    assert body[0]["name"] == "大阪府1"
