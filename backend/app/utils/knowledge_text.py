"""Canonical alias text normalization and filtering helpers for the knowledge layer."""

from __future__ import annotations

import re
from typing import Iterable


def normalize_alias_text(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return " ".join(token for token in cleaned.split() if token)


def split_csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_canonical_alias_text(value: str) -> str:
    normalized = normalize_alias_text(value)
    if not normalized:
        return ""
    if all(token.isdigit() for token in normalized.split()):
        return ""
    return normalized


def filter_canonical_aliases(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    filtered: list[str] = []
    for value in values:
        normalized = normalize_canonical_alias_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        filtered.append(normalized)
    return filtered