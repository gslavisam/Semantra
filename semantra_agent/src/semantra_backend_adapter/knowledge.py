"""Backend adapter for the `KnowledgeBase` protocol.

Wraps `backend.app.services.metadata_knowledge_service` to expose canonical
concepts, search, and active overlay entries.
"""

from __future__ import annotations

from typing import List, Optional

from semantra_core.models.knowledge import (
    CanonicalGlossaryEntry,
    KnowledgeOverlayEntry,
)
from semantra_core.services.implementations import InMemoryKnowledgeBase

from .context import BackendContext


class BackendKnowledgeBase:
    """Concrete `KnowledgeBase` backed by the Semantra FastAPI backend.

    Falls back to an in-memory implementation if the backend is not
    importable.
    """

    def __init__(self, context: BackendContext | None = None) -> None:
        self.context = context
        self._fallback = InMemoryKnowledgeBase()
        self._backend_available = False
        try:
            from backend.app.services import metadata_knowledge_service  # type: ignore

            self._service = metadata_knowledge_service
            self._backend_available = True
        except Exception:  # noqa: BLE001
            self._backend_available = False

    def get_canonical_concept(self, concept_id: str) -> Optional[CanonicalGlossaryEntry]:
        if not self._backend_available:
            return self._fallback.get_canonical_concept(concept_id)
        try:
            entry = self._service.get_canonical_concept(concept_id)
            if entry is None:
                return None
            return self._to_sdk_concept(entry)
        except Exception:  # noqa: BLE001
            return self._fallback.get_canonical_concept(concept_id)

    def search_concepts(self, query: str, limit: int = 10) -> List[CanonicalGlossaryEntry]:
        if not self._backend_available:
            return self._fallback.search_concepts(query, limit)
        try:
            results = self._service.search_concepts(query, limit=limit)
            return [self._to_sdk_concept(r) for r in results]
        except Exception:  # noqa: BLE001
            return self._fallback.search_concepts(query, limit)

    def get_active_overlay_entries(self) -> List[KnowledgeOverlayEntry]:
        if not self._backend_available:
            return self._fallback.get_active_overlay_entries()
        try:
            entries = self._service.get_active_overlay_entries()
            return [self._to_sdk_overlay_entry(e) for e in (entries or [])]
        except Exception:  # noqa: BLE001
            return self._fallback.get_active_overlay_entries()

    @staticmethod
    def _to_sdk_concept(entry) -> CanonicalGlossaryEntry:
        """Convert a backend concept object to the SDK model."""
        if isinstance(entry, CanonicalGlossaryEntry):
            return entry
        return CanonicalGlossaryEntry(
            concept_id=getattr(entry, "concept_id", ""),
            entity=getattr(entry, "entity", ""),
            attribute=getattr(entry, "attribute", ""),
            display_name=getattr(entry, "display_name", ""),
            description=getattr(entry, "description", ""),
            data_type=getattr(entry, "data_type", ""),
            aliases=list(getattr(entry, "aliases", [])),
        )

    @staticmethod
    def _to_sdk_overlay_entry(entry) -> KnowledgeOverlayEntry:
        if isinstance(entry, KnowledgeOverlayEntry):
            return entry
        return KnowledgeOverlayEntry(
            entry_id=getattr(entry, "entry_id", None),
            version_id=getattr(entry, "version_id", None),
            entry_type=getattr(entry, "entry_type", "synonym"),
            canonical_term=getattr(entry, "canonical_term", ""),
            canonical_concept_id=getattr(entry, "canonical_concept_id", None),
            alias=getattr(entry, "alias", ""),
            domain=getattr(entry, "domain", None),
            source_system=getattr(entry, "source_system", None),
            note=getattr(entry, "note", None),
            normalized_canonical_term=getattr(entry, "normalized_canonical_term", ""),
            normalized_alias=getattr(entry, "normalized_alias", ""),
        )
