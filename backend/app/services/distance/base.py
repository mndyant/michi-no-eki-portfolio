from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TravelEstimate:
    """2地点間の距離と自動車での所要時間の見積り。"""

    distance_km: float
    duration_min: float
    source: str


class DistanceProvider(ABC):
    """距離取得方法を差し替えるための共通インターフェース。"""

    @abstractmethod
    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        """2地点間の移動距離と所要時間を返す。"""
