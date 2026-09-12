# 名産・特徴のルールベース抽出
# 駅のチャンク本文（主にWikipedia抜粋）から「名産」「名物」等のキーワードを含む文を
# そのまま候補として抜き出す。文の要約・言い換え・商品名の作文は行わない
# （事実にない商品名を生成してしまうハルシネーションを避けるため）。
# Claude APIによる要約はIssue #52のllm_provider実装後に別途足す。
from __future__ import annotations

import re

SPECIALTY_KEYWORDS = ("名産", "名物", "特産", "名品")


def extract_specialty_candidates(contents: list[str]) -> list[str]:
    """チャンク本文群から名産・名物に言及する文を抽出する（重複除去・出現順）。"""
    candidates: list[str] = []
    seen: set[str] = set()
    for content in contents:
        for sentence in re.split(r"[。\n]", content):
            sentence = sentence.strip()
            if not sentence or sentence in seen:
                continue
            if any(keyword in sentence for keyword in SPECIALTY_KEYWORDS):
                seen.add(sentence)
                candidates.append(sentence)
    return candidates
