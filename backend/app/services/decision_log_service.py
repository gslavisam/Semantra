from __future__ import annotations

from threading import Lock

from app.models.mapping import DecisionLogEntry
from app.services.persistence_service import persistence_service


class InMemoryDecisionLogStore:
    def __init__(self) -> None:
        self._entries: list[DecisionLogEntry] = []
        self._lock = Lock()

    def append(self, entry: DecisionLogEntry) -> None:
        with self._lock:
            self._entries.append(entry)
        persistence_service.append_decision_log(entry)

    def list_entries(self) -> list[DecisionLogEntry]:
        with self._lock:
            if self._entries:
                return list(self._entries)
        persisted = persistence_service.list_decision_logs()
        with self._lock:
            self._entries = list(persisted)
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
        persistence_service.clear_decision_logs()


decision_log_store = InMemoryDecisionLogStore()