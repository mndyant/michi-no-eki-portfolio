# 自然文条件解釈（app/services/ai/nl_parser.py）の単体テスト
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai.nl_parser import parse_free_text  # noqa: E402


def test_方面と到着締切を抽出():
    result = parse_free_text("南方面を回って16:30までに最終駅に着きたい")
    assert result["directions"] == ["南"]
    assert result["last_arrival_by"] == "16:30"


def test_帰着時刻を抽出():
    result = parse_free_text("18時に戻りたい")
    assert result["return_by"] == "18:00"


def test_高速利用と訪問済み含むを抽出():
    result = parse_free_text("高速を使って、訪問済みも含めて回りたい")
    assert result["use_highway"] is True
    assert result["include_visited"] is True


def test_駅数の指定を抽出():
    result = parse_free_text("3駅くらい回りたい")
    assert result["max_stations"] == 3


def test_地名の部分一致で方面を誤検出しない():
    # 「西宮」に「西」が含まれるが、「西方面」のような接尾語が無いので拾わない
    result = parse_free_text("西宮のあたりに行きたい")
    assert "directions" not in result


def test_何も無ければ空辞書():
    assert parse_free_text("とくに希望はありません") == {}


def test_範囲外の時刻は無視される():
    # 25時のような不正な時刻は拾わない
    result = parse_free_text("25:99までに着きたい")
    assert "last_arrival_by" not in result
