# -*- coding: utf-8 -*-
"""同梱シードデータ（data/raw/stations_kinki.json）の座標の健全性チェック。

Issue #74 で16駅の座標をジオコーディング補完した際の回帰テスト。
座標の欠損や、明らかに近畿圏外の異常値（ジオコーディング誤ヒット）を検出する。
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

STATIONS_JSON = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / "stations_kinki.json"
pytestmark = pytest.mark.skipif(not STATIONS_JSON.exists(), reason="第三者データは同梱しない。任意のローカルデータ検証")

# 近畿7府県（大阪・京都・兵庫・奈良・和歌山・滋賀・福井）を覆う緩めの境界。
# 最南端は和歌山県串本町（約33.43度）、最北端は福井県あわら市（約36.3度）
LAT_MIN, LAT_MAX = 33.3, 36.5
LON_MIN, LON_MAX = 134.0, 137.0


def _load_stations() -> list[dict]:
    with open(STATIONS_JSON, encoding="utf-8") as f:
        return json.load(f)


def test_全159駅に座標がある() -> None:
    stations = _load_stations()
    assert len(stations) == 159
    missing = [s["name"] for s in stations if s.get("lat") is None or s.get("lon") is None]
    assert missing == [], f"座標未設定の駅: {missing}"


def test_全駅の座標が近畿圏の範囲内にある() -> None:
    """ジオコーディングの誤ヒット（同名の遠隔地など）を検出する。"""
    outliers = [
        f"{s['name']}({s['lat']},{s['lon']})"
        for s in _load_stations()
        if not (LAT_MIN <= s["lat"] <= LAT_MAX and LON_MIN <= s["lon"] <= LON_MAX)
    ]
    assert outliers == [], f"近畿圏外の座標: {outliers}"


def test_補完した16駅は施設精度である() -> None:
    """Issue #74 で補完した駅が全て facility 精度になっていること（町丁目近似の残留を防ぐ）。"""
    geocoded = [s for s in _load_stations() if s.get("coord_source")]
    assert len(geocoded) == 16
    approx = [s["name"] for s in geocoded if s.get("coord_precision") != "facility"]
    assert approx == [], f"施設精度でない補完座標: {approx}"
