from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.distance.base import TravelEstimate  # noqa: E402
from app.services.route.mountain_factor import (  # noqa: E402
    MOUNTAIN_CORRECTION_RATIO,
    apply_mountain_correction,
)

# Issue #73: 道路係数1.3は都市部で正確だが、山間部は1.55〜1.94相当必要と判明したため、
# 区間のどちらかの端点が山間駅なら1.6相当（1.3の約1.23倍）に補正する。


def test_non_mountainous_leg_is_unchanged() -> None:
    estimate = TravelEstimate(distance_km=50.0, duration_min=75.0, source="haversine")
    result = apply_mountain_correction(estimate, is_mountainous=False)
    assert result == estimate


def test_mountainous_leg_scales_distance_and_duration() -> None:
    estimate = TravelEstimate(distance_km=50.0, duration_min=75.0, source="haversine")
    result = apply_mountain_correction(estimate, is_mountainous=True)
    assert result.distance_km == pytest.approx(50.0 * MOUNTAIN_CORRECTION_RATIO)
    assert result.duration_min == pytest.approx(75.0 * MOUNTAIN_CORRECTION_RATIO)
    assert result.source == "haversine+mountain"
    # 1.3ベース→1.6相当への補正であることの確認（約1.2308倍）
    assert MOUNTAIN_CORRECTION_RATIO == pytest.approx(1.6 / 1.3)


def test_osrm_source_is_never_corrected() -> None:
    """OSRMは実道路距離のため、山間駅が絡んでも補正しない。"""
    estimate = TravelEstimate(distance_km=50.0, duration_min=75.0, source="osrm")
    result = apply_mountain_correction(estimate, is_mountainous=True)
    assert result == estimate


def test_non_haversine_test_source_is_never_corrected() -> None:
    """テスト用の固定プロバイダ（source="test"）等、haversine以外も補正しない。"""
    estimate = TravelEstimate(distance_km=50.0, duration_min=75.0, source="test")
    result = apply_mountain_correction(estimate, is_mountainous=True)
    assert result == estimate
