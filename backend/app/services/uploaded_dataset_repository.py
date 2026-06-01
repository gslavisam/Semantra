"""Repository helpers for durable uploaded dataset handles and preview payloads."""

from __future__ import annotations

from app.models.schema import PersistedDatasetRecord
from app.services.persistence_service import SQLitePersistenceService, persistence_service


class UploadedDatasetRepository:
    """Provide a narrow persistence surface for uploaded dataset handle storage."""

    def __init__(self, storage: SQLitePersistenceService | None = None) -> None:
        self._storage = storage or persistence_service

    def save_dataset(self, record: PersistedDatasetRecord) -> PersistedDatasetRecord:
        return self._storage.save_uploaded_dataset(record)

    def get_dataset(self, dataset_id: str) -> PersistedDatasetRecord:
        return self._storage.get_uploaded_dataset(dataset_id)

    def clear(self) -> None:
        self._storage.clear_uploaded_datasets()


uploaded_dataset_repository = UploadedDatasetRepository()