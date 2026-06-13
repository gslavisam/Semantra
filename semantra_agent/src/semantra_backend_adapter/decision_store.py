"""Backend adapter for the `DecisionStore` protocol.

Wraps `backend.app.services.decision_log_service.decision_log_store`
(the backend's in-memory singleton) and adapts its `list_entries` / `append` /
`clear` methods to the SDK's `DecisionStore` protocol.
"""

from __future__ import annotations

from typing import List

from semantra_core.models.mapping import DecisionLogEntry
from semantra_core.services.implementations import InMemoryDecisionStore

from .context import BackendContext


class BackendDecisionStore:
    """Concrete `DecisionStore` backed by the Semantra FastAPI backend.

    Delegates to the backend's singleton ``decision_log_store`` which
    persists to both the local SQLite database and an in-memory cache.

    If the backend is not importable, falls back to the SDK's
    ``InMemoryDecisionStore``.
    """

    def __init__(self, context: BackendContext | None = None) -> None:
        self.context = context
        self._backend_store = None
        self._fallback = InMemoryDecisionStore()
        self._backend_available = False
        try:
            from backend.app.services import decision_log_service  # type: ignore

            self._backend_store = decision_log_service.decision_log_store
            self._backend_available = True
        except Exception:  # noqa: BLE001
            self._backend_available = False

    def append(self, entry: DecisionLogEntry) -> None:
        if self._backend_available and self._backend_store is not None:
            self._backend_store.append(entry)
        else:
            self._fallback.append(entry)

    def list(self) -> List[DecisionLogEntry]:
        if self._backend_available and self._backend_store is not None:
            # The backend's store uses `list_entries()`; the protocol expects `list()`.
            return self._backend_store.list_entries()
        return self._fallback.list()

    def clear(self) -> None:
        if self._backend_available and self._backend_store is not None:
            self._backend_store.clear()
        else:
            self._fallback.clear()
