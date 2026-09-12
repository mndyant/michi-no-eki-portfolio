# 曜日別営業時間・定休日をルート計算の制約へ変換する純粋関数群（Issue #71）。
# business_hours/closed_daysのJSON・文字列解析だけを担当し、時刻計算そのものは
# timetable.pyに任せる（責務を分けてテストしやすくする）。
from __future__ import annotations

import json
from datetime import date

# app/services/seed_transform.py の WEEKDAYS と一致させる（曜日キー）
WEEKDAY_CODES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def weekday_code(visit_date: date) -> str:
    """日付から曜日キー（mon〜sun、月曜始まり）を求める。"""
    return WEEKDAY_CODES[visit_date.weekday()]


def resolve_open_time(business_hours_json: str, weekday: str) -> str | None:
    """business_hoursのJSON文字列（例: {"mon": "09:00-17:00", ...}）から、
    指定曜日の開店時刻（"HH:MM"）を取り出す。

    該当曜日の設定がない、または"開始-終了"形式で解析できない場合はNoneを返す
    （＝営業開始の制約を課さない。未確認データで誤警告を出さないため）。
    """
    try:
        hours = json.loads(business_hours_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(hours, dict):
        return None
    value = hours.get(weekday)
    if not value or "-" not in value:
        return None
    start, _, _end = value.partition("-")
    start = start.strip()
    return start or None


def is_closed_day(closed_days: str, weekday: str) -> bool:
    """closed_daysのカンマ区切り文字列（例: "wed,thu"）に指定曜日が含まれるか判定する。

    現状は仮値「空欄（不明）」のみのため、値が入るのは今後の運用入力を想定した規約。
    """
    codes = {code.strip() for code in closed_days.split(",") if code.strip()}
    return weekday in codes
