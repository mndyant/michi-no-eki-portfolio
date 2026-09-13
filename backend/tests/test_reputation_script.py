import pytest

from scripts.extract_reputation import clean_json_response


@pytest.mark.parametrize(('text', 'expected'), [
    ('["梅干し", "海鮮丼"]', ['梅干し', '海鮮丼']),
    ('```json\n["梅干し"]\n```', ['梅干し']),
    ('{"error": "invalid"}', []),
    ('not json', []),
])
def test_review_extraction_parses_only_a_json_list(text, expected):
    assert clean_json_response(text) == expected
