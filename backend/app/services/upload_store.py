from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any
from uuid import uuid4

from app.models.schema import DatasetHandle, SchemaProfile
from app.core.config import settings
from app.services.profiling_service import build_schema_profile


@dataclass
class StoredDataset:
    dataset_id: str
    dataset_name: str
    rows: list[dict[str, Any]]
    handle: DatasetHandle


class InMemoryDatasetStore:
    def __init__(self) -> None:
        self._items: dict[str, StoredDataset] = {}
        self._lock = Lock()

    def save_rows(self, rows: list[dict[str, Any]], dataset_name: str) -> DatasetHandle:
        dataset_id = str(uuid4())
        profile = build_schema_profile(rows, dataset_id=dataset_id, dataset_name=dataset_name)
        return self.save_schema_profile(profile, dataset_name=dataset_name, rows=rows)

    def save_schema_profile(
        self,
        profile: SchemaProfile,
        dataset_name: str,
        rows: list[dict[str, Any]] | None = None,
    ) -> DatasetHandle:
        dataset_id = profile.dataset_id
        stored_rows = list(rows or [])
        handle = DatasetHandle(
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            schema_profile=profile,
            preview_rows=stored_rows[: settings.max_upload_preview_rows],
        )
        with self._lock:
            self._items[dataset_id] = StoredDataset(
                dataset_id=dataset_id,
                dataset_name=dataset_name,
                rows=stored_rows,
                handle=handle,
            )
        return handle

    def get_dataset(self, dataset_id: str) -> StoredDataset:
        try:
            return self._items[dataset_id]
        except KeyError as error:
            raise KeyError(f"Unknown dataset_id: {dataset_id}") from error

    def merge_companion_metadata(
        self,
        dataset_id: str,
        companion_profile: SchemaProfile,
    ) -> tuple[DatasetHandle, int, list[str]]:
        with self._lock:
            try:
                stored = self._items[dataset_id]
            except KeyError as error:
                raise KeyError(f"Unknown dataset_id: {dataset_id}") from error

            existing_columns = list(stored.handle.schema_profile.columns)
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
                dataset_id=stored.handle.dataset_id,
                dataset_name=stored.handle.dataset_name,
                schema_profile=updated_profile,
                preview_rows=list(stored.handle.preview_rows),
            )
            stored.handle = updated_handle
            self._items[dataset_id] = StoredDataset(
                dataset_id=stored.dataset_id,
                dataset_name=stored.dataset_name,
                rows=list(stored.rows),
                handle=updated_handle,
            )
            return updated_handle, matched_columns, unmatched_columns

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


dataset_store = InMemoryDatasetStore()


def _column_merge_key(value: str) -> str:
    return str(value or "").strip().lower()