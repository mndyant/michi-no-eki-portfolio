# stations入力スキーマの境界チェック（DB不要の純粋バリデーションテスト）。
# 背景: stamp_start/stamp_endに"HH:MM"以外の値がDBへ入ると、その駅を含む
# /api/routes/manual・/what-if・/suggest がstrptimeのValueError（=500）で全滅する。
# 負の滞在時間は時刻表で「出発が到着より前」になる（レビューで再現済み）。
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.station import StationCreate, StationUpdate  # noqa: E402


def _create_payload(**overrides: object) -> dict:
    payload = {
        "station_id": "TEST_001",
        "name": "テスト駅",
        "pref": "大阪府",
        "stamp_start": "09:00",
        "stamp_end": "17:00",
        "facility_scale": "small",
        "revisit_difficulty_score": 1,
        "revisit_difficulty_reason": "テスト",
        "source": "test",
        "last_verified_at": date(2026, 7, 11),
    }
    payload.update(overrides)
    return payload


def test_create_accepts_valid_stamp_times() -> None:
    station = StationCreate(**_create_payload())
    assert station.stamp_end == "17:00"


@pytest.mark.parametrize("bad_time", ["営業時間確認中", "25:00", "17時", "17:00-18:00", ""])
def test_create_rejects_invalid_stamp_end(bad_time: str) -> None:
    with pytest.raises(ValidationError):
        StationCreate(**_create_payload(stamp_end=bad_time))


def test_create_rejects_invalid_stamp_start() -> None:
    with pytest.raises(ValidationError):
        StationCreate(**_create_payload(stamp_start="9am"))


def test_create_rejects_negative_stay_time() -> None:
    with pytest.raises(ValidationError):
        StationCreate(**_create_payload(stay_time_min_default=-30))


def test_update_rejects_invalid_stamp_end() -> None:
    with pytest.raises(ValidationError):
        StationUpdate(stamp_end="営業時間確認中")


def test_update_rejects_negative_stay_time() -> None:
    with pytest.raises(ValidationError):
        StationUpdate(stay_time_min_default=-1)


def test_update_allows_valid_partial_fields() -> None:
    update = StationUpdate(stamp_end="16:30", stay_time_min_default=0)
    assert update.stamp_end == "16:30"
    assert update.stay_time_min_default == 0


def test_update_allows_omitted_time_fields() -> None:
    # 部分更新でNone（未指定）のままなら検証は走らない
    update = StationUpdate(user_memo="メモだけ更新")
    assert update.stamp_start is None
    assert update.stamp_end is None
