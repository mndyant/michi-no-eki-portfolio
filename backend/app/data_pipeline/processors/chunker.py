"""各道の駅データを項目別チャンクに分割する。

チャンク種別:
  basic      - 駅名・所在地・登録番号・座標
  facilities - 施設有無の自然言語テキスト
  wikipedia  - Wikipedia導入文（found=True の駅のみ）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict


class Chunk(TypedDict):
    station_id: str | None
    name: str
    pref: str
    chunk_type: str   # "basic" | "facilities" | "wikipedia"
    content: str
    metadata: dict


# 施設キー → 日本語ラベル
_FACILITY_LABELS: dict[str, str] = {
    "atm": "ATM",
    "baby_bed": "ベビーベッド",
    "restaurant": "レストラン",
    "coffee_shop": "コーヒーショップ",
    "accommodation": "宿泊施設",
    "spa": "温泉・スパ",
    "camping": "キャンプ場",
    "park": "公園",
    "observation_tower": "展望台",
    "museum": "博物館・資料館",
    "gas_station": "ガソリンスタンド",
    "ev_charge": "EV充電スタンド",
    "wifi": "Wi-Fi",
    "shower": "シャワー",
    "experience": "体験施設",
    "visitor_info": "観光案内所",
    "accessible_restroom": "多目的トイレ",
    "shop": "売店・直売所",
}


def _basic_chunk(station: dict) -> Chunk:
    lines = [f"道の駅「{station['name']}」（{station['pref']}）"]
    if station.get("address"):
        lines.append(f"住所: {station['address']}")
    if station.get("registration"):
        lines.append(f"登録番号: {station['registration']}")
    if station.get("reg_date"):
        lines.append(f"登録年月: {station['reg_date']}")
    if station.get("lat") and station.get("lon"):
        lines.append(f"座標: 緯度{station['lat']:.5f} 経度{station['lon']:.5f}")
    if station.get("url"):
        lines.append(f"公式URL: {station['url']}")
    return Chunk(
        station_id=station.get("station_id"),
        name=station["name"],
        pref=station["pref"],
        chunk_type="basic",
        content="\n".join(lines),
        metadata={
            "lat": station.get("lat"),
            "lon": station.get("lon"),
            "registration": station.get("registration", ""),
        },
    )


def _facilities_chunk(station: dict) -> Chunk | None:
    fac = station.get("facilities")
    if not fac:
        return None
    present = [label for key, label in _FACILITY_LABELS.items() if fac.get(key)]
    absent = [label for key, label in _FACILITY_LABELS.items() if not fac.get(key)]
    lines = [f"道の駅「{station['name']}」の施設情報:"]
    if present:
        lines.append(f"利用可能: {', '.join(present)}")
    if absent:
        lines.append(f"なし: {', '.join(absent)}")
    return Chunk(
        station_id=station.get("station_id"),
        name=station["name"],
        pref=station["pref"],
        chunk_type="facilities",
        content="\n".join(lines),
        metadata={"facilities": {k: bool(v) for k, v in fac.items()}},
    )


def _wiki_chunk(station: dict, wiki_dir: Path) -> Chunk | None:
    safe_name = station["name"].replace(" ", "_").replace("/", "_").replace("\\", "_")
    wiki_file = wiki_dir / f"{safe_name}.json"
    if not wiki_file.exists():
        return None
    wiki = json.loads(wiki_file.read_text(encoding="utf-8"))
    if not wiki.get("found") or not wiki.get("extract", "").strip():
        return None
    return Chunk(
        station_id=station.get("station_id"),
        name=station["name"],
        pref=station["pref"],
        chunk_type="wikipedia",
        content=f"道の駅「{station['name']}」について（Wikipedia）:\n{wiki['extract'].strip()}",
        metadata={"wiki_title": wiki.get("wiki_title", "")},
    )


def chunk_station(station: dict, wiki_dir: Path) -> list[Chunk]:
    """1駅分のチャンクリストを生成する（3〜5件）"""
    chunks: list[Chunk] = []
    chunks.append(_basic_chunk(station))
    fac = _facilities_chunk(station)
    if fac:
        chunks.append(fac)
    wiki = _wiki_chunk(station, wiki_dir)
    if wiki:
        chunks.append(wiki)
    return chunks


def chunk_all(stations_json: Path, wiki_dir: Path) -> list[Chunk]:
    """全駅分のチャンクを生成して返す"""
    stations = json.loads(stations_json.read_text(encoding="utf-8"))
    all_chunks: list[Chunk] = []
    for station in stations:
        all_chunks.extend(chunk_station(station, wiki_dir))
    return all_chunks
