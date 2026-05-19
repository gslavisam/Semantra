"""In-memory decision logging helpers for runtime inspection and audit readouts."""

from __future__ import annotations

from threading import Lock

from app.models.mapping import DecisionLogEntry
from app.services.persistence_service import persistence_service


class InMemoryDecisionLogStore:
    """In-memory facade over persisted mapping decision logs used for observability."""

    def __init__(self) -> None:
        self._entries: list[DecisionLogEntry] = []
        self._lock = Lock()

    def append(self, entry: DecisionLogEntry) -> None:
        """Persist one decision-log entry and mirror it into the local cache."""

        persistence_service.append_decision_log(entry)
        with self._lock:
            self._entries.append(entry)

    def list_entries(self) -> list[DecisionLogEntry]:
        """Return persisted decision logs and refresh the in-memory cache."""

        persisted = persistence_service.list_decision_logs()
        with self._lock:
            self._entries = list(persisted)
            return list(self._entries)

    def clear(self) -> None:
        """Clear all persisted and cached decision-log entries."""

        persistence_service.clear_decision_logs()
        with self._lock:
            self._entries.clear()


decision_log_store = InMemoryDecisionLogStore()