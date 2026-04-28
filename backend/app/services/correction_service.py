from __future__ import annotations

from threading import Lock

from app.models.mapping import UserCorrectionEntry
from app.services.persistence_service import persistence_service


class UserCorrectionStore:
    def __init__(self) -> None:
        self._entries: list[UserCorrectionEntry] = []
        self._lock = Lock()

    def append(self, entry: UserCorrectionEntry | dict) -> None:
        if isinstance(entry, dict):
            entry = UserCorrectionEntry.model_validate(entry)
        saved_entry = persistence_service.save_user_correction(entry)
        with self._lock:
            self._entries.append(saved_entry)

    def list_entries(self) -> list[UserCorrectionEntry]:
        with self._lock:
            if self._entries:
                return list(self._entries)
        persisted = persistence_service.list_user_corrections()
        with self._lock:
            self._entries = list(persisted)
            return list(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
        persistence_service.clear_user_corrections()

    def get_feedback_adjustment(self, source: str, target: str) -> float:
        matches = [
            entry
            for entry in self.list_entries()
            if entry.source == source and entry.corrected_target == target
        ]
        mismatches = [
            entry
            for entry in self.list_entries()
            if entry.source == source and entry.suggested_target == target and entry.corrected_target != target
        ]
        boost = min(0.2, 0.05 * len(matches))
        penalty = min(0.2, 0.05 * len(mismatches))
        return round(boost - penalty, 4)


correction_store = UserCorrectionStore()