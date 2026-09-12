from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.route.planner import (  # noqa: E402
    PLAN_PROFILES,
    PlanStation,
    build_plan,
    simulate_order,
)

# テストでは緯度を「駅の識別子」として使い、座標ペア→分の固定表で移動時間を引く。
# キーは (from_lat, to_lat)。対称にしておく
ORIGIN = 0.0


def _make_travel_fn(matrix: dict[tuple[float, float], float]):
    def travel_fn(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
        if from_lat == to_lat:
            return 0.0
        return matrix[(from_lat, to_lat)]

    return travel_fn


def _symmetric(matrix: dict[tuple[float, float], float]) -> dict[tuple[float, float], float]:
    return matrix | {(b, a): minutes for (a, b), minutes in matrix.items()}


def _station(
    key: float,
    name: str,
    deadline: str = "17:00",
    stay: int = 15,
    revisit: int = 1,
    food: int = 0,
) -> PlanStation:
    return PlanStation(
        station_id=int(key),
        name=name,
        lat=key,
        lon=0.0,
        stamp_deadline=deadline,
        stay_min=stay,
        revisit_score=revisit,
        food_score=food,
    )


def _profile(key: str):
    return next(profile for profile in PLAN_PROFILES if profile.key == key)


# --- DESIGN.md 8章の固定ケース: 遠回りでも締切の早いEを先に組み込む ---

# C(1.0)は近い・締切ゆるい / E(3.0)は遠い・締切11:00 / D(2.0)は中間・締切ゆるい。
# 距離だけならC→D→E（総移動100分）だが、それではEの締切に間に合わない。
CED_MATRIX = _symmetric(
    {
        (ORIGIN, 1.0): 30.0,  # 出発地→C
        (ORIGIN, 2.0): 40.0,  # 出発地→D
        (ORIGIN, 3.0): 80.0,  # 出発地→E
        (1.0, 2.0): 20.0,  # C→D
        (1.0, 3.0): 60.0,  # C→E
        (2.0, 3.0): 50.0,  # D→E
    }
)
CED_STATIONS = [
    _station(1.0, "C"),
    _station(2.0, "D"),
    _station(3.0, "E", deadline="11:00"),
]


def test_max_plan_visits_urgent_station_first() -> None:
    """最大効率でも、締切の早いEをC→E→Dの順で先に組み込む（EDF）。"""
    plan = build_plan(
        ORIGIN, 0.0, "09:00", CED_STATIONS,
        _make_travel_fn(CED_MATRIX), _profile("max"), max_stations=3,
    )
    assert [station.name for station in plan.order] == ["C", "E", "D"]
    assert plan.warnings == ()


def test_two_opt_rejects_shorter_but_infeasible_order() -> None:
    """C→D→Eは総移動100分と短いが締切違反のため、2-optは採用しない。"""
    result = simulate_order(
        ORIGIN, 0.0, 9 * 60,
        [CED_STATIONS[0], CED_STATIONS[1], CED_STATIONS[2]],
        _make_travel_fn(CED_MATRIX), min_margin_min=0,
        return_to_origin=False, return_by_min=None,
    )
    assert result.feasible is False


def test_light_plan_drops_station_without_enough_margin() -> None:
    """軽めプランは、直行しても余裕30分を確保できない駅を組み込まず、件数減の警告を出す。"""
    # E: 締切10:40。出発地から直行しても到着10:20で余裕20分 < 30分
    stations = [
        _station(1.0, "C"),
        _station(2.0, "D"),
        _station(3.0, "E", deadline="10:40"),
    ]
    plan = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(CED_MATRIX), _profile("light"), max_stations=3,
    )
    names = [station.name for station in plan.order]
    assert "E" not in names
    assert "fewer_stations_than_requested" in plan.warnings


# --- プロファイル別の優先度 ---

# 出発地から等距離の2駅。締切も同じにして、加点要素だけで差が付くようにする
PAIR_MATRIX = _symmetric(
    {
        (ORIGIN, 1.0): 30.0,
        (ORIGIN, 2.0): 30.0,
        (1.0, 2.0): 30.0,
    }
)


def test_gourmet_plan_prefers_food_station() -> None:
    stations = [
        _station(1.0, "普通の駅"),
        _station(2.0, "グルメ駅", food=4),
    ]
    plan = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(PAIR_MATRIX), _profile("gourmet"), max_stations=1,
    )
    assert [station.name for station in plan.order] == ["グルメ駅"]


def test_rare_plan_prefers_high_revisit_difficulty() -> None:
    stations = [
        _station(1.0, "行きやすい駅", revisit=1),
        _station(2.0, "行きにくい駅", revisit=5),
    ]
    plan = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(PAIR_MATRIX), _profile("rare"), max_stations=1,
    )
    assert [station.name for station in plan.order] == ["行きにくい駅"]


# --- 制約まわり ---


def test_return_by_excludes_station_that_prevents_return() -> None:
    """帰着締切があるとき、寄ると戻れなくなる駅は選ばない。"""
    stations = [_station(1.0, "近い駅"), _station(2.0, "遠い駅")]
    matrix = _symmetric(
        {
            (ORIGIN, 1.0): 30.0,
            (ORIGIN, 2.0): 120.0,
            (1.0, 2.0): 120.0,
        }
    )
    # 09:00発・11:00帰着: 遠い駅は往復240分+滞在で間に合わない
    plan = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(matrix), _profile("max"), max_stations=2,
        return_to_origin=True, return_by="11:00",
    )
    assert [station.name for station in plan.order] == ["近い駅"]
    assert "fewer_stations_than_requested" in plan.warnings


