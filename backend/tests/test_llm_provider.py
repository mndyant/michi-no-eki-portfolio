# Claude API呼び出しの抽象化（app/services/ai/llm_provider.py）の単体テスト
# ANTHROPIC_API_KEY未設定時の挙動（=デフォルトの開発環境）を担保する
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.ai import llm_provider  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_キー未設定なら利用不可():
    assert llm_provider.is_llm_available() is False


def test_キー未設定ならcompleteはNoneを返す():
    assert llm_provider.complete("こんにちは") is None


def test_キーを設定すればSDKインストール時は利用可能判定になる():
    import app.services.ai.llm_provider as mod

    if mod.anthropic is None:
        pytest.skip("anthropic SDK未インストール環境")
    import os

    os.environ["ANTHROPIC_API_KEY"] = "dummy-key-for-test"
    try:
        assert llm_provider.is_llm_available() is True
    finally:
        del os.environ["ANTHROPIC_API_KEY"]
