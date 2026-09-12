# 推薦理由生成（app/services/ai/reason_generator.py）の単体テスト
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai.reason_generator import generate_plan_reason  # noqa: E402


def test_方面希望が理由文に反映される():
    reason = generate_plan_reason(
        profile_key="max", station_count=5, finish_time="15:00", requested_directions=["南"]
    )
    assert "南" in reason
    assert "5駅" in reason
    assert "15:00" in reason


def test_方面希望が無ければ言及しない():
    reason = generate_plan_reason(
        profile_key="light", station_count=3, finish_time="10:00", requested_directions=[]
    )
    assert "方面希望" not in reason
    assert "3駅" in reason


def test_未知のプロファイルキーはデフォルトテンプレートになる():
    reason = generate_plan_reason(
        profile_key="unknown", station_count=2, finish_time="09:00", requested_directions=[]
    )
    assert "2駅" in reason
    assert "09:00" in reason


def test_全プロファイルキーで理由文が生成できる():
    for key in ("max", "light", "gourmet", "rare", "far_first"):
        reason = generate_plan_reason(
            profile_key=key, station_count=4, finish_time="12:00", requested_directions=["東"]
        )
        assert reason  # 空文字にならない
        assert "4駅" in reason
