# app/services/seed_transform.py の単体テスト
# DB・ファイルI/Oに依存しない純粋関数なので、固定の入力値で結果を検証する
import sys
from pathlib import Path

# backend/ をパスに通す
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.seed_transform import (  # noqa: E402
    NO_COORD_REVISIT_REASON,
    NO_COORD_REVISIT_SCORE,
    assign_placeholder_station_ids,
    build_business_hours_json,
    build_placeholder_station_id,
    build_clusters,
    build_revisit_difficulty,
    determine_is_mountainous,
    estimate_facility_scale,
    estimate_purpose_flags,
    haversine_km,
    transform_stations,
)


def test_haversine_km_same_point_is_zero():
    assert haversine_km(34.7025, 135.4959, 34.7025, 135.4959) == 0


def test_haversine_km_osaka_to_kyoto_is_about_40km():
    # 大阪駅と京都駅の距離はおよそ38〜42km程度
    osaka = (34.7025, 135.4959)
    kyoto = (34.9858, 135.7588)
    distance = haversine_km(*osaka, *kyoto)
    assert 35 < distance < 45


def test_build_business_hours_json_has_all_weekdays():
    import json

    hours = json.loads(build_business_hours_json())
    assert set(hours.keys()) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}
    assert all(v == "09:00-17:00" for v in hours.values())


def test_estimate_facility_scale_none_is_small():
    assert estimate_facility_scale(None) == "small"


def test_estimate_facility_scale_thresholds():
    small = {"a": True, "b": False, "c": False}
    medium = {f"f{i}": True for i in range(4)}
    large = {f"f{i}": True for i in range(8)}
    assert estimate_facility_scale(small) == "small"
    assert estimate_facility_scale(medium) == "medium"
    assert estimate_facility_scale(large) == "large"


def test_estimate_purpose_flags_none_is_all_false():
    flags = estimate_purpose_flags(None)
    assert flags == {
        "good_for_lunch": False,
        "good_for_sweets": False,
        "good_for_souvenir": False,
        "has_spa": False,
    }


def test_estimate_purpose_flags_maps_correct_keys():
    facilities = {"restaurant": True, "coffee_shop": True, "shop": False, "spa": True}
    flags = estimate_purpose_flags(facilities)
    assert flags == {
        "good_for_lunch": True,
        "good_for_sweets": True,
        "good_for_souvenir": False,
        "has_spa": True,
    }


def test_determine_is_mountainous_by_keyword():
    # 座標や近隣駅の有無に関わらず、住所にキーワードがあればTrue
    assert determine_is_mountainous("南丹市美山町", 35.0, 135.5, [(35.0, 135.5)], radius_km=15.0)


def test_determine_is_mountainous_by_isolation():
    # 半径15km以内に他駅が無ければTrue
    assert determine_is_mountainous("大野市", 35.9, 136.6, [], radius_km=15.0)


def test_determine_is_mountainous_false_when_near_other_station():
    # キーワードも無く、近くに他駅もあればFalse
    other = [(34.71, 135.50)]  # 約1km程度の近さ
    assert not determine_is_mountainous("大阪市北区", 34.7025, 135.4959, other, radius_km=15.0)


def test_determine_is_mountainous_no_coords_returns_false_without_keyword():
    assert not determine_is_mountainous("大阪市北区", None, None, [], radius_km=15.0)


def test_build_clusters_groups_nearby_stations_within_same_pref():
    stations = [
        {"station_id": "A", "pref": "大阪府", "lat": 34.70, "lon": 135.50},
        {"station_id": "B", "pref": "大阪府", "lat": 34.71, "lon": 135.51},  # Aの近く
        {"station_id": "C", "pref": "大阪府", "lat": 35.50, "lon": 136.50},  # 遠い
    ]
    clusters = build_clusters(stations, radius_km=15.0)
    names = {c["name"] for c in clusters}
    assert names == {"大阪府1", "大阪府2"}
    cluster1 = next(c for c in clusters if c["name"] == "大阪府1")
    assert set(cluster1["station_ids"]) == {"A", "B"}


def test_build_clusters_separates_different_prefs():
    stations = [
        {"station_id": "A", "pref": "大阪府", "lat": 34.70, "lon": 135.50},
        {"station_id": "B", "pref": "京都府", "lat": 34.70, "lon": 135.50},  # 同座標でも府県が違う
    ]
    clusters = build_clusters(stations, radius_km=15.0)
    assert len(clusters) == 2
    assert {c["name"] for c in clusters} == {"大阪府1", "京都府1"}


def test_build_clusters_ignores_stations_without_coords():
    stations = [
        {"station_id": "A", "pref": "大阪府", "lat": None, "lon": None},
    ]
    assert build_clusters(stations) == []


