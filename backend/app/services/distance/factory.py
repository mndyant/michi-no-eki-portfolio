from __future__ import annotations

import os

from app.services.distance.base import DistanceProvider
from app.services.distance.haversine_provider import HaversineProvider
from app.services.distance.osrm_provider import OSRMProvider


def get_distance_provider() -> DistanceProvider:
    """環境変数で距離取得方法を選ぶ。不明値でも安全な既定値を使う。"""
    provider_name = os.getenv("DISTANCE_PROVIDER", "haversine").strip().lower()
    if provider_name == "osrm":
        return OSRMProvider()
    return HaversineProvider()
