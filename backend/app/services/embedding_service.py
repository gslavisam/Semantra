from __future__ import annotations

import hashlib
import math

from app.core.config import settings
from app.utils.normalization import semantic_token_set


def is_enabled() -> bool:
    return settings.embedding_provider.lower() != "none"


def get_embedding(text: str) -> list[float] | None:
    provider = settings.embedding_provider.lower()
    if provider == "none":
        return None
    if provider == "hash":
        return _hash_embedding(text)
    return None


def cosine_similarity(left: list[float] | None, right: list[float] | None) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * settings.embedding_dimensions
    for token in sorted(semantic_token_set(text)):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % settings.embedding_dimensions
        sign = 1.0 if digest[2] % 2 == 0 else -1.0
        magnitude = 1.0 + ((digest[3] / 255.0) * 0.25)
        vector[index] += sign * magnitude
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]