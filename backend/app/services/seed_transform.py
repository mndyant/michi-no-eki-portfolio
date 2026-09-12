# シード投入用の変換ロジック（純粋関数のみ）
#
# data/raw/stations_kinki.json（GML由来の生データ）を stations テーブルの行データへ
# 変換するための関数群。DBやファイルI/Oには依存しない＝pytestで単体テストしやすい形にする。
#
# 仮値ルールは docs/DESIGN.md 12章に準拠する。
from __future__ import annotations

import json
from datetime import date
from hashlib import sha1
from math import atan2, cos, radians, sin, sqrt
from typing import Any

# 地球の半径（km）。haversine距離計算に使う
EARTH_RADIUS_KM = 6371.0088

# 再訪問しにくさスコアの基準地点＝大阪駅の座標（DESIGN.md 12章「出発地デフォルト」と同じ値）
OSAKA_STATION_COORDS = (34.7025, 135.4959)

# 住所に含まれていたら「山間部」とみなすキーワード
MOUNTAIN_KEYWORDS = ("山", "峠", "渓", "谷")

# 営業時間の仮値を適用する曜日一覧
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# データ収集元・最終確認日（DESIGN.md 12章の仮値ルールどおり）
SEED_SOURCE = "国土数値情報+Wikipedia(2026-05-17)"
SEED_LAST_VERIFIED_AT = date(2026, 5, 17)

