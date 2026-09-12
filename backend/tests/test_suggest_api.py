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
from app.services.route.mountain_factor import MOUNTAIN_CORRECTION_RATIO  # noqa: E402
from tests.route_test_data import make_station  # noqa: E402


@pytest.fixture()
def suggest_client():
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
        # 大阪駅（34.70, 135.49）周辺に近い順で3駅。座標なし・訪問済み・他府県も混ぜる
        near = make_station(1, "近い駅", 34.75, 135.50)
        middle = make_station(2, "中間の駅", 34.85, 135.60)
        far = make_station(3, "遠い駅", 35.00, 135.75)
        visited = make_station(4, "訪問済みの駅", 34.72, 135.52)
        visited.visited = True
        kyoto = make_station(5, "京都の駅", 34.95, 135.70)
        kyoto.pref = "京都府"
        no_coords = make_station(6, "座標なし", None, None)
        db.add_all([near, middle, far, visited, kyoto, no_coords])
        db.commit()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _payload(**overrides: object) -> dict:
    payload = {
        "origin": {"lat": 34.70, "lon": 135.49, "label": "大阪駅"},
        "departure_time": "09:00",
        "max_stations": 3,
    }
    payload.update(overrides)
    return payload


def test_suggest_returns_four_plans_with_timetable(suggest_client: TestClient) -> None:
    response = suggest_client.post("/api/routes/suggest", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert [plan["key"] for plan in body["plans"]] == [
        "far_first", "max", "light", "gourmet", "rare",
    ]
    for plan in body["plans"]:
        assert 1 <= len(plan["stops"]) <= 3
        assert plan["google_maps_url"].startswith("https://www.google.com/maps/dir/")
        assert plan["totals"]["travel_min"] > 0
        # 行程の終了時刻（帰着なしなので最終駅の出発時刻）を返す
        assert plan["finish_time"] == plan["stops"][-1]["departure"]
    # 訪問済み・座標なしは候補に入らない（未訪問かつ座標ありの4駅のみ）
    assert body["candidate_count"] == 4


def test_suggest_pref_filter_limits_candidates(suggest_client: TestClient) -> None:
    response = suggest_client.post(
        "/api/routes/suggest", json=_payload(prefs=["京都府"])
    )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 1
    for plan in body["plans"]:
        assert [stop["name"] for stop in plan["stops"]] == ["京都の駅"]


def test_suggest_include_visited_adds_visited_station(suggest_client: TestClient) -> None:
    response = suggest_client.post(
        "/api/routes/suggest", json=_payload(include_visited=True)
    )
    assert response.status_code == 200
    assert response.json()["candidate_count"] == 5


def test_suggest_no_candidates_returns_warning(suggest_client: TestClient) -> None:
    response = suggest_client.post(
        "/api/routes/suggest", json=_payload(prefs=["福井県"])
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plans"] == []
    assert body["warnings"] == ["no_candidates"]


def test_suggest_invalid_time_is_422(suggest_client: TestClient) -> None:
    response = suggest_client.post(
        "/api/routes/suggest", json=_payload(departure_time="25時")
    )
    assert response.status_code == 422


def test_suggest_direction_filter(suggest_client: TestClient) -> None:
    """方面フィルタ: シード駅は全て大阪駅の北〜北東側にあるため、南を選ぶと候補0になる。"""
    north = suggest_client.post("/api/routes/suggest", json=_payload(directions=["北"]))
    assert north.status_code == 200
    assert north.json()["candidate_count"] == 4

    south = suggest_client.post("/api/routes/suggest", json=_payload(directions=["南"]))
    assert south.status_code == 200
    body = south.json()
    assert body["candidate_count"] == 0
    assert body["warnings"] == ["no_candidates"]


def test_suggest_invalid_direction_is_422(suggest_client: TestClient) -> None:
    response = suggest_client.post(
        "/api/routes/suggest", json=_payload(directions=["上"])
    )
    assert response.status_code == 422


def test_suggest_last_arrival_by_limits_plans(suggest_client: TestClient) -> None:
    """最終駅到着締切: 全プランの全駅到着がlast_arrival_by以前になる。"""
    response = suggest_client.post(
        "/api/routes/suggest", json=_payload(last_arrival_by="10:30")
    )
    assert response.status_code == 200
    for plan in response.json()["plans"]:
        for stop in plan["stops"]:
            assert stop["arrival"] <= "10:30"


def test_suggest_plans_include_reason(suggest_client: TestClient) -> None:
    """各プランに実際の結果を反映した推薦理由(reason)が付く（フェーズ5・Issue #52）。"""
    response = suggest_client.post("/api/routes/suggest", json=_payload())
    assert response.status_code == 200
    for plan in response.json()["plans"]:
        assert plan["reason"]
        assert str(len(plan["stops"])) + "駅" in plan["reason"]


def test_suggest_free_text_fills_unset_directions(suggest_client: TestClient) -> None:
    """directions未指定なら自然文から解釈して補う（シード駅は全て北〜北東側）。"""
    response = suggest_client.post(
        "/api/routes/suggest",
        json=_payload(free_text="北方面をゆったり回りたい"),
    )
    assert response.status_code == 200
    assert response.json()["candidate_count"] == 4


def test_suggest_free_text_does_not_override_explicit_directions(suggest_client: TestClient) -> None:
    """directionsを明示指定済みなら自然文の解釈で上書きしない。"""
    response = suggest_client.post(
        "/api/routes/suggest",
        json=_payload(directions=["南"], free_text="北方面を回りたい"),
    )
    assert response.status_code == 200
    assert response.json()["candidate_count"] == 0


def test_suggest_use_highway_shortens_travel(suggest_client: TestClient) -> None:
    """高速利用時は総移動時間が下道より短くなる。"""
    normal = suggest_client.post("/api/routes/suggest", json=_payload()).json()
    highway = suggest_client.post(
        "/api/routes/suggest", json=_payload(use_highway=True)
    ).json()
    assert (
        highway["plans"][0]["totals"]["travel_min"]
        < normal["plans"][0]["totals"]["travel_min"]
    )


# --- 遠方から戻るプランの候補絞り込み（Issue #73） ---


@pytest.fixture()
def many_stations_client():
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
        # 出発地(34.70, 135.49)から真北へ0.01度ずつ離れる45駅。
        # MAX_CANDIDATES(40)を超えるため、近い順に切ると最遠5駅(id 41-45)が候補から漏れる
        stations = [
            make_station(i, f"駅{i:02d}", 34.70 + i * 0.01, 135.49) for i in range(1, 46)
        ]
        db.add_all(stations)
        db.commit()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_suggest_far_first_sees_true_farthest_beyond_max_candidates(
    many_stations_client: TestClient,
) -> None:
    """far_firstは近い順40件に絞る前の全候補から最遠を選ぶ（近場の中の最遠を選ばない）。"""
    response = many_stations_client.post(
        "/api/routes/suggest",
        json={
            "origin": {"lat": 34.70, "lon": 135.49, "label": "大阪駅"},
            "departure_time": "09:00",
            "max_stations": 1,
        },
    )
    assert response.status_code == 200
    body = response.json()
    # 近い順候補（他プロファイル用）は上限40件に切られたまま
    assert body["candidate_count"] == 40
    far_first = next(plan for plan in body["plans"] if plan["key"] == "far_first")
    # 45駅中もっとも遠いのはid=45。近い順40件（id<=40）には含まれない
    assert far_first["station_ids"] == [45]

    max_plan = next(plan for plan in body["plans"] if plan["key"] == "max")
    # maxプランは従来通り近い順候補（id<=40）からしか選ばない
    assert max_plan["station_ids"][0] <= 40


# --- 山間部の道路係数補正（Issue #73） ---


@pytest.fixture()
def mountain_suggest_client():
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
        # 同一座標の駅を県名だけ変えて2件用意し、prefsフィルタで1件ずつ単独候補にして比較する
        mountain = make_station(1, "山間の駅", 34.9858, 135.7588)
        mountain.is_mountainous = True
        mountain.pref = "山間県"
        flat = make_station(2, "平地の駅", 34.9858, 135.7588)
        flat.pref = "平地県"
        db.add_all([mountain, flat])
        db.commit()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_suggest_mountain_flag_increases_travel_time(
    mountain_suggest_client: TestClient,
) -> None:
    """山間駅を含む候補は、同座標の平地駅より総移動時間が長く見積もられる（探索・最終計算とも）。"""
    payload = {
        "origin": {"lat": 34.70, "lon": 135.49, "label": "大阪駅"},
        "departure_time": "09:00",
        "max_stations": 1,
    }
    mountain_body = mountain_suggest_client.post(
        "/api/routes/suggest", json={**payload, "prefs": ["山間県"]}
    ).json()
    flat_body = mountain_suggest_client.post(
        "/api/routes/suggest", json={**payload, "prefs": ["平地県"]}
    ).json()

    mountain_travel = mountain_body["plans"][0]["totals"]["travel_min"]
    flat_travel = flat_body["plans"][0]["totals"]["travel_min"]
    assert mountain_travel > flat_travel
    # 道路係数1.3→1.6相当（約1.2308倍）の補正であることを確認する（ceil丸め分の誤差を許容）
    assert mountain_travel == pytest.approx(flat_travel * MOUNTAIN_CORRECTION_RATIO, abs=2)
