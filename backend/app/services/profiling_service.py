from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.models.schema import ColumnProfile, SchemaProfile
from app.utils.normalization import normalize_name, tokenize_name


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-()]{5,14}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", re.IGNORECASE)
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d")


def build_schema_profile(rows: list[dict[str, Any]], dataset_id: str, dataset_name: str) -> SchemaProfile:
    columns = []
    column_names = list(rows[0].keys()) if rows else []
    for column_name in column_names:
        values = [row.get(column_name) for row in rows]
        columns.append(profile_column(values, column_name))
    return SchemaProfile(
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        row_count=len(rows),
        columns=columns,
    )


def profile_column(values: list[Any], column_name: str) -> ColumnProfile:
    non_null = [value for value in values if not is_nullish(value)]
    stringified = [to_text(value) for value in non_null[: settings.max_profile_samples]]
    distinct_sample = distinct_values(non_null)[: settings.max_profile_samples]
    avg_length = sum(len(item) for item in stringified) / len(stringified) if stringified else 0.0
    detected_patterns = detect_patterns(non_null)

    denominator = max(len(values), 1)
    unique_ratio = float(len({to_text(value) for value in non_null}) / denominator)
    null_ratio = float((len(values) - len(non_null)) / denominator) if values else 0.0
    dtype = infer_dtype(non_null)

    return ColumnProfile(
        name=column_name,
        normalized_name=normalize_name(column_name),
        dtype=dtype,
        null_ratio=round(null_ratio, 4),
        unique_ratio=round(unique_ratio, 4),
        avg_length=round(avg_length, 2),
        non_null_count=len(non_null),
        sample_values=stringified,
        distinct_sample_values=[to_text(value) for value in distinct_sample],
        detected_patterns=detected_patterns,
        tokenized_name=tokenize_name(column_name),
    )


def detect_patterns(non_null: list[Any]) -> list[str]:
    if not non_null:
        return ["empty"]

    values = [to_text(value) for value in non_null[:25]]
    pattern_hits: Counter[str] = Counter()

    if match_ratio(values, is_date_like) >= 0.8:
        pattern_hits["date"] += 1

    numeric_values = [safe_float(value) for value in values]
    present_numeric = [value for value in numeric_values if value is not None]
    if present_numeric and (len(present_numeric) / len(values)) >= 0.8:
        if all(float(value).is_integer() for value in present_numeric):
            pattern_hits["integer"] += 1
        else:
            pattern_hits["float"] += 1
        if len({to_text(value) for value in non_null}) / max(len(non_null), 1) >= 0.9:
            pattern_hits["numeric_id"] += 1

    for value in values:
        lowered = value.lower()
        if EMAIL_RE.match(lowered):
            pattern_hits["email"] += 1
        if PHONE_RE.match(value):
            pattern_hits["phone"] += 1
        if UUID_RE.match(lowered):
            pattern_hits["uuid"] += 1

    if not pattern_hits:
        unique_ratio = len({to_text(value) for value in non_null}) / max(len(non_null), 1)
        pattern_hits["categorical" if unique_ratio <= 0.3 else "text"] += 1

    return [pattern for pattern, _count in pattern_hits.most_common()[:3]]


def to_text(value: object) -> str:
    return "" if value is None else str(value)


def distinct_values(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        marker = to_text(value)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def infer_dtype(values: list[Any]) -> str:
    if not values:
        return "empty"
    if all(safe_int(to_text(value)) is not None for value in values[:10]):
        return "integer"
    if all(safe_float(to_text(value)) is not None for value in values[:10]):
        return "float"
    if all(is_date_like(to_text(value)) for value in values[:10]):
        return "date"
    return "string"


def safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def safe_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def is_date_like(value: str) -> bool:
    for pattern in DATE_FORMATS:
        try:
            datetime.strptime(value, pattern)
            return True
        except ValueError:
            continue
    return False


def is_nullish(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def match_ratio(values: list[str], predicate: callable) -> float:
    if not values:
        return 0.0
    matches = sum(1 for value in values if predicate(value))
    return matches / len(values)