from __future__ import annotations

from difflib import SequenceMatcher


def clamp_score(value: float) -> float:
    return max(0.0, min(1.0, value))


def fuzzy_similarity(left: str, right: str) -> float:
    return clamp_score(SequenceMatcher(None, left, right).ratio())


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return clamp_score(len(left & right) / len(left | right))


def score_distance(left: float, right: float) -> float:
    return clamp_score(1.0 - abs(left - right))