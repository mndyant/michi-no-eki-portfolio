from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.services.route.planner import TravelMinutesFn

# 手動ルートの訪問順自動並べ替え（Issue #78）。
#
# フェーズ3の自動提案（suggest.py）とは目的が異なる: あちらは「何駅回れるか」を
# 締切等の制約で絞り込みながら決めるが、こちらはユーザーが/routes/newで明示的に
# 選んだ駅を一切間引かず、その全駅を対象に「訪問する順番」だけを最適化する。
#
# 手順:
#   1. 出発地から最近傍法（nearest neighbor）で初期順序を作る（全駅を必ず含む）
#   2. 2-optで総移動時間を最小化する（締切の実行可能性チェックはしない。
#      全駅を含めることが最優先で、締切に間に合うかどうかは既存のtimetable生成の
#      警告システムに委ねる）
#
# 得られた順序はそのまま既存のcompute_route（Issue #71の営業時間評価・
# Issue #73の山間係数を含む）に渡され、通常通り警告が付与される。


@dataclass(frozen=True, slots=True)
class OrderableStation:
    """並べ替えに必要な座標情報だけを持つ、駅の最小表現。"""

    station_id: int
    lat: float
    lon: float


def _nearest_neighbor_order(
    origin_lat: float,
    origin_lon: float,
    stations: Sequence[OrderableStation],
    travel_min_fn: TravelMinutesFn,
) -> list[OrderableStation]:
    """現在地から最も近い未訪問駅を順に選んでいく貪欲法。全駅を必ず含む。"""
    remaining = list(stations)
    ordered: list[OrderableStation] = []
    current_lat, current_lon = origin_lat, origin_lon
    while remaining:
        nearest = min(
            remaining,
            key=lambda station: travel_min_fn(
                current_lat, current_lon, station.lat, station.lon
            ),
        )
        ordered.append(nearest)
        remaining.remove(nearest)
        current_lat, current_lon = nearest.lat, nearest.lon
    return ordered


def _total_travel_minutes(
    origin_lat: float,
    origin_lon: float,
    order: Sequence[OrderableStation],
    travel_min_fn: TravelMinutesFn,
    return_to_origin: bool,
) -> float:
    """出発地からこの順で全駅を回ったときの総移動時間（分）。"""
    current_lat, current_lon = origin_lat, origin_lon
    total = 0.0
    for station in order:
        total += travel_min_fn(current_lat, current_lon, station.lat, station.lon)
        current_lat, current_lon = station.lat, station.lon
    if return_to_origin and order:
        total += travel_min_fn(current_lat, current_lon, origin_lat, origin_lon)
    return total


def _two_opt_improve(
    origin_lat: float,
    origin_lon: float,
    order: list[OrderableStation],
    travel_min_fn: TravelMinutesFn,
    return_to_origin: bool,
) -> list[OrderableStation]:
    """2-opt: 部分区間を反転して総移動時間が短くなる限り採用する。

    planner.pyの_two_opt_improveと違い、締切による実行可能性チェックは行わない。
    全駅を含めることが最優先のため、総移動時間が短くなれば常に採用する。
    2駅でも試す: 移動時間が非対称（行きと帰りで異なる）な場合、全体反転で改善することがある。
    """
    if len(order) < 2:
        return order
    best_order = order
    best_total = _total_travel_minutes(
        origin_lat, origin_lon, best_order, travel_min_fn, return_to_origin
    )
    improved = True
    while improved:
        improved = False
        for i in range(len(best_order) - 1):
            for j in range(i + 1, len(best_order)):
                trial = best_order[:i] + best_order[i : j + 1][::-1] + best_order[j + 1 :]
                total = _total_travel_minutes(
                    origin_lat, origin_lon, trial, travel_min_fn, return_to_origin
                )
                if total < best_total:
                    best_order, best_total = trial, total
                    improved = True
        # 改善が続く限り繰り返す（手動ルートは駅数が少ないため計算量は小さい）
    return best_order


def auto_order_stations(
    origin_lat: float,
    origin_lon: float,
    stations: Sequence[OrderableStation],
    travel_min_fn: TravelMinutesFn,
    return_to_origin: bool = False,
) -> list[OrderableStation]:
    """最近傍法で初期順序を作り、2-optで総移動時間を最小化した訪問順を返す。

    ユーザーが選んだ駅は1件も間引かず、常に全駅を含んだ順序を返す。
    """
    if len(stations) <= 1:
        return list(stations)
    initial_order = _nearest_neighbor_order(origin_lat, origin_lon, stations, travel_min_fn)
    return _two_opt_improve(origin_lat, origin_lon, initial_order, travel_min_fn, return_to_origin)
