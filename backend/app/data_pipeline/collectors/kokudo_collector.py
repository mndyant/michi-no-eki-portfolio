"""国土数値情報 GML から道の駅データを取得して JSON に変換する。"""
from __future__ import annotations

import json
from pathlib import Path

from lxml import etree

# 名前空間
KSJ_NS = "http://nlftp.mlit.go.jp/ksj/schemas/ksj-app"
GML_NS = "http://www.opengis.net/gml/3.2"

# 近畿7府県名（PrefectureName でフィルタ）
KINKI_PREF_NAMES = {"福井県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"}


def _text(elem, tag: str) -> str:
    """子要素のテキストを取得（存在しない場合は空文字）"""
    child = elem.find(f"{{{KSJ_NS}}}{tag}")
    return child.text.strip() if child is not None and child.text else ""


def _flag(elem, tag: str) -> bool:
    """施設有無フラグ（1=有, 2=無）"""
    return _text(elem, tag) == "1"


def parse_gml(xml_path: Path) -> list[dict]:
    """GMLファイルをパースして近畿7府県の道の駅リストを返す"""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    stations = []
    for rs in root.iter(f"{{{KSJ_NS}}}RoadsideStation"):
        pref = _text(rs, "PrefectureName")
        if pref not in KINKI_PREF_NAMES:
            continue

        area_code = _text(rs, "AdministrativeAreaCode")
        gml_id = rs.get(f"{{{GML_NS}}}id")  # 例: "P35_123"

        lat_str = _text(rs, "CenterOfLatitude")
        lon_str = _text(rs, "CenterOfLongitude")

        station = {
            "station_id": gml_id,
            "name": _text(rs, "NameOfRoadsideStation"),
            "pref": pref,
            "city": _text(rs, "LocalGovernmentName"),
            "area_code": area_code,
            "lat": float(lat_str) if lat_str else None,
            "lon": float(lon_str) if lon_str else None,
            "url": _text(rs, "URL1"),
            "facilities": {
                "atm": _flag(rs, "ATMPresence"),
                "baby_bed": _flag(rs, "BabyBedPresence"),
                "restaurant": _flag(rs, "RestaurantPresence"),
                "coffee_shop": _flag(rs, "CoffeeShopPresence"),
                "accommodation": _flag(rs, "AccommodationsPresence"),
                "spa": _flag(rs, "SpaFacilityPresence"),
                "camping": _flag(rs, "CampingGroundPresence"),
                "park": _flag(rs, "ParkPresence"),
                "observation_tower": _flag(rs, "SightseeingTowerPresence"),
                "museum": _flag(rs, "ArtGalleryAndMuseumPresence"),
                "gas_station": _flag(rs, "GasStationPresence"),
                "ev_charge": _flag(rs, "EVChargeFacilitiesPresence"),
                "wifi": _flag(rs, "WirelessLANPresence"),
                "shower": _flag(rs, "ShowerBathPresence"),
                "experience": _flag(rs, "ExperienceBasedFacilitiesPresence"),
                "visitor_info": _flag(rs, "VisitorInformationPresence"),
                "accessible_restroom": _flag(rs, "PersonWithAPhysicalDisabilityRestroomPresence"),
                "shop": _flag(rs, "ShopPresence"),
            },
        }
        stations.append(station)

    return stations


def collect(data_dir: Path | None = None) -> list[dict]:
    """data/raw/ 以下の GML ファイルを全て読み込んで近畿データを返す"""
    if data_dir is None:
        data_dir = Path(__file__).parents[3] / "data" / "raw"

    xml_files = sorted(data_dir.rglob("P35-*.xml"))
    if not xml_files:
        raise FileNotFoundError(f"GMLファイルが見つかりません: {data_dir}")

    # gml:id で重複排除（複数XMLファイルに対応）
    seen_ids: set[str] = set()
    all_stations: list[dict] = []

    for xml_path in xml_files:
        print(f"  パース中: {xml_path.name}")
        for s in parse_gml(xml_path):
            if s["station_id"] not in seen_ids:
                seen_ids.add(s["station_id"])
                all_stations.append(s)

    return all_stations


def main() -> None:
    output_path = Path(__file__).parents[3] / "data" / "raw" / "stations_kinki.json"

    print("GMLパース開始...")
    stations = collect()

    output_path.write_text(
        json.dumps(stations, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n完了: {len(stations)}件 → {output_path}")
    # 府県別内訳を表示
    from collections import Counter
    pref_counts = Counter(s["pref"] for s in stations)
    for pref, count in sorted(pref_counts.items()):
        print(f"  {pref}: {count}件")


if __name__ == "__main__":
    main()
