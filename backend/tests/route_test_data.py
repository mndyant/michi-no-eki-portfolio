from __future__ import annotations

from datetime import date

from app.models.station import Station


def make_station(
    station_id: int,
    name: str,
    lat: float | None,
    lon: float | None,
    stamp_end: str = "17:00",
    business_hours: str = "{}",
    closed_days: str = "",
) -> Station:
    """ルートAPIテスト用に、必須項目をそろえた道の駅を作る。

    business_hours/closed_daysはIssue #71の営業時間・定休日制約テスト用に上書きできる。
    """
    return Station(
        id=station_id,
        station_id=f"TEST_{station_id:03d}",
        name=name,
        pref="大阪府",
        city=None,
        address=None,
        lat=lat,
        lon=lon,
        official_url=None,
        business_hours=business_hours,
        stamp_start="09:00",
        stamp_end=stamp_end,
        closed_days=closed_days,
        visited=False,
        visited_date=None,
        stay_time_min_default=15,
        facility_scale="small",
        good_for_lunch=False,
        good_for_sweets=False,
        good_for_souvenir=False,
        has_spa=False,
        scenery_score=None,
        is_mountainous=False,
        revisit_difficulty_score=1,
        revisit_difficulty_reason="テスト",
        cluster_id=None,
        reputation_items="[]",
        local_specialty="[]",
        seasonal_specialty="[]",
        user_memo=None,
        source="test",
        last_verified_at=date(2026, 7, 11),
    )
