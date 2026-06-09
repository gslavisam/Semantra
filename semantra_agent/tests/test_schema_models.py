"""Unit tests for semantra_core.models.schema.

Covers the public Pydantic models used by ingestion and mapping flows:
``ColumnProfile``, ``SchemaProfile``, ``DatasetHandle``,
``PersistedDatasetRecord``, ``SpecLayoutHint``, and the response wrappers
for upload, recovery, and metadata enrichment.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from semantra_core.models.schema import (
    ColumnProfile,
    DatasetHandle,
    MetadataEnrichmentResponse,
    PersistedDatasetRecord,
    SchemaProfile,
    SpecDetectionResponse,
    SpecLayoutHint,
    SpecRecoveryResponse,
    SpecRecoverySuggestion,
    SqlTableDiscoveryResponse,
    UploadResponse,
)


# ---------------------------------------------------------------------------
# ColumnProfile
# ---------------------------------------------------------------------------


def test_column_profile_minimal_required_fields(column_id: ColumnProfile) -> None:
    """ColumnProfile should be constructible from the minimum required fields."""
    assert column_id.name == "id"
    assert column_id.normalized_name == "id"
    assert column_id.dtype == "str"
    assert column_id.null_ratio == 0.0
    assert column_id.unique_ratio == 1.0
    assert column_id.non_null_count == 100
    # Defaults
    assert column_id.avg_length == 0.0
    assert column_id.sample_values == []
    assert column_id.distinct_sample_values == []
    assert column_id.detected_patterns == []
    assert column_id.tokenized_name == []
    assert column_id.description == ""
    assert column_id.declared_type == ""


def test_column_profile_detected_patterns_accept_known_values(
    column_email: ColumnProfile,
) -> None:
    """Detected patterns should round-trip the values that were provided."""
    assert column_email.detected_patterns == ["email"]
    assert column_email.sample_values == ["a@example.com", "b@example.com"]


def test_column_profile_rejects_missing_required_fields() -> None:
    """Omitting required fields must raise a ValidationError, not silently coerce."""
    with pytest.raises(ValidationError):
        ColumnProfile(name="x")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# SchemaProfile
# ---------------------------------------------------------------------------


def test_schema_profile_round_trip(source_schema: SchemaProfile) -> None:
    """SchemaProfile should preserve all child column profiles on round-trip."""
    assert source_schema.dataset_id == "src"
    assert source_schema.dataset_name == "users_source"
    assert source_schema.row_count == 100
    assert len(source_schema.columns) == 2
    assert source_schema.columns[0].name == "id"
    assert source_schema.columns[1].detected_patterns == ["email"]


def test_schema_profile_default_columns_is_empty_list() -> None:
    """When no columns are supplied, the profile should expose an empty list."""
    profile = SchemaProfile(
        dataset_id="x", dataset_name="x", row_count=0
    )
    assert profile.columns == []


# ---------------------------------------------------------------------------
# DatasetHandle
# ---------------------------------------------------------------------------


def test_dataset_handle_defaults_preview_rows_to_empty(source_schema: SchemaProfile) -> None:
    """DatasetHandle.preview_rows should default to an empty list, never None."""
    handle = DatasetHandle(
        dataset_id="src",
        dataset_name="src",
        schema_profile=source_schema,
    )
    assert handle.preview_rows == []


def test_dataset_handle_preserves_preview_rows(source_handle: DatasetHandle) -> None:
    """Preview rows should be preserved exactly as provided."""
    assert source_handle.preview_rows == [
        {"id": "1", "email_address": "a@example.com"}
    ]


# ---------------------------------------------------------------------------
# PersistedDatasetRecord / to_handle
# ---------------------------------------------------------------------------


def test_persisted_dataset_record_to_handle_strips_storage_metadata(
    source_schema: SchemaProfile,
) -> None:
    """``to_handle`` should drop storage-only fields and return a DatasetHandle."""
    record = PersistedDatasetRecord(
        dataset_id="src",
        dataset_name="users_source",
        schema_profile=source_schema,
        preview_rows=[{"id": "1"}],
        storage_mode="schema_only",
        source_format="csv",
        selected_table="users",
        created_at="2025-01-01T00:00:00Z",
        updated_at="2025-01-02T00:00:00Z",
    )

    handle = record.to_handle()

    assert isinstance(handle, DatasetHandle)
    assert handle.dataset_id == "src"
    assert handle.dataset_name == "users_source"
    assert handle.schema_profile is source_schema
    assert handle.preview_rows == [{"id": "1"}]
    # The storage-mode/source-format/timestamps must NOT leak into the handle.
    assert not hasattr(handle, "storage_mode")
    assert not hasattr(handle, "source_format")
    assert not hasattr(handle, "created_at")


def test_persisted_dataset_record_storage_mode_literal() -> None:
    """The storage_mode field must validate against the DatasetStorageMode literal."""
    record = PersistedDatasetRecord(
        dataset_id="x",
        dataset_name="x",
        schema_profile=SchemaProfile(
            dataset_id="x", dataset_name="x", row_count=0
        ),
    )
    assert record.storage_mode == "row_data"
    # Literal type should reject unknown storage modes.
    with pytest.raises(ValidationError):
        PersistedDatasetRecord(
            dataset_id="x",
            dataset_name="x",
            schema_profile=SchemaProfile(
                dataset_id="x", dataset_name="x", row_count=0
            ),
            storage_mode="cloud_only",  # type: ignore[arg-type]
        )


def test_persisted_dataset_record_default_storage_mode() -> None:
    """Default storage_mode should be 'row_data'."""
    record = PersistedDatasetRecord(
        dataset_id="x",
        dataset_name="x",
        schema_profile=SchemaProfile(
            dataset_id="x", dataset_name="x", row_count=0
        ),
    )
    assert record.storage_mode == "row_data"


# ---------------------------------------------------------------------------
# Spec layout / recovery
# ---------------------------------------------------------------------------


def test_spec_layout_hint_round_trip() -> None:
    """SpecLayoutHint should round-trip name, optional columns, and confidence."""
    hint = SpecLayoutHint(
        name_col="field",
        description_col="desc",
        type_col="type",
        sample_values_col="samples",
        confidence=0.85,
    )
    assert hint.name_col == "field"
    assert hint.description_col == "desc"
    assert hint.type_col == "type"
    assert hint.sample_values_col == "samples"
    assert hint.confidence == 0.85

    # Optional columns should be allowed to be None.
    minimal = SpecLayoutHint(name_col="x", confidence=0.5)
    assert minimal.description_col is None
    assert minimal.type_col is None
    assert minimal.sample_values_col is None


def test_spec_detection_response_hint_optional() -> None:
    """SpecDetectionResponse should allow no hint to be detected."""
    response = SpecDetectionResponse(hint=None)
    assert response.hint is None


def test_spec_recovery_response_status_literal_validation() -> None:
    """SpecRecoveryResponse.status must validate against the SpecRecoveryStatus literal."""
    response = SpecRecoveryResponse(status="recovered")
    assert response.status == "recovered"
    assert response.warnings == []
    assert response.failure_reason == ""

    with pytest.raises(ValidationError):
        SpecRecoveryResponse(status="not_a_real_status")  # type: ignore[arg-type]


def test_spec_recovery_suggestion_defaults() -> None:
    """SpecRecoverySuggestion should expose sensible defaults for missing fields."""
    suggestion = SpecRecoverySuggestion()
    assert suggestion.detected_mode == "unknown"
    assert suggestion.sheet_name is None
    assert suggestion.header_row_index is None
    assert suggestion.record_path is None
    assert suggestion.warnings == []


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------


def test_upload_response_contains_source_and_target(
    source_handle: DatasetHandle,
) -> None:
    """UploadResponse should expose both source and target handles."""
    target_handle = DatasetHandle(
        dataset_id="tgt",
        dataset_name="tgt",
        schema_profile=SchemaProfile(
            dataset_id="tgt", dataset_name="tgt", row_count=0
        ),
    )
    response = UploadResponse(source=source_handle, target=target_handle)
    assert response.source is source_handle
    assert response.target is target_handle


def test_metadata_enrichment_response_defaults(source_handle: DatasetHandle) -> None:
    """MetadataEnrichmentResponse should default unmatched_columns to []."""
    response = MetadataEnrichmentResponse(
        dataset=source_handle,
        matched_columns=2,
    )
    assert response.matched_columns == 2
    assert response.unmatched_columns == []


def test_sql_table_discovery_response_defaults() -> None:
    """SqlTableDiscoveryResponse should default tables to an empty list."""
    response = SqlTableDiscoveryResponse()
    assert response.tables == []
