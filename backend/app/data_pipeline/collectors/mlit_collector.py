"""国交省 list.xls から近畿7府県の道の駅マスターリストを取得する。"""
from __future__ import annotations

import re
from pathlib import Path

import xlrd

KINKI_PREFS = {"福井県", "滋賀県", "京都府", "大阪府", "兵庫県", "奈良県", "和歌山県"}


def _normalize_name(name: str) -> str:
    """駅名を正規化（全角スペース→半角、連続スペース→1個）"""
    name = name.replace("　", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", name).strip()


def load_xls(xls_path: Path) -> list[dict]:
    """list.xls を読んで近畿7府県の道の駅リストを返す"""
    wb = xlrd.open_workbook(str(xls_path))
    ws = wb.sheet_by_index(0)

    stations = []
    for r in range(1, ws.nrows):
        pref = ws.cell_value(r, 0)
        if pref not in KINKI_PREFS:
            continue
        name_raw = ws.cell_value(r, 1).strip()
        stations.append({
            "name_raw": name_raw,
            "name": _normalize_name(name_raw),
            "pref": pref,
            "registration": ws.cell_value(r, 2),   # 登録回
            "reg_date": ws.cell_value(r, 3),        # 登録年月
            "address": ws.cell_value(r, 4),
            "url": ws.cell_value(r, 5),
        })
    return stations


def merge_with_gml(xls_stations: list[dict], gml_stations: list[dict]) -> list[dict]:
    """XLSをマスターとして、GMLの座標・施設情報をマージする"""
    gml_index = {_normalize_name(s["name"]): s for s in gml_stations}

    merged = []
    for xs in xls_stations:
        gml = gml_index.get(xs["name"])
        station = {
            "station_id": gml["station_id"] if gml else None,
            "name": xs["name"],
            "pref": xs["pref"],
            "address": xs["address"] or (gml["city"] if gml else ""),
            "url": xs["url"] or (gml["url"] if gml else ""),
            "registration": xs["registration"],
            "reg_date": xs["reg_date"],
            # GMLから補完（GMLにない駅はNone）
            "lat": gml["lat"] if gml else None,
            "lon": gml["lon"] if gml else None,
            "facilities": gml["facilities"] if gml else None,
        }
        merged.append(station)
    return merged
