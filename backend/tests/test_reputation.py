# -*- coding: utf-8 -*-
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.extract_reputation import clean_json_response

def test_clean_json_response_正常系():
    raw_response = '["まいたけ弁当", "まいたけコロッケ"]'
    result = clean_json_response(raw_response)
    assert result == ["まいたけ弁当", "まいたけコロッケ"]


def test_clean_json_response_マークダウン装飾あり():
    raw_response = '```json\n["梅干し", "梅ゼリー"]\n```'
    result = clean_json_response(raw_response)
    assert result == ["梅干し", "梅ゼリー"]


def test_clean_json_response_異常なフォーマットは空リストを返す():
    raw_response = 'おすすめは梅干しと梅ゼリーです。'
    result = clean_json_response(raw_response)
    assert result == []
