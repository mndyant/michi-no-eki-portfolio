from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from app.services.distance.base import DistanceProvider, TravelEstimate

EARTH_RADIUS_KM = 6371.0
ROAD_FACTOR = 1.3
AVERAGE_SPEED_KMH = 40.0


def haversine_km(from_lat: float, from_lon: float, to_lat: float, to_lon: float) -> float:
    """緯度経度から地球表面上の直線距離を計算する。"""
    lat1, lon1, lat2, lon2 = map(radians, (from_lat, from_lon, to_lat, to_lon))
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(value))


class HaversineProvider(DistanceProvider):
    """外部APIを使わず、直線距離から道路移動を概算するプロバイダ。"""

    def get_travel(
        self, from_lat: float, from_lon: float, to_lat: float, to_lon: float
    ) -> TravelEstimate:
        distance_km = haversine_km(from_lat, from_lon, to_lat, to_lon) * ROAD_FACTOR
        duration_min = distance_km / AVERAGE_SPEED_KMH * 60
        return TravelEstimate(
            distance_km=distance_km,
            duration_min=duration_min,
            source="haversine",
        )
