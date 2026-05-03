from __future__ import annotations

import json
from typing import Any


def decode_text_payload(payload: bytes) -> str:
    return payload.decode("utf-8-sig")


def is_nullish(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def normalize_tabular_header(value: Any) -> str:
    header = "" if value is None else str(value).strip()
    if not header:
        raise ValueError("Column names must be non-empty")
    return header


def normalize_tabular_cell(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, ensure_ascii=True, default=str)