# 座標未取得駅に適用する再訪問しにくさスコアの暫定値と理由
NO_COORD_REVISIT_SCORE = 3
NO_COORD_REVISIT_REASON = "座標未取得のため暫定値3"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """2点間の大圏距離（km）をhaversine公式で計算する"""
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lambda = radians(lon2 - lon1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lambda / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def build_business_hours_json() -> str:
    """全曜日09:00-17:00の仮値business_hoursをJSON文字列で返す"""
    hours = {day: "09:00-17:00" for day in WEEKDAYS}
    return json.dumps(hours, ensure_ascii=False)


def estimate_facility_scale(facilities: dict[str, Any] | None) -> str:
    """facilitiesのtrue数から施設規模を推定する
    8個以上=large、4個以上=medium、それ未満=small、facilitiesが無ければsmall
    """
    if not facilities:
        return "small"
    true_count = sum(1 for value in facilities.values() if value is True)
    if true_count >= 8:
        return "large"
    if true_count >= 4:
        return "medium"
    return "small"


def estimate_purpose_flags(facilities: dict[str, Any] | None) -> dict[str, bool]:
    """facilitiesから利用目的フラグを推定する
    good_for_lunch <- restaurant, good_for_sweets <- coffee_shop,
    good_for_souvenir <- shop, has_spa <- spa
    facilitiesが無い場合は全てFalse
    """
    if not facilities:
        return {
            "good_for_lunch": False,
            "good_for_sweets": False,
            "good_for_souvenir": False,
            "has_spa": False,
        }
    return {
        "good_for_lunch": bool(facilities.get("restaurant", False)),
        "good_for_sweets": bool(facilities.get("coffee_shop", False)),
        "good_for_souvenir": bool(facilities.get("shop", False)),
        "has_spa": bool(facilities.get("spa", False)),
    }


def determine_is_mountainous(
    address: str | None,
    lat: float | None,
    lon: float | None,
    other_coords: list[tuple[float, float]],
    radius_km: float = 15.0,
) -> bool:
    """山間部かどうかを簡易判定する（DESIGN.md 12章）
    - 住所に「山」「峠」「渓」「谷」のいずれかを含む → True
    - それ以外は、半径radius_km以内に他駅が1件も無ければ True
    - 座標が無い場合はキーワード判定のみで、なければFalse
    """
    if address and any(keyword in address for keyword in MOUNTAIN_KEYWORDS):
        return True
    if lat is None or lon is None:
        return False
    for other_lat, other_lon in other_coords:
        if haversine_km(lat, lon, other_lat, other_lon) <= radius_km:
            # 15km以内に他駅がある＝山間部の孤立駅ではないと判定
            return False
    return True


def build_placeholder_station_id(name: str) -> str:
    """station_id未収録の駅に振る仮IDを、駅名から決定的に生成する（Issue #82レビュー対応）

    以前は「NOID_001」のような位置連番だったが、シードデータの並び替えや駅の追加・削除で
    IDがズレてupsert照合が破綻する（UNIQUE制約違反を起こす）ため、name のSHA-1ハッシュ
    先頭8桁を使った安定IDに変更した。同じ駅名なら並び順に関係なく常に同じIDになる。
    """
    digest = sha1(name.encode("utf-8")).hexdigest()[:8]
    return f"NOID_{digest}"


def assign_placeholder_station_ids(stations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """station_idが欠けている駅（GMLに未収録の16件程度）に仮IDを振る
    元のリストは変更せず、コピーを返す純粋関数。
    仮IDは駅名由来の決定的ハッシュ（並び順・追加削除に依存しない）
    """
    result = []
    for station in stations:
        new_station = dict(station)
        if not new_station.get("station_id"):
            new_station["station_id"] = build_placeholder_station_id(new_station["name"])
        result.append(new_station)
    return result


def build_clusters(stations: list[dict[str, Any]], radius_km: float = 15.0) -> list[dict[str, Any]]:
    """座標のある駅を府県ごとに区切った上で、半径radius_km・貪欲法でクラスタリングする

    アルゴリズム（府県内）:
      1. 未クラスタの駅を順番に見る
      2. 既存クラスタの「代表駅（最初にそのクラスタへ入った駅）」から半径km以内なら、そのクラスタに追加
      3. どのクラスタにも入らなければ、この駅を代表駅とする新クラスタを作る

    戻り値: [{"name": "大阪府1", "station_ids": ["P35_xxx", ...]}, ...]
    座標の無い駅（lat/lonがNone）はここでは対象外（呼び出し側でcluster_id=Noneとして扱う）
    """
    stations_by_pref: dict[str, list[dict[str, Any]]] = {}
    for station in stations:
        if station.get("lat") is None or station.get("lon") is None:
            continue
        stations_by_pref.setdefault(station["pref"], []).append(station)

    clusters: list[dict[str, Any]] = []
    for pref, pref_stations in stations_by_pref.items():
        # 府県内での貪欲クラスタリング（代表駅の座標のみで判定するシンプル版）
        pref_clusters: list[dict[str, Any]] = []
        for station in pref_stations:
            lat, lon = station["lat"], station["lon"]
            placed = False
            for cluster in pref_clusters:
                seed_lat, seed_lon = cluster["seed"]
                if haversine_km(lat, lon, seed_lat, seed_lon) <= radius_km:
                    cluster["station_ids"].append(station["station_id"])
                    placed = True
                    break
            if not placed:
                pref_clusters.append({"seed": (lat, lon), "station_ids": [station["station_id"]]})

        for index, cluster in enumerate(pref_clusters, start=1):
            clusters.append({"name": f"{pref}{index}", "station_ids": cluster["station_ids"]})

    return clusters


def build_revisit_difficulty(
    lat: float, lon: float, is_mountainous: bool, cluster_size: int
) -> tuple[int, str]:
    """再訪問しにくさスコア（1-5）と理由文を算出する（DESIGN.md 12章）

    基準1点 + 大阪駅からの距離（60km超+1, 100km超でさらに+1）
           + 山間部(+1) + クラスタが自分含め2駅以下(+1)、上限5
    """
    score = 1
    reasons: list[str] = []

    distance_km = haversine_km(lat, lon, *OSAKA_STATION_COORDS)
    if distance_km > 60:
        score += 1
        reasons.append(f"大阪駅から{distance_km:.1f}kmで60km超")
    if distance_km > 100:
        score += 1
        reasons.append(f"さらに100km超（{distance_km:.1f}km）")
    if is_mountainous:
        score += 1
        reasons.append("山間部と判定されたため")
    if cluster_size <= 2:
        score += 1
        reasons.append("クラスタ内が自駅含め2駅以下のため")

    score = min(score, 5)

    if reasons:
        reason_text = "基準1点に加え、" + "、".join(reasons) + f"、合計{score}点。"
    else:
        reason_text = "基準1点のみ（加点要因なし）。"

    return score, reason_text


def transform_stations(
    raw_stations: list[dict[str, Any]], radius_km: float = 15.0
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """stations_kinki.json の生データ一覧を、stations/clustersテーブルの投入用データへ変換する

    戻り値: (station_rows, cluster_rows)
      - station_rows: 各駅の行データのdict。"cluster_name"キーに紐づくクラスタ名を含む
        （DBのcluster_idはseed.py側でクラスタ投入後のIDを引いて解決する）
      - cluster_rows: [{"name": ..., "description": None}, ...]
    """
    stations = assign_placeholder_station_ids(raw_stations)

    # 山間部判定に使う「他駅座標一覧」（座標のある駅のみ）。
    # インデックスで管理し、座標が偶然一致するケースでも自分自身だけを正しく除外できるようにする
    coords_with_index = [
        (i, s["lat"], s["lon"])
        for i, s in enumerate(stations)
        if s.get("lat") is not None and s.get("lon") is not None
    ]

    clusters = build_clusters(stations, radius_km=radius_km)
    cluster_name_by_station_id: dict[str, str] = {}
    cluster_size_by_name: dict[str, int] = {}
    for cluster in clusters:
        cluster_size_by_name[cluster["name"]] = len(cluster["station_ids"])
        for station_id in cluster["station_ids"]:
            cluster_name_by_station_id[station_id] = cluster["name"]

    station_rows: list[dict[str, Any]] = []
    for idx, station in enumerate(stations):
        lat, lon = station.get("lat"), station.get("lon")
        facilities = station.get("facilities")
        flags = estimate_purpose_flags(facilities)
        has_coords = lat is not None and lon is not None

        if has_coords:
            # 自分自身（同じインデックス）を除いた他駅座標一覧を作る
            other_coords = [(o_lat, o_lon) for i, o_lat, o_lon in coords_with_index if i != idx]
            mountainous = determine_is_mountainous(
                station.get("address"), lat, lon, other_coords, radius_km=radius_km
            )
            cluster_name = cluster_name_by_station_id.get(station["station_id"])
            cluster_size = cluster_size_by_name.get(cluster_name, 1) if cluster_name else 1
            revisit_score, revisit_reason = build_revisit_difficulty(
                lat, lon, mountainous, cluster_size
            )
        else:
            mountainous = False
            cluster_name = None
            revisit_score = NO_COORD_REVISIT_SCORE
            revisit_reason = NO_COORD_REVISIT_REASON

        station_rows.append(
            {
                "station_id": station["station_id"],
                "name": station["name"],
                "pref": station["pref"],
                "city": None,  # 既存addressは市町村までしか含まれない駅もあり、分離は今回未実施
                "address": station.get("address"),
                "lat": lat,
                "lon": lon,
                "official_url": station.get("url"),
                "business_hours": build_business_hours_json(),
                "stamp_start": "09:00",
                "stamp_end": "17:00",
                "closed_days": "",
                "visited": False,
                "visited_date": None,
                "stay_time_min_default": 15,
                "facility_scale": estimate_facility_scale(facilities),
                "good_for_lunch": flags["good_for_lunch"],
                "good_for_sweets": flags["good_for_sweets"],
                "good_for_souvenir": flags["good_for_souvenir"],
                "has_spa": flags["has_spa"],
                "scenery_score": None,
                "is_mountainous": mountainous,
                "revisit_difficulty_score": revisit_score,
                "revisit_difficulty_reason": revisit_reason,
                "cluster_name": cluster_name,
                "reputation_items": "[]",
                "local_specialty": "[]",
                "seasonal_specialty": "[]",
                "user_memo": None,
                "source": SEED_SOURCE,
                "last_verified_at": SEED_LAST_VERIFIED_AT,
            }
        )

    cluster_rows = [{"name": c["name"], "description": None} for c in clusters]
    return station_rows, cluster_rows
