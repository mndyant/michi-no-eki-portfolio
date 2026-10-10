"""Real Osaka dataset, calculation flow and public write boundary."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient
from app.public_demo import app, demo_db
from app.models.station import Station

client = TestClient(app)
PLAN = {"origin": {"lat": 34.7025, "lon": 135.4959}, "departure_time": "08:00", "station_ids": [5, 2, 4]}


def test_default_sample_waits_for_opening_without_a_visit_date():
    response = client.post("/api/routes/manual", json=PLAN)
    assert response.status_code == 200
    body = response.json()
    assert body["stops"][0]["arrival"] == "08:41"
    assert body["stops"][0]["departure"] == "09:15"
    assert body["stops"][0]["warnings"] == ["wait_for_open"]
    assert body["stops"][1]["arrival"] == "09:29"
    assert body["stops"][2]["departure"] == "10:11"
    assert body["totals"]["wait_min"] == 19
    dated = client.post("/api/routes/manual", json={**PLAN, "visit_date": "2026-10-10"})
    assert dated.json() == body
    delayed = client.post("/api/routes/what-if", json={**PLAN, "delay_min": 60})
    assert delayed.status_code == 200
    assert delayed.json()["stops"][0]["departure"] == "09:56"
    assert delayed.json()["totals"]["wait_min"] == 0


def test_public_stations_match_approved_json_exactly():
    source = json.loads((Path(__file__).resolve().parents[2] / "data/demo/stations_osaka.json").read_text(encoding="utf-8"))
    response = client.get("/api/stations")
    assert response.status_code == 200
    actual = response.json()
    assert len(actual) == len(source) == 10
    assert response.headers["cache-control"] == "no-store"
    for station, raw in zip(actual, source):
        assert all(station[key] == raw[key] for key in ("station_id", "name", "pref", "lat", "lon", "address"))
        assert station["pref"] == "大阪府" and station["last_verified_at"] is None
        assert station["visited"] is False and station["user_memo"] is None


def test_plan_whatif_suggest_and_concurrent_repeatability():
    base = client.post("/api/routes/manual", json=PLAN)
    assert base.status_code == 200
    assert [s["name"] for s in base.json()["stops"]] == ["しらとりの郷・羽曳野", "近つ飛鳥の里太子", "かなん"]
    delayed = client.post("/api/routes/what-if", json={**PLAN, "delay_min": 60})
    assert delayed.status_code == 200
    assert delayed.json()["applied_delay_min"] == 60
    assert delayed.json()["stops"][0]["arrival"] != base.json()["stops"][0]["arrival"]
    omitted = client.post("/api/routes/what-if", json={**PLAN, "excluded_station_ids": [2]})
    assert len(omitted.json()["stops"]) == 2
    suggestions = client.post("/api/routes/suggest", json={"origin": PLAN["origin"], "departure_time": "08:00", "max_stations": 3})
    assert suggestions.status_code == 200 and suggestions.json()["plans"]
    assert all(len(p["stops"]) <= 3 for p in suggestions.json()["plans"])
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: client.post("/api/routes/manual", json=PLAN).json(), range(3)))
    assert all(result == base.json() for result in results)


def test_public_boundary_rejects_writes_and_unbounded_work():
    for path, method in [("/api/stations", "post"), ("/api/stations/1", "put"), ("/api/stations/1/visit", "patch"), ("/api/stations/1/visit-records", "post"), ("/api/visit-records/1/photos", "post")]:
        assert getattr(client, method)(path, json={}).status_code in (404, 405)
    for changes in ({"station_ids": [1] * 11}, {"station_ids": [1, 1]}, {"stay_overrides": {1: 481}}):
        assert client.post("/api/routes/manual", json={**PLAN, **changes}).status_code == 422
    assert client.post("/api/routes/manual", content=b"x" * 16_385).status_code == 413
    assert client.get("/data/demo/stations_osaka.json").status_code == 404
    assert client.get("/.env").status_code == 404


def test_each_request_owns_its_database():
    first = demo_db()
    db = next(first)
    station = db.get(Station, 1)
    station.name = "Request-local change"
    db.commit()
    second = demo_db()
    try:
        assert next(second).get(Station, 1).name == "ちはやあかさか"
    finally:
        first.close()
        second.close()
