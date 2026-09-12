from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from urllib.parse import urlencode

GOOGLE_MAPS_DIR_URL = "https://www.google.com/maps/dir/"
MAX_WAYPOINTS = 9


@dataclass(frozen=True, slots=True)
class MapPoint:
    lat: float
    lon: float
    label: str | None = None


def _coordinate(point: MapPoint) -> str:
    """URLが長くなり過ぎない精度で緯度経度を文字列化する。"""
    return f"{point.lat:.6f},{point.lon:.6f}"


def build_google_maps_url(
    origin: MapPoint,
    stations: Sequence[MapPoint],
    return_to_origin: bool = False,
) -> tuple[str, list[str]]:
    """訪問順を保ったGoogle Maps経路URLと警告を返す。"""
    if not stations:
        raise ValueError("訪問駅を1件以上指定してください")

    destination = origin if return_to_origin else stations[-1]
    waypoint_candidates = list(stations if return_to_origin else stations[:-1])
    warnings: list[str] = []
    if len(waypoint_candidates) > MAX_WAYPOINTS:
        waypoint_candidates = waypoint_candidates[:MAX_WAYPOINTS]
        warnings.append("waypoints_truncated")

    params = {
        "api": "1",
        "origin": _coordinate(origin),
        "destination": _coordinate(destination),
    }
    if waypoint_candidates:
        params["waypoints"] = "|".join(_coordinate(point) for point in waypoint_candidates)
    return f"{GOOGLE_MAPS_DIR_URL}?{urlencode(params, safe=',|')}", warnings
