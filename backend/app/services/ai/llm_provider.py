# Claude API呼び出しの抽象化（distance providerと同じパターン）。
# ANTHROPIC_API_KEY未設定・SDK未インストール・呼び出し失敗のいずれでもNoneを返すので、
# 呼び出し側（nl_parser/reason_generator）は必ずルールベース結果へフォールバックすること。
# これにより「APIキー無しでも全機能が動く」制約（CLAUDE.md）を満たす。
from __future__ import annotations

import os

try:
    import anthropic
except ImportError:  # SDK未インストールでも動くようにする
    anthropic = None  # type: ignore[assignment]

DEFAULT_MODEL = os.getenv("LLM_MODEL", "claude-haiku-4-5-20251001")


def is_llm_available() -> bool:
    """ANTHROPIC_API_KEYが設定され、かつSDKがインストールされているかを返す。"""
    return bool(os.getenv("ANTHROPIC_API_KEY")) and anthropic is not None


def complete(prompt: str, *, max_tokens: int = 300) -> str | None:
    """Claude APIで応答テキストを生成する。

    利用不可（キー未設定/SDK未インストール）または呼び出し失敗（ネットワークエラー等）の
    場合はNoneを返す。例外を外へ投げない（呼び出し側の自然文解釈・推薦理由生成が
    Claude API任意である以上、失敗してもルールベースで応答を返し続けられるようにするため）。
    """
    if not is_llm_available():
        return None
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=DEFAULT_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None
