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
    name: str
    normalized_name: str
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
    dataset_id: str
    dataset_name: str
    row_count: int
    columns: list[ColumnProfile] = Field(default_factory=list)


class DatasetHandle(BaseModel):
    dataset_id: str
    dataset_name: str
    schema_profile: SchemaProfile
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)


class UploadResponse(BaseModel):
    source: DatasetHandle
    target: DatasetHandle


class SqlTableDiscoveryResponse(BaseModel):
    tables: list[str] = Field(default_factory=list)
