# 自然文条件解釈（ルールベース）
# 自由文から自動ルート提案(SuggestRouteRequest)の一部フィールドを推測する。
# LLM連携は行わない（Claude APIに構造化出力させる案もあるが、キー未設定でも
# 動作を保証する必要があるためルールベースを既定・唯一の実装とする）。
from __future__ import annotations

import re

from app.schemas.route import DIRECTION_KEYS

_TIME_PATTERN = re.compile(r"(\d{1,2})[:時](\d{2})?分?")

# 「までに」の直後20文字以内に時刻があれば到着締切、「戻り/帰」なら帰着締切、
# 「発/出発」なら出発時刻とみなす（時刻表現の直後に目的語が来る日本語の語順を利用）
_LAST_ARRIVAL_KEYWORDS = ("までに", "までには")
_RETURN_KEYWORDS = ("に戻り", "に帰", "帰着")
_DEPARTURE_KEYWORDS = ("発", "出発")

_LOOKAHEAD_CHARS = 20


def _extract_time(text: str, keywords: tuple[str, ...]) -> str | None:
    for match in _TIME_PATTERN.finditer(text):
        tail = text[match.end():match.end() + _LOOKAHEAD_CHARS]
        if not any(keyword in tail for keyword in keywords):
            continue
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return None


def parse_free_text(text: str) -> dict:
    """自由文からSuggestRouteRequestの一部フィールドを推測して辞書で返す。

    抽出できなかったフィールドはキーごと含めない（呼び出し側で「未指定の
    フィールドだけをこの結果で補う」マージをしやすくするため）。
    """
    result: dict = {}

    # 方面: 「南方面」「南側」のように明示的な接尾語がある場合だけ拾う
    # （接尾語無しの単漢字一致は「西宮」等の地名に誤反応するリスクが高いため避ける）
    directions = [d for d in DIRECTION_KEYS if f"{d}方面" in text or f"{d}側" in text]
    if directions:
        result["directions"] = directions

    last_arrival_by = _extract_time(text, _LAST_ARRIVAL_KEYWORDS)
    if last_arrival_by:
        result["last_arrival_by"] = last_arrival_by

    return_by = _extract_time(text, _RETURN_KEYWORDS)
    if return_by:
        result["return_by"] = return_by

    departure_time = _extract_time(text, _DEPARTURE_KEYWORDS)
    if departure_time:
        result["departure_time"] = departure_time

    if "高速" in text:
        result["use_highway"] = True

    if "訪問済み" in text and ("含め" in text or "含む" in text):
        result["include_visited"] = True

    max_stations_match = re.search(r"(\d+)\s*駅", text)
    if max_stations_match:
        count = int(max_stations_match.group(1))
        if 1 <= count <= 9:
            result["max_stations"] = count

    return result