def test_no_feasible_station_returns_warning() -> None:
    stations = [_station(1.0, "締切切れ駅", deadline="09:10")]
    matrix = _symmetric({(ORIGIN, 1.0): 60.0})
    plan = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(matrix), _profile("max"), max_stations=1,
    )
    assert plan.order == ()
    assert "no_feasible_station" in plan.warnings


def test_max_stations_is_respected() -> None:
    stations = [_station(float(i), f"駅{i}") for i in range(1, 5)]
    keys = [ORIGIN] + [float(i) for i in range(1, 5)]
    matrix = _symmetric(
        {(a, b): 10.0 for i, a in enumerate(keys) for b in keys[i + 1 :]}
    )
    plan = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(matrix), _profile("max"), max_stations=2,
    )
    assert len(plan.order) == 2


def test_light_profile_caps_station_count_at_four() -> None:
    """軽めプランは依頼が9駅でも最大4駅に抑える（DESIGN.md 13-2章）。"""
    stations = [_station(float(i), f"駅{i}") for i in range(1, 7)]
    keys = [ORIGIN] + [float(i) for i in range(1, 7)]
    matrix = _symmetric(
        {(a, b): 10.0 for i, a in enumerate(keys) for b in keys[i + 1 :]}
    )
    light = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(matrix), _profile("light"), max_stations=9,
    )
    maximum = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(matrix), _profile("max"), max_stations=9,
    )
    assert len(light.order) == 4
    assert len(maximum.order) == 6


def test_arrive_by_limits_last_arrival() -> None:
    """「最後の駅にHH:MM到着」制約: 締切には間に合っても到着締切を超える駅は組み込まない。"""
    stations = [_station(1.0, "近い駅"), _station(2.0, "遠い駅")]
    matrix = _symmetric(
        {
            (ORIGIN, 1.0): 30.0,
            (ORIGIN, 2.0): 60.0,
            (1.0, 2.0): 60.0,
        }
    )
    # 09:00発・最終到着10:30まで: 近い駅(9:30着)の後、遠い駅は10:45着になり超過
    plan = build_plan(
        ORIGIN, 0.0, "09:00", stations,
        _make_travel_fn(matrix), _profile("max"), max_stations=2,
        arrive_by="10:30",
    )
    assert [station.name for station in plan.order] == ["近い駅"]
    assert "fewer_stations_than_requested" in plan.warnings


def test_far_first_plan_starts_farthest_and_returns_homeward() -> None:
    """遠方から戻る: 一直線上の3駅を「遠い→中間→近い」の順で回る。"""
    stations = [
        _station(1.0, "近い駅"),
        _station(2.0, "中間の駅"),
        _station(3.0, "遠い駅"),
    ]
    # 一直線の配置: 出発地(0)—近(1)—中(2)—遠(3)、隣接30分
    matrix = _symmetric(
        {
            (ORIGIN, 1.0): 30.0,
            (ORIGIN, 2.0): 60.0,
            (ORIGIN, 3.0): 90.0,
            (1.0, 2.0): 30.0,
            (1.0, 3.0): 60.0,
            (2.0, 3.0): 30.0,
        }
    )
    plan = build_plan(
        ORIGIN, 0.0, "08:00", stations,
        _make_travel_fn(matrix), _profile("far_first"), max_stations=3,
    )
    assert [station.name for station in plan.order] == ["遠い駅", "中間の駅", "近い駅"]


def test_max_profile_rejects_arrival_with_less_than_ten_minutes_margin() -> None:
    """締切ちょうど到着（余裕0〜9分）は、min_margin_min=10により実行可能と判定しない（Issue #71）。"""
    # 出発09:00+30分移動=09:30着。締切09:39なら余裕9分で不可、09:40なら余裕10分で可
    matrix = _symmetric({(ORIGIN, 1.0): 30.0})
    too_tight = build_plan(
        ORIGIN, 0.0, "09:00", [_station(1.0, "駅", deadline="09:39")],
        _make_travel_fn(matrix), _profile("max"), max_stations=1,
    )
    assert too_tight.order == ()
    assert "no_feasible_station" in too_tight.warnings

    just_enough = build_plan(
        ORIGIN, 0.0, "09:00", [_station(1.0, "駅", deadline="09:40")],
        _make_travel_fn(matrix), _profile("max"), max_stations=1,
    )
    assert [station.name for station in just_enough.order] == ["駅"]


def test_far_first_respects_deadline_on_far_anchor() -> None:
    """最遠の駅が締切に間に合わない場合は、次に遠い実行可能な駅が先頭になる。"""
    stations = [
        _station(1.0, "近い駅"),
        _station(3.0, "遠すぎる駅", deadline="09:20"),  # 90分先なので9:30着では間に合わない
        _station(2.0, "遠い駅"),
    ]
    matrix = _symmetric(
        {
            (ORIGIN, 1.0): 30.0,
            (ORIGIN, 2.0): 60.0,
            (ORIGIN, 3.0): 90.0,
            (1.0, 2.0): 30.0,
            (1.0, 3.0): 60.0,
            (2.0, 3.0): 30.0,
        }
    )
    plan = build_plan(
        ORIGIN, 0.0, "08:00", stations,
        _make_travel_fn(matrix), _profile("far_first"), max_stations=3,
    )
    assert plan.order[0].name == "遠い駅"
    assert "遠すぎる駅" not in [station.name for station in plan.order]
