from __future__ import annotations

import re


def normalize_alias_text(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", value).strip().lower()
    return " ".join(token for token in cleaned.split() if token)


def split_csv_values(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]