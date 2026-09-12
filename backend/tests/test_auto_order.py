from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.route.auto_order import (  # noqa: E402
    OrderableStation,
    _total_travel_minutes,
    auto_order_stations,
)

# テストでは緯度を「駅の識別子」として使い、座標ペア→分の固定表で移動時間を引く
# （test_planner.pyと同じ手法）。
ORIGIN = 0.0


def _make_travel_fn(matrix: dict[tuple[float, float], float]):
    def travel_fn(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
        if from_lat == to_lat:
            return 0.0
        return matrix[(from_lat, to_lat)]

    return travel_fn


def _symmetric(matrix: dict[tuple[float, float], float]) -> dict[tuple[float, float], float]:
    return matrix | {(b, a): minutes for (a, b), minutes in matrix.items()}


def _station(key: float) -> OrderableStation:
    return OrderableStation(station_id=int(key), lat=key, lon=0.0)


# --- 出発地(0)-A(1)-B(2)-C(3)が一直線上に並ぶケース ---
# ユーザーがC,A,Bの順で選んでも、出発地から近い順A→B→Cの方が総移動時間が短い
LINE_MATRIX = _symmetric(
    {
        (ORIGIN, 1.0): 10.0,  # 出発地→A
        (ORIGIN, 2.0): 20.0,  # 出発地→B
        (ORIGIN, 3.0): 30.0,  # 出発地→C
        (1.0, 2.0): 10.0,  # A→B
        (1.0, 3.0): 20.0,  # A→C
        (2.0, 3.0): 10.0,  # B→C
    }
)


def test_auto_order_includes_all_selected_stations() -> None:
    """選択順が悪くても、全駅を必ず含む（間引かれない）。"""
    selected = [_station(3.0), _station(1.0), _station(2.0)]  # C, A, B
    ordered = auto_order_stations(ORIGIN, 0.0, selected, _make_travel_fn(LINE_MATRIX))
    assert {station.station_id for station in ordered} == {1, 2, 3}
    assert len(ordered) == 3


def test_auto_order_two_opt_reduces_total_travel_time() -> None:
    """C,A,Bという選択順より、出発地から近い順A,B,Cの方が総移動時間が短く採用される。"""
    selected = [_station(3.0), _station(1.0), _station(2.0)]  # C, A, B
    travel_fn = _make_travel_fn(LINE_MATRIX)
    ordered = auto_order_stations(ORIGIN, 0.0, selected, travel_fn)
    assert [station.station_id for station in ordered] == [1, 2, 3]

    optimized_total = _total_travel_minutes(ORIGIN, 0.0, ordered, travel_fn, False)
    naive_total = _total_travel_minutes(ORIGIN, 0.0, selected, travel_fn, False)
    assert optimized_total == 30.0
    assert optimized_total < naive_total  # 選択順のまま(60分)より改善する


def test_auto_order_keeps_far_station_with_no_deadline_rejection() -> None:
    """極端に遠い駅が混ざっていても、締切という概念自体がないため必ず含まれる。

    auto_order.pyは締切による実行可能性チェックを一切行わない（Issue #78の設計方針）。
    """
    far_station = OrderableStation(station_id=99, lat=100.0, lon=0.0)
    matrix = dict(LINE_MATRIX)
    for key in (1.0, 2.0, 3.0):
        matrix[(ORIGIN, 100.0)] = 999.0
        matrix[(100.0, key)] = 999.0
    matrix = _symmetric(matrix)
    selected = [_station(3.0), _station(1.0), _station(2.0), far_station]
    ordered = auto_order_stations(ORIGIN, 0.0, selected, _make_travel_fn(matrix))
    assert {station.station_id for station in ordered} == {1, 2, 3, 99}


def test_auto_order_two_stations_with_asymmetric_costs_can_reverse() -> None:
    """2駅でも2-optを試す: 移動時間が非対称な場合、反転で改善するなら採用する。

    最近傍法はA（出発地から5分）を先に選ぶが、A→Bが50分と高い。
    B→Aは1分なのでB→Aの順（6+1=7分）の方が総移動時間が短い。
    """
    # 非対称な固定表（_symmetricを使わない）
    asymmetric_matrix = {
        (ORIGIN, 1.0): 5.0,  # 出発地→A
        (ORIGIN, 2.0): 6.0,  # 出発地→B
        (1.0, 2.0): 50.0,  # A→B（行きは山越えで高い、という想定）
        (2.0, 1.0): 1.0,  # B→A
    }
    travel_fn = _make_travel_fn(asymmetric_matrix)
    selected = [_station(1.0), _station(2.0)]
    ordered = auto_order_stations(ORIGIN, 0.0, selected, travel_fn)
    assert [station.station_id for station in ordered] == [2, 1]
    assert _total_travel_minutes(ORIGIN, 0.0, ordered, travel_fn, False) == 7.0


# --- 出発地からの距離が偏った三角形ケース: return_to_origin考慮の検証 ---
# A(1)は出発地から近い(1)。B(2)は中間(5)。C(3)は出発地からとても遠い(50)。
# 帰路を考えない場合はB→A→Cの順(最後にCへ行って終わり)が最短だが、
# 帰路まで含めるとCへの帰り道(50)が高くつくため、A→C→Bの順（Bで終わって帰る）が最適になる
TRIANGLE_MATRIX = _symmetric(
    {
        (ORIGIN, 1.0): 1.0,  # 出発地→A
        (ORIGIN, 2.0): 5.0,  # 出発地→B
        (ORIGIN, 3.0): 50.0,  # 出発地→C
        (1.0, 2.0): 1.0,  # A→B
        (1.0, 3.0): 4.0,  # A→C
        (2.0, 3.0): 45.0,  # B→C
    }
)


def test_auto_order_without_return_prefers_shortest_forward_path() -> None:
    """帰路なしの場合は往路の総移動時間だけを最小化する（B→A→Cが最短=10分）。"""
    selected = [_station(1.0), _station(2.0), _station(3.0)]
    travel_fn = _make_travel_fn(TRIANGLE_MATRIX)
    ordered = auto_order_stations(ORIGIN, 0.0, selected, travel_fn, return_to_origin=False)
    assert [station.station_id for station in ordered] == [2, 1, 3]
    assert _total_travel_minutes(ORIGIN, 0.0, ordered, travel_fn, False) == 10.0


def test_auto_order_with_return_to_origin_considers_return_leg() -> None:
    """帰路ありの場合は帰路区間も評価に含めるため、往路のみ最短とは異なる順序(B→C→A)が選ばれる。

    往路のみなら最短はB→A→C(10分)だが、Cからの帰路(50分)が高くつくため
    帰路込みでは合計55分のB→C→A(id=2,3,1)の方が有利になる。
    """
    selected = [_station(1.0), _station(2.0), _station(3.0)]
    travel_fn = _make_travel_fn(TRIANGLE_MATRIX)
    ordered = auto_order_stations(ORIGIN, 0.0, selected, travel_fn, return_to_origin=True)
    assert [station.station_id for station in ordered] == [2, 3, 1]
    total_with_return = _total_travel_minutes(ORIGIN, 0.0, ordered, travel_fn, True)
    assert total_with_return == 55.0

    # 帰路を考えない場合の最適順(B,A,C)をそのまま帰路込みで評価すると、より高くつく
    forward_only_best = [_station(2.0), _station(1.0), _station(3.0)]
    forward_only_round_trip = _total_travel_minutes(
        ORIGIN, 0.0, forward_only_best, travel_fn, True
    )
    assert total_with_return < forward_only_round_trip
