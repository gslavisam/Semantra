"""Shared fixtures for semantra_agent tests.

The fixtures here are deliberately minimal — enough to construct the
Pydantic models that the SDK exposes (``SchemaProfile``, ``DatasetHandle``,
``ColumnProfile``). Tests that need richer data (real CSV/JSON/XLSX files
from ``ui_fixtures/``) are in ``tests/test_e2e_*.py``.
"""

from __future__ import annotations

import pytest

from semantra_core.models.schema import (
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)


@pytest.fixture
def column_id() -> ColumnProfile:
    """A single deterministic identifier column profile."""
    return ColumnProfile(
        name="id",
        normalized_name="id",
        dtype="str",
        null_ratio=0.0,
        unique_ratio=1.0,
        non_null_count=100,
    )


@pytest.fixture
def column_email() -> ColumnProfile:
    """A column profile with email-like pattern metadata."""
    return ColumnProfile(
        name="email_address",
        normalized_name="email_address",
        dtype="str",
        null_ratio=0.1,
        unique_ratio=0.95,
        non_null_count=90,
        detected_patterns=["email"],
        sample_values=["a@example.com", "b@example.com"],
    )


@pytest.fixture
def source_schema(column_id: ColumnProfile, column_email: ColumnProfile) -> SchemaProfile:
    """A source dataset schema with two columns."""
    return SchemaProfile(
        dataset_id="src",
        dataset_name="users_source",
        row_count=100,
        columns=[column_id, column_email],
    )


@pytest.fixture
def target_schema() -> SchemaProfile:
    """A target dataset schema with one matching identifier column."""
    return SchemaProfile(
        dataset_id="tgt",
        dataset_name="users_target",
        row_count=200,
        columns=[
            ColumnProfile(
                name="user_id",
                normalized_name="user_id",
                dtype="str",
                null_ratio=0.0,
                unique_ratio=1.0,
                non_null_count=200,
            ),
        ],
    )


@pytest.fixture
def source_handle(source_schema: SchemaProfile) -> DatasetHandle:
    """A source DatasetHandle wrapping the source schema and a small preview."""
    return DatasetHandle(
        dataset_id="src",
        dataset_name="users_source",
        schema_profile=source_schema,
        preview_rows=[{"id": "1", "email_address": "a@example.com"}],
    )
