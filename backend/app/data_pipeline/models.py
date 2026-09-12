"""道の駅データモデル定義。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Facilities(BaseModel):
    """施設有無フラグ（GML由来。新規登録駅はNoneのまま）"""
    atm: bool = False
    baby_bed: bool = False
    restaurant: bool = False
    coffee_shop: bool = False
    accommodation: bool = False
    spa: bool = False
    camping: bool = False
    park: bool = False
    observation_tower: bool = False
    museum: bool = False
    gas_station: bool = False
    ev_charge: bool = False
    wifi: bool = False
    shower: bool = False
    experience: bool = False
    visitor_info: bool = False
    accessible_restroom: bool = False
    shop: bool = False


class MichiNoEki(BaseModel):
    """道の駅1件のデータモデル。

    station_id: GMLのgml:id（例: P35_123）。新規登録駅はNone。
    lat/lon: GMLから補完。新規登録駅はNone。
    facilities: GMLから補完。新規登録駅はNone。
    """
    station_id: str | None = None
    name: str
    pref: str
    address: str = ""
    url: str = ""
    registration: str = ""
    reg_date: str = ""
    lat: float | None = None
    lon: float | None = None
    facilities: Facilities | None = None

    @property
    def has_coordinates(self) -> bool:
        return self.lat is not None and self.lon is not None
