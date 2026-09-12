from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class RouteOrigin(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    label: str | None = None


def _validate_iso_date(value: str) -> str:
    """"YYYY-MM-DD" 形式であることを確認する共通バリデータ（Issue #71の訪問日）。"""
    from datetime import date

    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("訪問日はYYYY-MM-DD形式で指定してください") from exc
    return value


class ManualRouteRequest(BaseModel):
    origin: RouteOrigin
    # fixed: departure_timeから順方向に計算 / latest: 締切から最遅出発時刻を逆算（Issue #46）
    departure_mode: Literal["fixed", "latest"] = "fixed"
    # fixedモードでは必須。latestモードでは無視される（サーバー側で逆算した時刻を使う）
    departure_time: str | None = None
    station_ids: list[int] = Field(min_length=1)
    stay_overrides: dict[int, int] = Field(default_factory=dict)
    return_to_origin: bool = False
    # 帰着締切。latestモードの逆算制約として使う（帰着ありの場合のみ効く）
    return_by: str | None = None
    # 高速道路を使う区間のインデックス（0=出発地→1駅目、i=i駅目→i+1駅目、駅数=帰路）
    highway_legs: list[int] = Field(default_factory=list)
    # 訪問日（YYYY-MM-DD、任意）。指定時のみ曜日別営業時間・定休日を評価する（Issue #71）。
    # 未指定なら従来通り曜日を考慮しない（後方互換）
    visit_date: str | None = None
    # trueの場合、station_idsの並び順ではなくサーバー側で最適な訪問順に並べ替える
    # （最近傍法+2-opt、Issue #78）。選択した駅は全て含めたまま順序だけを変える。
    # 未指定時はFalse＝従来通り選択順をそのまま使う（後方互換）
    auto_order: bool = False

    @field_validator("departure_time", "return_by")
    @classmethod
    def validate_time_fields(cls, value: str | None) -> str | None:
        """時・分だけの24時間表記であることを確認する。"""
        if value is None:
            return None
        from datetime import datetime

        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("時刻はHH:MM形式で指定してください") from exc
        return value

    @field_validator("visit_date")
    @classmethod
    def validate_visit_date(cls, value: str | None) -> str | None:
        return _validate_iso_date(value) if value is not None else None

    @field_validator("stay_overrides")
    @classmethod
    def validate_stay_overrides(cls, value: dict[int, int]) -> dict[int, int]:
        if any(minutes < 0 for minutes in value.values()):
            raise ValueError("滞在時間は0分以上で指定してください")
        return value

    @model_validator(mode="after")
    def validate_departure_time_required(self) -> "ManualRouteRequest":
        if self.departure_mode == "fixed" and self.departure_time is None:
            raise ValueError("departure_mode=fixedの場合はdeparture_timeが必須です")
        return self

    @model_validator(mode="after")
    def validate_auto_order_combinations(self) -> "ManualRouteRequest":
        """auto_orderと両立しない指定を入口で拒否する（Issue #78レビュー対応）。

        - highway_legs: 区間インデックスは並び順に対する指定のため、サーバー側で
          順序が変わると意味が壊れる。並べ替え後の順序に対して指定し直すべきなので併用不可
        - departure_mode=latest: 順序最適化は滞在時間・締切・帰着締切を考慮しないため、
          逆算と組み合わせると実行不可の誤判定や必要以上に早い出発時刻になり得る。
          締切を考慮した順序戦略と併せてIssue #83で対応予定。当面は併用を拒否する
        """
        if self.auto_order and self.highway_legs:
            raise ValueError(
                "自動最適順（auto_order）と高速道路区間（highway_legs）は併用できません。"
                "並べ替え後のルートに対して高速区間を指定してください"
            )
        if self.auto_order and self.departure_mode == "latest":
            raise ValueError("出発時刻の逆算と自動最適順の併用は未対応です")
        return self


def _validate_hhmm(value: str) -> str:
    """時・分だけの24時間表記であることを確認する共通バリデータ。"""
    from datetime import datetime

    try:
        datetime.strptime(value, "%H:%M")
    except ValueError as exc:
        raise ValueError("時刻はHH:MM形式で指定してください") from exc
    return value


# 方面フィルタで指定できる8方位（DESIGN.md 13-2章）
DIRECTION_KEYS = ("北", "北東", "東", "南東", "南", "南西", "西", "北西")


class SuggestRouteRequest(BaseModel):
    """自動ルート提案の入力条件（フェーズ3・13-2章でv2拡張）。

    駅数は入力でなく結果。時間（last_arrival_by / return_by）・地域（prefs / cluster_ids）・
    方面（directions）で絞り、何駅回れるかは各プランが返す。
    """

    origin: RouteOrigin
    departure_time: str
    max_stations: int = Field(default=9, ge=1, le=9)
    prefs: list[str] = Field(default_factory=list)
    cluster_ids: list[int] = Field(default_factory=list)
    include_visited: bool = False
    return_to_origin: bool = False
    return_by: str | None = None
    # 最後の駅への到着締切（例: 17:30）。全駅の到着がこれ以前になる
    last_arrival_by: str | None = None
    # 出発地から見た方面（8方位、複数可）。±45°の扇形で候補を絞る
    directions: list[str] = Field(default_factory=list)
    # 全区間で高速道路を使う想定で見積もる
    use_highway: bool = False
    # 自然文でのルート希望（任意、フェーズ5）。既に指定済みの構造化条件は上書きしない。
    # 例: 「南方面を回って16:30までに最終駅に着きたい」
    free_text: str | None = None
    # 訪問日（YYYY-MM-DD、任意）。指定時のみ曜日別営業時間・定休日を評価する（Issue #71）
    visit_date: str | None = None

    @field_validator("departure_time")
    @classmethod
    def validate_departure_time(cls, value: str) -> str:
        return _validate_hhmm(value)

    @field_validator("return_by", "last_arrival_by")
    @classmethod
    def validate_optional_time(cls, value: str | None) -> str | None:
        return _validate_hhmm(value) if value is not None else None

    @field_validator("visit_date")
    @classmethod
    def validate_visit_date(cls, value: str | None) -> str | None:
        return _validate_iso_date(value) if value is not None else None

    @field_validator("directions")
    @classmethod
    def validate_directions(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if item not in DIRECTION_KEYS]
        if invalid:
            raise ValueError(
                f"方面は{'/'.join(DIRECTION_KEYS)}のいずれかで指定してください: {invalid}"
            )
        return value


class RouteStopRead(BaseModel):
    station_id: int
    name: str
    arrival: str
    departure: str
    stay_min: int
    stamp_deadline: str
    margin_min: int
    warnings: list[str]


class RouteTotals(BaseModel):
    travel_min: int
    distance_km: float
    stay_min: int


class ManualRouteResponse(BaseModel):
    stops: list[RouteStopRead]
    totals: RouteTotals
    google_maps_url: str
    warnings: list[str]
    # 実際に計算へ使った出発時刻。逆算モード（departure_mode=latest）の結果表示に使う
    departure_time: str


class WhatIfRouteRequest(ManualRouteRequest):
    """What-ifシミュレーションの入力。手動ルートの条件に変化分を加える（フェーズ4）。

    departure_time は必須（親のlatestモードは使わず、常に確定時刻から再計算する）。
    return_by は親クラスから継承。
    """

    delay_min: int = Field(default=0, ge=0, le=24 * 60)
    excluded_station_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_whatif_departure_time(self) -> "WhatIfRouteRequest":
        if self.departure_time is None:
            raise ValueError("What-ifではdeparture_timeが必須です")
        return self


class WhatIfStopRead(RouteStopRead):
    """What-if結果の立ち寄り駅。最遅出発時刻の情報を追加で持つ。"""

    # この時刻までに出発すれば、以降の駅の締切（と帰着締切）に間に合う。制約がなければNone
    latest_departure: str | None
    # 最遅出発時刻 - 実際の出発時刻。負なら以降のどこかで間に合わない
    departure_slack_min: int | None


class WhatIfRouteResponse(BaseModel):
    stops: list[WhatIfStopRead]
    totals: RouteTotals
    google_maps_url: str
    warnings: list[str]
    applied_delay_min: int
    excluded_station_ids: list[int]


class SuggestedPlanRead(BaseModel):
    """自動提案された1プラン分の結果。"""

    key: str
    label: str
    description: str
    station_ids: list[int]
    stops: list[RouteStopRead]
    totals: RouteTotals
    google_maps_url: str
    warnings: list[str]
    # 行程の終了時刻。帰着ありなら出発地への帰着時刻、なしなら最終駅の出発時刻
    finish_time: str
    # 実際の計算結果（駅数・終了時刻・方面希望との一致）を反映した一言コメント（フェーズ5）
    reason: str


class SuggestRouteResponse(BaseModel):
    plans: list[SuggestedPlanRead]
    candidate_count: int
    warnings: list[str]
