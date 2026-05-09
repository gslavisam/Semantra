from __future__ import annotations

import json

import pytest

from app.services.profiling_service import build_schema_profile
from app.services.tabular_upload_service import normalize_rows


def test_normalize_rows_reuses_shared_header_and_cell_normalization() -> None:
    rows = normalize_rows(
        [{" Customer ID ": 1, "meta": {"source": "erp"}}, {"Customer ID": 2, "meta": {"source": "crm"}}],
        header_order=[" Customer ID ", "meta"],
    )

    assert rows == [
        {"Customer ID": 1, "meta": json.dumps({"source": "erp"}, ensure_ascii=True)},
        {"Customer ID": 2, "meta": json.dumps({"source": "crm"}, ensure_ascii=True)},
    ]


def test_build_schema_profile_uses_shared_nullish_logic() -> None:
    profile = build_schema_profile(
        [{"customer_id": 1, "email": "ana@example.com"}, {"customer_id": " ", "email": None}],
        dataset_id="source",
        dataset_name="source.csv",
    )

    customer_id_column = next(column for column in profile.columns if column.name == "customer_id")
    email_column = next(column for column in profile.columns if column.name == "email")

    assert customer_id_column.non_null_count == 1
    assert customer_id_column.null_ratio == 0.5
    assert email_column.non_null_count == 1


def test_build_schema_profile_does_not_classify_iso_dates_as_phone_numbers() -> None:
    profile = build_schema_profile(
        [{"ERSDA": "2023-01-10"}, {"ERSDA": "2022-09-18"}, {"ERSDA": "2024-02-07"}],
        dataset_id="source",
        dataset_name="source.csv",
    )

    created_date_column = next(column for column in profile.columns if column.name == "ERSDA")

    assert "date" in created_date_column.detected_patterns
    assert "phone" not in created_date_column.detected_patterns


def test_normalize_rows_rejects_empty_headers() -> None:
    with pytest.raises(ValueError, match="Column names must be non-empty"):
        normalize_rows([{"   ": "value"}])