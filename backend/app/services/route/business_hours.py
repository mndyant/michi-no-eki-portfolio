# 曜日別営業時間・定休日をルート計算の制約へ変換する純粋関数群（Issue #71）。
# business_hours/closed_daysのJSON・文字列解析だけを担当し、時刻計算そのものは
# timetable.pyに任せる（責務を分けてテストしやすくする）。
from __future__ import annotations

import json
from datetime import date, datetime

# app/services/seed_transform.py の WEEKDAYS と一致させる（曜日キー）
WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def weekday_code(visit_date: date) -> str:
    """日付から曜日キー（mon〜sun、月曜始まり）を求める。"""
    return WEEKDAY_CODES[visit_date.weekday()]


def resolve_open_time(business_hours_json: str, weekday: str | None) -> str | None:
    """business_hoursのJSON文字列（例: {"mon": "09:00-17:00", ...}）から、
    指定曜日の開店時刻（"HH:MM"）を取り出す。

    日付未指定なら、全7曜日で開店時刻が一致する場合だけその時刻を使う。
    該当曜日の設定がない、または"開始-終了"形式で解析できない場合はNoneを返す
    （＝営業開始の制約を課さない。未確認データで誤警告を出さないため）。
    """
    try:
        hours = json.loads(business_hours_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(hours, dict):
        return None
    if weekday is None:
        openings = [resolve_open_time(business_hours_json, day) for day in WEEKDAY_CODES]
        return openings[0] if openings[0] is not None and len(set(openings)) == 1 else None
    value = hours.get(weekday)
    if not isinstance(value, str) or "-" not in value:
        return None
    start, _, _end = value.partition("-")
    start = start.strip()
    if not start:
        return None
    # "9am-5pm" のようにHH:MMとして解析できない値は「制約なし」に倒す。
    # ここで素通しすると後段のtimetable計算がValueError（=API 500）になる
    try:
        datetime.strptime(start, "%H:%M")
    except ValueError:
        return None
    return datetime.strptime(start, "%H:%M").strftime("%H:%M")


def is_closed_day(closed_days: str, weekday: str) -> bool:
    """closed_daysのカンマ区切り文字列（例: "wed,thu"）に指定曜日が含まれるか判定する。

    現状は仮値「空欄（不明）」のみのため、値が入るのは今後の運用入力を想定した規約。
    """
    codes = {code.strip() for code in closed_days.split(",") if code.strip()}
    return weekday in codes
