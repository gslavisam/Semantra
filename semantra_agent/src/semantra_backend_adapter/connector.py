"""Backend adapter for the `Connector` protocol.

Wraps `backend.app.services.upload_store` to expose schema and preview
fetching from the Semantra upload runtime.
"""

from __future__ import annotations

from semantra_core.models.schema import DatasetHandle, SchemaProfile
from semantra_core.services.implementations import StaticConnector

from .context import BackendContext


class BackendConnector:
    """Concrete `Connector` backed by the Semantra FastAPI backend.

    Falls back to a `StaticConnector` with an empty schema if the backend
    is not importable or the requested dataset does not exist.
    """

    def __init__(
        self,
        dataset_id: str,
        context: BackendContext | None = None,
    ) -> None:
        self.dataset_id = dataset_id
        self.context = context
        self._backend_available = False
        try:
            from backend.app.services import upload_store  # type: ignore

            self._store = upload_store
            self._backend_available = True
        except Exception:  # noqa: BLE001
            self._backend_available = False

        self._fallback = StaticConnector(
            schema=SchemaProfile(
                dataset_id=dataset_id,
                dataset_name=dataset_id,
                row_count=0,
                columns=[],
            )
        )

    def fetch_schema(self) -> SchemaProfile:
        if not self._backend_available:
            return self._fallback.fetch_schema()
        try:
            record = self._store.get_dataset_record(self.dataset_id)
            if record is None:
                return self._fallback.fetch_schema()
            return record.schema_profile
        except Exception:  # noqa: BLE001
            return self._fallback.fetch_schema()

    def fetch_preview(self, limit: int = 100) -> DatasetHandle:
        if not self._backend_available:
            return self._fallback.fetch_preview(limit)
        try:
            record = self._store.get_dataset_record(self.dataset_id)
            if record is None:
                return self._fallback.fetch_preview(limit)
            preview_rows = list(record.preview_rows)[:limit]
            return DatasetHandle(
                dataset_id=record.dataset_id,
                dataset_name=record.dataset_name,
                schema_profile=record.schema_profile,
                preview_rows=preview_rows,
            )
        except Exception:  # noqa: BLE001
            return self._fallback.fetch_preview(limit)
