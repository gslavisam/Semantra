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

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


dataset_store = InMemoryDatasetStore()