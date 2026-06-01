"""Session-scoped in-memory dataset store for uploaded rows and schema profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from dataclasses import dataclass
from threading import Lock
from typing import Any
from uuid import uuid4

from app.models.schema import DatasetHandle, PersistedDatasetRecord, SchemaProfile
from app.core.config import settings
from app.services.profiling_service import build_schema_profile
from app.services.uploaded_dataset_repository import UploadedDatasetRepository, uploaded_dataset_repository


@dataclass
class StoredDataset:
    """Stored upload record containing source rows and the derived dataset handle."""

    dataset_id: str
    dataset_name: str
    rows: list[dict[str, Any]]
    handle: DatasetHandle


class InMemoryDatasetStore:
    """Session-scoped in-memory store for uploaded datasets and metadata-enriched handles."""

    def __init__(self, repository: UploadedDatasetRepository | None = None) -> None:
        self._items: dict[str, StoredDataset] = {}
        self._lock = Lock()
        self._repository = repository or uploaded_dataset_repository

    def save_rows(
        self,
        rows: list[dict[str, Any]],
        dataset_name: str,
        *,
        source_format: str = "row_data",
    ) -> DatasetHandle:
        """Create a schema profile from raw rows and persist the resulting dataset handle in memory."""

        dataset_id = str(uuid4())
        profile = build_schema_profile(rows, dataset_id=dataset_id, dataset_name=dataset_name)
        return self.save_schema_profile(
            profile,
            dataset_name=dataset_name,
            rows=rows,
            source_format=source_format,
            storage_mode="row_data",
        )

    def save_schema_profile(
        self,
        profile: SchemaProfile,
        dataset_name: str,
        rows: list[dict[str, Any]] | None = None,
        *,
        source_format: str = "schema_profile",
        storage_mode: str = "schema_only",
        selected_table: str | None = None,
    ) -> DatasetHandle:
        dataset_id = profile.dataset_id
        stored_rows = list((rows or [])[: settings.max_upload_preview_rows])
        handle = DatasetHandle(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            schema_profile=profile,
            preview_rows=stored_rows[: settings.max_upload_preview_rows],
        )
        persisted = self._repository.save_dataset(
            PersistedDatasetRecord(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                schema_profile=profile,
                preview_rows=list(handle.preview_rows),
                storage_mode=str(storage_mode or "schema_only"),
                source_format=str(source_format or "schema_profile"),
                selected_table=selected_table,
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
        handle = persisted.to_handle()
        with self._lock:
            self._items[dataset_id] = StoredDataset(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                rows=stored_rows,
                handle=handle,
            )
        return handle

    def get_dataset(self, dataset_id: str) -> StoredDataset:
        """Return one stored dataset by id or raise when the id is unknown."""

        with self._lock:
            cached = self._items.get(dataset_id)
            if cached is not None:
                return cached

        try:
            persisted = self._repository.get_dataset(dataset_id)
        except KeyError as error:
            raise KeyError(f"Unknown dataset_id: {dataset_id}") from error

        stored = StoredDataset(
            dataset_id=persisted.dataset_id,
            dataset_name=persisted.dataset_name,
            rows=list(persisted.preview_rows),
            handle=persisted.to_handle(),
        )
        with self._lock:
            self._items[dataset_id] = stored
        return stored

    def merge_companion_metadata(
        self,
        dataset_id: str,
        companion_profile: SchemaProfile,
    ) -> tuple[DatasetHandle, int, list[str]]:
        with self._lock:
            stored = self._items.get(dataset_id)
        if stored is None:
            stored = self.get_dataset(dataset_id)

        with self._lock:
            current = self._items.get(dataset_id, stored)

            existing_columns = list(current.handle.schema_profile.columns)
            existing_index = {_column_merge_key(column.name): column for column in existing_columns}
            companion_index = {_column_merge_key(column.name): column for column in companion_profile.columns}

            matched_columns = 0
            merged_columns = []
            for column in existing_columns:
                companion = companion_index.get(_column_merge_key(column.name))
                if companion is None:
                    merged_columns.append(column)
                    continue

                matched_columns += 1
                merged_columns.append(
                    column.model_copy(
                        update={
                            "description": companion.description or column.description,
                            "declared_type": companion.declared_type or column.declared_type,
                            "sample_values": companion.sample_values or column.sample_values,
                            "distinct_sample_values": companion.distinct_sample_values or column.distinct_sample_values,
                        }
                    )
                )

            if matched_columns == 0:
                raise ValueError("Companion metadata did not match any existing dataset columns.")

            unmatched_columns = [
                column.name
                for key, column in companion_index.items()
                if key not in existing_index
            ]

            updated_profile = stored.handle.schema_profile.model_copy(update={"columns": merged_columns})
            updated_handle = DatasetHandle(
                dataset_id=current.handle.dataset_id,
                dataset_name=current.handle.dataset_name,
                schema_profile=updated_profile,
                preview_rows=list(current.handle.preview_rows),
            )
            persisted = self._repository.save_dataset(
                PersistedDatasetRecord(
                    dataset_id=updated_handle.dataset_id,
                    dataset_name=updated_handle.dataset_name,
                    schema_profile=updated_profile,
                    preview_rows=list(updated_handle.preview_rows),
                    storage_mode="row_data" if current.rows else "schema_only",
                    source_format=_infer_source_format(updated_handle.dataset_name),
                    created_at=datetime.now(UTC).isoformat(),
                    updated_at=datetime.now(UTC).isoformat(),
                )
            )
            updated_handle = persisted.to_handle()
            self._items[dataset_id] = StoredDataset(
                dataset_id=current.dataset_id,
                dataset_name=current.dataset_name,
                rows=list(current.rows),
                handle=updated_handle,
            )
            return updated_handle, matched_columns, unmatched_columns

    def clear(self) -> None:
        """Clear all in-memory uploaded dataset state."""

        with self._lock:
            self._items.clear()
        self._repository.clear()

    def clear_memory_cache(self) -> None:
        """Clear only the in-memory cache while preserving durable dataset state."""

        with self._lock:
            self._items.clear()


dataset_store = InMemoryDatasetStore()


def _column_merge_key(value: str) -> str:
    return str(value or "").strip().lower()


def _infer_source_format(dataset_name: str) -> str:
    normalized = str(dataset_name or "").strip().lower()
    if normalized.endswith(".csv"):
        return "csv"
    if normalized.endswith(".json"):
        return "json"
    if normalized.endswith(".xml"):
        return "xml"
    if normalized.endswith(".xlsx"):
        return "xlsx"
    if normalized.endswith(".sql"):
        return "sql"
    return "unknown"