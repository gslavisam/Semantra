"""Schema profiling and dataset-handle models used by ingestion and mapping flows."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


DetectedPattern = Literal[
    "empty",
    "email",
    "phone",
    "uuid",
    "date",
    "numeric_id",
    "integer",
    "float",
    "categorical",
    "text",
    "mixed",
]


class ColumnProfile(BaseModel):
    """Profile of one dataset column used during mapping and preview flows."""

    name: str
    normalized_name: str
    description: str = ""
    declared_type: str = ""
    dtype: str
    null_ratio: float
    unique_ratio: float
    avg_length: float = 0.0
    non_null_count: int
    sample_values: list[str] = Field(default_factory=list)
    distinct_sample_values: list[str] = Field(default_factory=list)
    detected_patterns: list[DetectedPattern] = Field(default_factory=list)
    tokenized_name: list[str] = Field(default_factory=list)


class SchemaProfile(BaseModel):
    """Profile of an uploaded dataset schema and its detected columns."""

    dataset_id: str
    dataset_name: str
    row_count: int
    columns: list[ColumnProfile] = Field(default_factory=list)


class DatasetHandle(BaseModel):
    """Dataset handle combining schema profile metadata and preview rows."""

    dataset_id: str
    dataset_name: str
    schema_profile: SchemaProfile
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)


DatasetStorageMode = Literal["row_data", "schema_only"]


class PersistedDatasetRecord(BaseModel):
    """Durable uploaded-dataset payload stored behind the upload runtime facade."""

    dataset_id: str
    dataset_name: str
    schema_profile: SchemaProfile
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)
    storage_mode: DatasetStorageMode = "row_data"
    source_format: str = ""
    selected_table: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_handle(self) -> DatasetHandle:
        return DatasetHandle(
            dataset_id=self.dataset_id,
            dataset_name=self.dataset_name,
            schema_profile=self.schema_profile,
            preview_rows=list(self.preview_rows),
        )


class SpecLayoutHint(BaseModel):
    """Detected or user-specified mapping of schema-spec columns to semantic roles."""

    name_col: str
    description_col: str | None = None
    type_col: str | None = None
    sample_values_col: str | None = None
    confidence: float


class SpecDetectionResponse(BaseModel):
    """Response returned after attempting to detect a schema-spec layout."""

    hint: SpecLayoutHint | None = None


SpecRecoveryStatus = Literal[
    "recovered",
    "unavailable",
    "no_suggestion",
    "invalid_suggestion",
    "replay_failed",
]


class SpecRecoverySuggestion(BaseModel):
    """Bounded recovery proposal for a schema-spec upload that did not match deterministic heuristics."""

    detected_mode: Literal["spec", "row_data", "unknown"] = "unknown"
    sheet_name: str | None = None
    header_row_index: int | None = None
    record_path: str | None = None
    name_col: str | None = None
    description_col: str | None = None
    type_col: str | None = None
    sample_values_col: str | None = None
    selected_table: str | None = None
    confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)


class SpecRecoveryResponse(BaseModel):
    """Response returned after bounded schema-spec recovery analysis and deterministic replay."""

    status: SpecRecoveryStatus
    suggestion: SpecRecoverySuggestion | None = None
    hint: SpecLayoutHint | None = None
    warnings: list[str] = Field(default_factory=list)
    failure_reason: str = ""


class UploadResponse(BaseModel):
    """Response containing the stored source and target dataset handles."""

    source: DatasetHandle
    target: DatasetHandle


class MetadataEnrichmentResponse(BaseModel):
    """Response returned after companion metadata is merged into a dataset handle."""

    dataset: DatasetHandle
    matched_columns: int
    unmatched_columns: list[str] = Field(default_factory=list)


class SqlTableDiscoveryResponse(BaseModel):
    """Response containing table names discovered in an uploaded SQL snapshot."""

    tables: list[str] = Field(default_factory=list)
