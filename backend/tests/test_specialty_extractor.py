# 名産・特徴のルールベース抽出（app/services/rag/specialty_extractor.py）の単体テスト
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rag.specialty_extractor import extract_specialty_candidates  # noqa: E402


def test_名産キーワードを含む文だけ抽出される():
    contents = [
        "道の駅「舞鶴港とれとれセンター」について（Wikipedia）:\n"
        "舞鶴漁港で水揚げされた魚介類や、丹後地方の名産品を販売する観光施設。\n"
        "隣接する道の駅では交通情報なども提供している。"
    ]
    result = extract_specialty_candidates(contents)
    assert len(result) == 1
    assert "名産品" in result[0]
    assert "交通情報" not in "".join(result)


def test_キーワードが無ければ空リスト():
    contents = ["道の駅河野は福井県南条郡南越前町にある国道8号の道の駅である"]
    assert extract_specialty_candidates(contents) == []


def test_複数チャンク_複数キーワードにマッチする():
    contents = [
        "この地域の名物は柿の葉寿司である",
        "隣町では特産の梅干しも有名",
        "施設情報には言及なし",
    ]
    result = extract_specialty_candidates(contents)
    assert len(result) == 2


def test_同一文の重複は除去される():
    contents = ["名物のいちご大福が人気", "名物のいちご大福が人気"]
    assert extract_specialty_candidates(contents) == ["名物のいちご大福が人気"]


def test_空文字列や空白のみの文は無視される():
    contents = ["", "   ", "\n\n"]
    assert extract_specialty_candidates(contents) == []
