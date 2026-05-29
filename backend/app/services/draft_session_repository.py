"""Repository helpers for draft workspace session persistence."""

from __future__ import annotations

from app.models.mapping import DraftSessionCreateRequest, DraftSessionDetail, DraftSessionRecord, DraftSessionUpdateRequest
from app.services.persistence_service import DraftSessionStaleWriteError, SQLitePersistenceService, persistence_service


class DraftSessionRepository:
    """Provide a narrow persistence surface for durable draft workspace sessions."""

    def __init__(self, storage: SQLitePersistenceService | None = None) -> None:
        self._storage = storage or persistence_service

    def save_draft_session(self, request: DraftSessionCreateRequest) -> DraftSessionRecord:
        """Persist one durable draft workspace snapshot."""

        return self._storage.save_draft_session(request)

    def update_draft_session(self, draft_session_id: int, request: DraftSessionUpdateRequest) -> DraftSessionDetail:
        """Update one durable draft workspace snapshot."""

        return self._storage.update_draft_session(draft_session_id, request)

    def list_draft_sessions(self) -> list[DraftSessionRecord]:
        """List saved draft workspace snapshots."""

        return self._storage.list_draft_sessions()

    def get_draft_session(self, draft_session_id: int) -> DraftSessionDetail:
        """Return one saved draft workspace snapshot with full restore payload."""

        return self._storage.get_draft_session(draft_session_id)


draft_session_repository = DraftSessionRepository()
