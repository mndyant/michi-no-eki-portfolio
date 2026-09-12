from __future__ import annotations

import requests

from app.services.distance.base import DistanceProvider, TravelEstimate
from app.services.distance.haversine_provider import HaversineProvider

OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"


class OSRMProvider(DistanceProvider):
    """OSRMの公開デモを利用し、利用不能ならオフライン概算へ戻す。"""

    def __init__(self, fallback: DistanceProvider | None = None) -> None:
        self.fallback = fallback or HaversineProvider()

    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        coordinates = f"{from_lon},{from_lat};{to_lon},{to_lat}"
        try:
            response = requests.get(
                f"{OSRM_ROUTE_URL}/{coordinates}",
                params={"overview": "false"},
                timeout=5,
            )
            response.raise_for_status()
            route = response.json()["routes"][0]
            return TravelEstimate(
                distance_km=float(route["distance"]) / 1000,
                duration_min=float(route["duration"]) / 60,
                source="osrm",
            )
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            # 公開デモには稼働保証がないため、通信・応答形式の問題では処理を止めない。
            return self.fallback.get_travel(from_lat, from_lon, to_lat, to_lon)


# Pythonでは略語を大文字にしたOSRMProviderを正式名とし、旧表記も互換用に残す。
OsrmProvider = OSRMProvider