def test_build_revisit_difficulty_base_score_only():
    # 大阪駅から近く・平地・大きいクラスタなら加点要因無し
    score, reason = build_revisit_difficulty(
        lat=34.71, lon=135.50, is_mountainous=False, cluster_size=10
    )
    assert score == 1
    assert "加点要因なし" in reason


def test_build_revisit_difficulty_all_factors_capped_at_5():
    # 大阪駅から100km超・山間部・クラスタ2駅以下 → 1+1+1+1+1=5（上限にも一致）
    score, reason = build_revisit_difficulty(
        lat=35.9, lon=136.6, is_mountainous=True, cluster_size=1
    )
    assert score == 5
    assert "60km超" in reason
    assert "100km超" in reason
    assert "山間部" in reason
    assert "2駅以下" in reason


def test_build_revisit_difficulty_over_60_but_not_100():
    # 大阪駅からdaisen(60km超100km未満)程度の距離を想定
    # 60km超のみ加点され、100km超は加点されないことを確認
    from app.services.seed_transform import OSAKA_STATION_COORDS

    lat = OSAKA_STATION_COORDS[0] + 0.6  # おおよそ+66km相当
    score, reason = build_revisit_difficulty(
        lat=lat, lon=OSAKA_STATION_COORDS[1], is_mountainous=False, cluster_size=10
    )
    assert score == 2
    assert "60km超" in reason
    assert "100km超" not in reason


def test_transform_stations_no_coord_station_gets_fixed_values():
    raw = [
        {
            "station_id": None,
            "name": "座標未取得駅",
            "pref": "福井県",
            "address": "テスト市",
            "url": None,
            "lat": None,
            "lon": None,
            "facilities": None,
        }
    ]
    station_rows, cluster_rows = transform_stations(raw)
    assert len(station_rows) == 1
    row = station_rows[0]
    # 仮IDは駅名由来の決定的ハッシュ（NOID_ + SHA-1先頭8桁）
    assert row["station_id"] == build_placeholder_station_id("座標未取得駅")
    assert row["station_id"].startswith("NOID_")
    assert row["cluster_name"] is None
    assert row["revisit_difficulty_score"] == NO_COORD_REVISIT_SCORE
    assert row["revisit_difficulty_reason"] == NO_COORD_REVISIT_REASON
    assert cluster_rows == []


def test_transform_stations_assigns_cluster_and_common_fields():
    raw = [
        {
            "station_id": "P1",
            "name": "テスト駅1",
            "pref": "大阪府",
            "address": "大阪市北区",
            "url": "https://example.com/1",
            "lat": 34.70,
            "lon": 135.50,
            "facilities": {"restaurant": True, "shop": True},
        },
        {
            "station_id": "P2",
            "name": "テスト駅2",
            "pref": "大阪府",
            "address": "大阪市中央区",
            "url": "https://example.com/2",
            "lat": 34.71,
            "lon": 135.51,
            "facilities": {"coffee_shop": True},
        },
    ]
    station_rows, cluster_rows = transform_stations(raw)
    assert len(station_rows) == 2
    assert len(cluster_rows) == 1
    assert cluster_rows[0]["name"] == "大阪府1"
    for row in station_rows:
        assert row["cluster_name"] == "大阪府1"
        assert row["stay_time_min_default"] == 15
        assert row["stamp_start"] == "09:00"
        assert row["stamp_end"] == "17:00"
        assert row["source"] == "国土数値情報+Wikipedia(2026-05-17)"
        assert row["reputation_items"] == "[]"


def test_assign_placeholder_station_ids_is_order_independent():
    """NOID仮IDは駅名由来のハッシュのため、並び替えても各駅のIDが変わらない（Issue #82レビュー対応）"""
    stations = [
        {"station_id": None, "name": "無名駅A"},
        {"station_id": "P35_001", "name": "正式ID駅"},
        {"station_id": None, "name": "無名駅B"},
    ]
    ids_original = {s["name"]: s["station_id"] for s in assign_placeholder_station_ids(stations)}
    ids_reversed = {
        s["name"]: s["station_id"] for s in assign_placeholder_station_ids(stations[::-1])
    }
    assert ids_original == ids_reversed
    # 正式IDを持つ駅はそのまま、無名駅同士は異なるIDになる
    assert ids_original["正式ID駅"] == "P35_001"
    assert ids_original["無名駅A"].startswith("NOID_")
    assert ids_original["無名駅A"] != ids_original["無名駅B"]


def test_build_placeholder_station_id_is_deterministic():
    """同じ駅名からは常に同じ仮ID（NOID_ + SHA-1先頭8桁）が生成される"""
    first = build_placeholder_station_id("テスト駅")
    second = build_placeholder_station_id("テスト駅")
    assert first == second
    assert first.startswith("NOID_")
    assert len(first) == len("NOID_") + 8
