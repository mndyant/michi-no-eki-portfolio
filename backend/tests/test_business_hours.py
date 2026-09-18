from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.route.business_hours import (  # noqa: E402
    is_closed_day,
    resolve_open_time,
    weekday_code,
)


def test_weekday_code_matches_iso_weekday() -> None:
    # 2026-07-16は木曜日
    assert weekday_code(date(2026, 7, 16)) == "thu"
    # 2026-07-13は月曜日
    assert weekday_code(date(2026, 7, 13)) == "mon"


def test_resolve_open_time_extracts_start_of_range() -> None:
    hours = '{"mon": "09:00-17:00", "tue": "10:00-16:00"}'
    assert resolve_open_time(hours, "mon") == "09:00"
    assert resolve_open_time(hours, "tue") == "10:00"


def test_resolve_open_time_returns_none_when_weekday_missing() -> None:
    assert resolve_open_time('{"mon": "09:00-17:00"}', "sun") is None


def test_resolve_open_time_returns_none_for_empty_or_invalid_json() -> None:
    assert resolve_open_time("{}", "mon") is None
    assert resolve_open_time("not json", "mon") is None


def test_resolve_open_time_returns_none_for_unparsable_start() -> None:
    """HH:MMとして解析できない開始時刻は制約なし（None）に倒す。

    素通しするとcalculate_timetableのstrptimeがValueErrorになり、
    visit_date指定のルート計算APIが500を返してしまう（レビューで再現済み）。
    """
    assert resolve_open_time('{"mon": "9am-5pm"}', "mon") is None
    assert resolve_open_time('{"mon": "24時間営業-"}', "mon") is None
    assert resolve_open_time('{"mon": " - "}', "mon") is None
    # 1桁時はstrptimeが受理するため従来どおり返す
    assert resolve_open_time('{"mon": "9:00-17:00"}', "mon") == "9:00"


def test_is_closed_day_matches_comma_separated_codes() -> None:
    assert is_closed_day("wed,thu", "wed") is True
    assert is_closed_day("wed,thu", "thu") is True
    assert is_closed_day("wed,thu", "mon") is False


def test_is_closed_day_empty_string_is_never_closed() -> None:
    assert is_closed_day("", "mon") is False
