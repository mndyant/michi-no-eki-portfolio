from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil
from typing import Sequence


@dataclass(frozen=True, slots=True)
class TimetableOrigin:
    """時刻表の起点となる任意地点。"""

    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class TimetableStation:
    """時刻計算に必要な道の駅情報だけを持つ。"""

    station_id: int
    name: str
    lat: float
    lon: float
    stamp_deadline: str
    stay_min: int
    # 訪問日の曜日から解決した開店時刻（"HH:MM"）。visit_date未指定や
    # 曜日別営業時間が未確認の場合はNone（＝開店待ち制約を課さない）
    open_time: str | None = None
    # 訪問日がその駅の定休日に該当するか（Issue #71）。自動除外はせず警告のみに使う
    is_closed_day: bool = False


@dataclass(frozen=True, slots=True)
class TimetableStop:
    station_id: int
    name: str
    arrival: str
    departure: str
    stay_min: int
    stamp_deadline: str
    margin_min: int
    warnings: tuple[str, ...]


def calculate_latest_departures(
    deadlines_min: Sequence[int],
    stays_min: Sequence[int],
    travels_min: Sequence[int],
    return_travel_min: int | None,
    return_by_min: int | None,
) -> list[int | None]:
    """各駅の最遅出発時刻（分）を後ろから逆算する純粋関数。

    travels_min は「出発地→駅0、駅0→駅1、…」の順で駅数と同じ長さ。
    駅iの最遅出発 L[i] は「駅i+1に締切までに着ける」かつ
    「駅i+1をL[i+1]までに出られる」の両方を満たす時刻。
    以降に制約が何もない駅（＝最終駅で帰着締切なし）は None を返す。
    """
    count = len(deadlines_min)
    if not (count == len(stays_min) == len(travels_min)):
        raise ValueError("駅数と滞在・移動区間の数が一致していません")
    latest: list[int | None] = [None] * count
    if count == 0:
        return latest
    # 最終駅: 帰着締切がある場合のみ「帰着締切 - 帰路の移動時間」が制約になる
    if return_by_min is not None and return_travel_min is not None:
        latest[count - 1] = return_by_min - return_travel_min
    for i in range(count - 2, -1, -1):
        travel_to_next = travels_min[i + 1]
        # 制約1: 次の駅へ締切までに到着する
        candidates = [deadlines_min[i + 1] - travel_to_next]
        # 制約2: 次の駅を最遅出発時刻までに出られる（滞在時間ぶん手前に着く必要がある）
        next_latest = latest[i + 1]
        if next_latest is not None:
            candidates.append(next_latest - stays_min[i + 1] - travel_to_next)
        latest[i] = min(candidates)
    return latest


def calculate_origin_latest_departure(
    deadlines_min: Sequence[int],
    stays_min: Sequence[int],
    travels_min: Sequence[int],
    return_travel_min: int | None,
    return_by_min: int | None,
) -> int:
    """出発地の最遅出発時刻（分）を逆算する（逆算モードの中核）。

    「最初の駅に締切までに着ける」かつ「最初の駅をその最遅出発時刻までに出られる」
    を満たす、最も遅い出発地の出発時刻を返す。
    """
    if not deadlines_min:
        raise ValueError("駅が1件以上必要です")
    latest = calculate_latest_departures(
        deadlines_min, stays_min, travels_min, return_travel_min, return_by_min
    )
    candidates = [deadlines_min[0] - travels_min[0]]
    if latest[0] is not None:
        candidates.append(latest[0] - stays_min[0] - travels_min[0])
    return min(candidates)


def calculate_timetable(
    origin: TimetableOrigin,
    departure_time: str,
    stations: Sequence[TimetableStation],
    travel_durations_min: Sequence[float],
) -> list[TimetableStop]:
    """起点から取得済みの区間所要時間で、訪問順どおりの時刻表を計算する。"""
    if len(stations) != len(travel_durations_min):
        raise ValueError("駅数と移動区間数が一致していません")
    if not -90 <= origin.lat <= 90 or not -180 <= origin.lon <= 180:
        raise ValueError("出発地の緯度経度が範囲外です")

    base_date = date(2000, 1, 1)
    current = datetime.combine(base_date, datetime.strptime(departure_time, "%H:%M").time())
    result: list[TimetableStop] = []
    for station, duration_min in zip(stations, travel_durations_min, strict=True):
        # 秒以下を切り捨てると締切余裕を過大評価するため、区間ごとに分単位で切り上げる。
        arrival = current + timedelta(minutes=ceil(duration_min))
        deadline_time = datetime.strptime(station.stamp_deadline, "%H:%M").time()
        deadline = datetime.combine(base_date, deadline_time)
        margin_min = int((deadline - arrival).total_seconds() // 60)
        warnings: list[str] = []
        if margin_min < 0:
            warnings.append("stamp_deadline_missed")
        elif margin_min < 15:
            warnings.append("tight")
        # 営業開始前の到着は開店まで待機する（Issue #71）。滞在・以降の出発はこれを起点にする
        stay_start = arrival
        if station.open_time is not None:
            open_dt = datetime.combine(
                base_date, datetime.strptime(station.open_time, "%H:%M").time()
            )
            if arrival < open_dt:
                stay_start = open_dt
                warnings.append("wait_for_open")
        if station.is_closed_day:
            # プランからの自動除外はしない。判断材料として警告するだけに留める
            warnings.append("closed_day")
        departure = stay_start + timedelta(minutes=station.stay_min)
        result.append(
            TimetableStop(
                station_id=station.station_id,
                name=station.name,
                arrival=arrival.strftime("%H:%M"),
                departure=departure.strftime("%H:%M"),
                stay_min=station.stay_min,
                stamp_deadline=station.stamp_deadline,
                margin_min=margin_min,
                warnings=tuple(warnings),
            )
        )
        current = departure
    return result
