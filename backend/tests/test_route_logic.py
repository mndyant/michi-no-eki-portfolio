from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.route.gmaps import MapPoint, build_google_maps_url  # noqa: E402
from app.services.route.timetable import (  # noqa: E402
    TimetableOrigin,
    TimetableStation,
    calculate_timetable,
)

ORIGIN = TimetableOrigin(34.7, 135.5)


def _ced_stations() -> list[TimetableStation]:
    return [
        TimetableStation(3, "C", 35.0, 135.0, "18:00", 15),
        TimetableStation(5, "E", 35.1, 135.1, "17:00", 15),
        TimetableStation(4, "D", 35.2, 135.2, "18:00", 15),
    ]


def test_ced_arrival_before_deadline_is_ok() -> None:
    stops = calculate_timetable(ORIGIN, "15:00", _ced_stations(), [30, 15, 15])
    station_e = stops[1]
    assert station_e.arrival == "16:00"
    assert station_e.margin_min == 60
    assert station_e.warnings == ()


def test_ced_late_arrival_has_deadline_warning() -> None:
    stops = calculate_timetable(ORIGIN, "16:30", _ced_stations(), [30, 15, 15])
    station_e = stops[1]
    assert station_e.arrival == "17:30"
    assert station_e.margin_min == -30
    assert station_e.warnings == ("stamp_deadline_missed",)


def test_tight_warning_when_margin_is_under_15_minutes() -> None:
    station = TimetableStation(1, "A", 35.0, 135.0, "17:00", 15)
    stop = calculate_timetable(ORIGIN, "16:00", [station], [50])[0]
    assert stop.arrival == "16:50"
    assert stop.warnings == ("tight",)


def test_wait_for_open_warning_when_arrival_before_open_time() -> None:
    """開店前到着は開店まで待機し、departureがそこから滞在時間分後ろにずれる（Issue #71）。"""
    station = TimetableStation(
        1, "A", 35.0, 135.0, "17:00", 15, open_time="09:00",
    )
    stop = calculate_timetable(ORIGIN, "08:00", [station], [30])[0]
    assert stop.arrival == "08:30"
    assert "wait_for_open" in stop.warnings
    # 09:00開店を待ってから15分滞在するので出発は09:15（到着直後の08:45にはならない）
    assert stop.departure == "09:15"


def test_no_wait_warning_when_arrival_after_open_time() -> None:
    """開店後の到着なら待機は発生せず、警告も付かない。"""
    station = TimetableStation(1, "A", 35.0, 135.0, "17:00", 15, open_time="09:00")
    stop = calculate_timetable(ORIGIN, "09:30", [station], [30])[0]
    assert stop.arrival == "10:00"
    assert stop.warnings == ()
    assert stop.departure == "10:15"


def test_closed_day_warning_does_not_block_visit() -> None:
    """定休日該当は警告として付くだけで、時刻計算自体は通常通り進む（自動除外はしない）。"""
    station = TimetableStation(1, "A", 35.0, 135.0, "17:00", 15, is_closed_day=True)
    stop = calculate_timetable(ORIGIN, "09:00", [station], [30])[0]
    assert stop.arrival == "09:30"
    assert "closed_day" in stop.warnings
    assert stop.departure == "09:45"


def test_wait_for_open_and_closed_day_can_combine_with_tight_warning() -> None:
    """開店待ち・定休日は締切系の警告（tight等）と共存できる。"""
    station = TimetableStation(
        1, "A", 35.0, 135.0, "10:00", 15, open_time="09:50", is_closed_day=True,
    )
    stop = calculate_timetable(ORIGIN, "09:00", [station], [50])[0]
    assert stop.arrival == "09:50"
    assert set(stop.warnings) == {"tight", "closed_day"}


def test_google_maps_truncates_more_than_nine_waypoints() -> None:
    origin = MapPoint(34.7, 135.5)
    stations = [MapPoint(35.0 + index / 100, 136.0) for index in range(11)]
    url, warnings = build_google_maps_url(origin, stations)
    query = parse_qs(urlparse(url).query)

    assert warnings == ["waypoints_truncated"]
    assert len(query["waypoints"][0].split("|")) == 9
    # 往路の最終駅は切り詰めず、destinationとして維持する。
    assert query["destination"] == ["35.100000,136.000000"]


def test_google_maps_return_destination_is_origin() -> None:
    origin = MapPoint(34.7, 135.5)
    url, warnings = build_google_maps_url(origin, [MapPoint(35.0, 136.0)], True)
    query = parse_qs(urlparse(url).query)
    assert warnings == []
    assert query["destination"] == query["origin"]
    assert query["waypoints"] == ["35.000000,136.000000"]
