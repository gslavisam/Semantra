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
    """Session-scoped handle combining schema profile metadata and preview rows."""

    dataset_id: str
    dataset_name: str
    schema_profile: SchemaProfile
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)


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
