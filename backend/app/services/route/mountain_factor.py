from __future__ import annotations

from app.services.distance.base import TravelEstimate

# 山間部区間の道路係数補正（Issue #73）。
# OSRM実道路距離との比較検証で、道路係数1.3は都市部でほぼ正確（実測1.16〜1.38）だが、
# 山間部（Station.is_mountainous）は1.55〜1.94相当必要と判明した。区間のどちらかの
# 端点が山間駅なら、既存の1.3ベース見積りを1.6相当に底上げする。
#
# 実装場所をdistanceプロバイダでなくroute層に置く理由: プロバイダは座標しか受け取らず
# 駅の山間部フラグを知らないため。haversine_provider.ROAD_FACTOR(1.3)を直接importせず
# 定数として再掲するのは、distance層とroute層の依存方向（route→distance）を保つため。
MOUNTAIN_ROAD_FACTOR = 1.6
FLAT_ROAD_FACTOR = 1.3
MOUNTAIN_CORRECTION_RATIO = MOUNTAIN_ROAD_FACTOR / FLAT_ROAD_FACTOR


def apply_mountain_correction(estimate: TravelEstimate, is_mountainous: bool) -> TravelEstimate:
    """区間の端点が山間駅なら、haversine由来の見積りを道路係数1.6相当に補正する。

    OSRM等、実道路距離を返すプロバイダの結果（source != "haversine"）は既に正確なため補正しない。
    """
    if not is_mountainous or estimate.source != "haversine":
        return estimate
    return TravelEstimate(
        distance_km=estimate.distance_km * MOUNTAIN_CORRECTION_RATIO,
        duration_min=estimate.duration_min * MOUNTAIN_CORRECTION_RATIO,
        source=f"{estimate.source}+mountain",
    )
