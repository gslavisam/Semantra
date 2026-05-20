"""Repository helpers for knowledge stewardship queue read and write models."""

from __future__ import annotations

from app.models.knowledge import (
    KnowledgeStewardshipItemCreateRequest,
    KnowledgeStewardshipItemDetail,
    KnowledgeStewardshipItemRecord,
)
from app.services.persistence_service import SQLitePersistenceService, persistence_service


class StewardshipRepository:
    """Provide a narrow persistence surface for stewardship queue operations."""

    def __init__(self, storage: SQLitePersistenceService | None = None) -> None:
        self._storage = storage or persistence_service

    def list_items(
        self,
        *,
        item_type: str | None = None,
        status: str | None = None,
        owner: str | None = None,
        assignee: str | None = None,
    ) -> list[KnowledgeStewardshipItemRecord]:
        """List stewardship queue items using the normalized SQLite read model."""

        return self._storage.list_knowledge_stewardship_items(
            item_type=item_type,
            status=status,
            owner=owner,
            assignee=assignee,
        )

    def get_item(self, item_id: int) -> KnowledgeStewardshipItemDetail:
        """Return one persisted stewardship item by id."""

        return self._storage.get_knowledge_stewardship_item(item_id)

    def get_item_by_key(self, item_type: str, item_key: str) -> KnowledgeStewardshipItemDetail | None:
        """Return one persisted stewardship item by stable item-type and item-key."""

        return self._storage.get_knowledge_stewardship_item_by_key(item_type, item_key)

    def upsert_item(self, request: KnowledgeStewardshipItemCreateRequest) -> KnowledgeStewardshipItemDetail:
        """Create or update one stewardship item in the normalized SQLite write model."""

        return self._storage.upsert_knowledge_stewardship_item(request)

    def update_item_status(
        self,
        item_id: int,
        status: str,
        *,
        changed_by: str | None = None,
        owner: str | None = None,
        assignee: str | None = None,
        review_note: str | None = None,
    ) -> KnowledgeStewardshipItemDetail:
        """Update stewardship status and assignment fields for one persisted item."""

        return self._storage.update_knowledge_stewardship_item_status(
            item_id,
            status,
            changed_by=changed_by,
            owner=owner,
            assignee=assignee,
            review_note=review_note,
        )


stewardship_repository = StewardshipRepository()
