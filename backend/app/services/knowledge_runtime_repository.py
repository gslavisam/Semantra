"""Repository helpers for SQLite-backed knowledge and canonical runtime snapshots."""

from __future__ import annotations

from app.services.persistence_service import SQLitePersistenceService, persistence_service


class KnowledgeRuntimeRepository:
    """Provide a narrow runtime persistence surface for knowledge and canonical state."""

    def __init__(self, storage: SQLitePersistenceService | None = None) -> None:
        self._storage = storage or persistence_service

    def get_seed_meta(self) -> dict | None:
        """Return the persisted runtime seed metadata when available."""

        return self._storage.get_knowledge_seed_meta()

    def load_runtime_snapshot(self) -> tuple[list[dict], list[dict], list[dict]]:
        """Load persisted knowledge concepts, canonical concepts, and canonical field contexts."""

        return self._storage.load_knowledge_concepts()

    def replace_runtime_snapshot(
        self,
        concepts: list[object],
        canonical_concepts: list[object],
        canonical_field_contexts: list[tuple[str, object]],
        *,
        source_hash: str,
    ) -> None:
        """Replace the full persisted runtime snapshot after a file-based reseed."""

        self._storage.seed_knowledge_concepts(concepts, canonical_concepts, canonical_field_contexts)
        self._storage.save_knowledge_seed_meta(
            source_hash=source_hash,
            concept_count=len(concepts),
            canonical_count=len(canonical_concepts),
        )

    def sync_canonical_runtime(
        self,
        canonical_concepts: list[object],
        canonical_field_contexts: list[tuple[str, object]],
        *,
        source_hash: str,
        concept_count: int,
    ) -> None:
        """Refresh only the canonical runtime slice while preserving persisted knowledge concepts."""

        self._storage.sync_canonical_runtime(
            canonical_concepts,
            canonical_field_contexts,
            source_hash=source_hash,
            concept_count=concept_count,
        )


knowledge_runtime_repository = KnowledgeRuntimeRepository()
