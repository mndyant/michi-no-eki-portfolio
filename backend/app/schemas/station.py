# stations APIのリクエスト/レスポンス用Pydanticスキーマ
# DBではJSON項目（business_hours等）をTEXT列に文字列で保存しているが、
# API上ではdict/listとして扱いやすくするため、ここではJSON型として定義する
# （文字列⇔JSONの変換はapp/services/station_service.pyが担当する）
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class StationBase(BaseModel):
    """作成・更新・レスポンスで共通する項目"""

    station_id: str
    name: str
    pref: str
    city: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    official_url: str | None = None
    business_hours: dict[str, str] = Field(default_factory=dict)
    stamp_start: str
    stamp_end: str
    closed_days: str = ""
    stay_time_min_default: int = 15
    facility_scale: str
    good_for_lunch: bool = False
    good_for_sweets: bool = False
    good_for_souvenir: bool = False
    has_spa: bool = False
    scenery_score: int | None = None
    is_mountainous: bool = False
    revisit_difficulty_score: int
    revisit_difficulty_reason: str
    cluster_id: int | None = None
    reputation_items: list = Field(default_factory=list)
    local_specialty: list = Field(default_factory=list)
    seasonal_specialty: list = Field(default_factory=list)
    user_memo: str | None = None
    source: str
    last_verified_at: date


class StationCreate(StationBase):
    """POST /api/stations 用。基本CRUD確認用（通常はシード投入で足りる）"""


class StationUpdate(BaseModel):
    """PUT /api/stations/{id} 用。渡された項目だけ上書きする（部分更新）"""

    station_id: str | None = None
    name: str | None = None
    pref: str | None = None
    city: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    official_url: str | None = None
    business_hours: dict[str, str] | None = None
    stamp_start: str | None = None
    stamp_end: str | None = None
    closed_days: str | None = None
    stay_time_min_default: int | None = None
    facility_scale: str | None = None
    good_for_lunch: bool | None = None
    good_for_sweets: bool | None = None
    good_for_souvenir: bool | None = None
    has_spa: bool | None = None
    scenery_score: int | None = None
    is_mountainous: bool | None = None
    revisit_difficulty_score: int | None = None
    revisit_difficulty_reason: str | None = None
    cluster_id: int | None = None
    reputation_items: list | None = None
    local_specialty: list | None = None
    seasonal_specialty: list | None = None
    user_memo: str | None = None
    source: str | None = None
    last_verified_at: date | None = None


class StationRead(StationBase):
    """一覧・詳細のレスポンス用"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    visited: bool
    visited_date: date | None = None


class StationVisitUpdate(BaseModel):
    """PATCH /api/stations/{id}/visit 用。訪問済みフラグと訪問日をまとめて更新する"""

    visited: bool
    visited_date: date | None = None
