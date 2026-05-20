"""Repository helpers for mapping-set governance and audit persistence."""

from __future__ import annotations

from app.models.mapping import (
    MappingSetAuditEntry,
    MappingSetDiffResponse,
    MappingSetDetail,
    MappingSetRecord,
)
from app.services.persistence_service import SQLitePersistenceService, persistence_service


class MappingGovernanceRepository:
    """Provide a narrow persistence surface for mapping-set governance flows."""

    def __init__(self, storage: SQLitePersistenceService | None = None) -> None:
        self._storage = storage or persistence_service

    def save_mapping_set(self, name: str, mapping_decisions: list[dict] | list[object], **kwargs) -> MappingSetRecord:
        """Persist one governed mapping set and refresh its catalog projection."""

        return self._storage.save_mapping_set(name, mapping_decisions, **kwargs)

    def list_mapping_sets(self) -> list[MappingSetRecord]:
        """List governed mapping-set versions."""

        return self._storage.list_mapping_sets()

    def get_mapping_set(self, mapping_set_id: int) -> MappingSetDetail:
        """Return one governed mapping-set detail record."""

        return self._storage.get_mapping_set(mapping_set_id)

    def update_mapping_set_status(
        self,
        mapping_set_id: int,
        status: str,
        *,
        owner: str | None = None,
        assignee: str | None = None,
        review_note: str | None = None,
    ) -> MappingSetRecord:
        """Update the governance status and assignment metadata for one mapping set."""

        return self._storage.update_mapping_set_status(
            mapping_set_id,
            status,
            owner=owner,
            assignee=assignee,
            review_note=review_note,
        )

    def append_audit_log(self, entry: MappingSetAuditEntry | dict[str, object]) -> MappingSetAuditEntry:
        """Append one persisted mapping-set audit entry."""

        return self._storage.append_mapping_set_audit_log(entry)

    def list_audit_logs(self, mapping_set_id: int | None = None) -> list[MappingSetAuditEntry]:
        """List persisted mapping-set audit entries, optionally scoped to one set."""

        return self._storage.list_mapping_set_audit_logs(mapping_set_id)

    def diff_mapping_sets(self, mapping_set_id: int, against_mapping_set_id: int) -> MappingSetDiffResponse:
        """Return the persisted diff between two mapping-set versions."""

        return self._storage.diff_mapping_sets(mapping_set_id, against_mapping_set_id)


mapping_governance_repository = MappingGovernanceRepository()
