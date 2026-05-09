from __future__ import annotations

from datetime import UTC, datetime

from app.models.knowledge import KnowledgeOverlayEntry
from app.models.mapping import (
    AutoMappingResponse,
    CanonicalGapApproveResponse,
    CanonicalGapCandidate,
    CanonicalGapSuggestion,
)
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service
from app.utils.knowledge_text import normalize_alias_text
from app.utils.normalization import semantic_token_set


def extract_canonical_gap_candidates(
    mapping_response: AutoMappingResponse,
    *,
    min_confidence: float = 0.65,
) -> list[CanonicalGapCandidate]:
    candidates: list[CanonicalGapCandidate] = []
    for mapping in mapping_response.mappings:
        if not mapping.target or mapping.status == "rejected":
            continue
        if mapping.canonical_details.shared_concepts:
            continue
        strong_signal = (
            mapping.confidence >= min_confidence
            or mapping.signals.knowledge >= 0.7
            or mapping.signals.semantic >= 0.7
            or (mapping.llm_consulted and mapping.confidence >= 0.5)
        )
        if not strong_signal:
            continue
        if mapping.canonical_details.source_concepts and mapping.canonical_details.target_concepts:
            continue
        reason = "Selected mapping has no shared canonical concept."
        if not mapping.canonical_details.source_concepts and not mapping.canonical_details.target_concepts:
            reason = "Neither side resolved to a canonical concept."
        elif not mapping.canonical_details.source_concepts:
            reason = "Source field did not resolve to a canonical concept."
        elif not mapping.canonical_details.target_concepts:
            reason = "Target field did not resolve to a canonical concept."
        candidates.append(
            CanonicalGapCandidate(
                source=mapping.source,
                target=mapping.target,
                confidence=mapping.confidence,
                confidence_label=mapping.confidence_label,
                status=mapping.status,
                method=mapping.method,
                signals=mapping.signals,
                explanation=mapping.explanation,
                canonical_details=mapping.canonical_details,
                reason=reason,
            )
        )
    return candidates


def nearest_canonical_concepts(candidate: CanonicalGapCandidate, *, limit: int = 8) -> list[dict]:
    query_tokens = semantic_token_set(candidate.source) | semantic_token_set(candidate.target)
    scored: list[tuple[float, dict]] = []
    for entry in metadata_knowledge_service.list_canonical_glossary_entries():
        alias_tokens = set()
        for value in [entry.concept_id, entry.display_name, entry.description, *entry.aliases]:
            alias_tokens.update(semantic_token_set(value))
        if not alias_tokens:
            continue
        overlap = len(query_tokens & alias_tokens) / max(len(query_tokens | alias_tokens), 1)
        if overlap <= 0:
            continue
        scored.append(
            (
                overlap,
                {
                    "concept_id": entry.concept_id,
                    "display_name": entry.display_name,
                    "description": entry.description,
                    "data_type": entry.data_type,
                    "aliases": entry.aliases[:12],
                    "similarity": round(overlap, 4),
                },
            )
        )
    return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]


def approve_canonical_gap_suggestion(
    candidate: CanonicalGapCandidate,
    suggestion: CanonicalGapSuggestion,
    *,
    approved_by: str | None = None,
    overlay_name: str | None = None,
) -> CanonicalGapApproveResponse:
    if suggestion.action == "no_action":
        raise ValueError("Cannot approve a no_action canonical gap suggestion.")
    if not suggestion.concept_id or not suggestion.display_name:
        raise ValueError("Approved canonical gap suggestion must include concept_id and display_name.")

    aliases = _suggestion_aliases(candidate, suggestion)
    if not aliases:
        raise ValueError("Approved canonical gap suggestion must include at least one alias.")

    previous_entries = []
    active = persistence_service.get_active_knowledge_overlay_version()
    if active and active.overlay_id is not None:
        previous_entries = persistence_service.get_knowledge_overlay_entries(active.overlay_id)

    version = persistence_service.save_knowledge_overlay_version(
        name=overlay_name or f"canonical-gap-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}",
        status="validated",
        created_by=(approved_by or "canonical-gap-assistant").strip() or "canonical-gap-assistant",
        source_filename="canonical-gap-assistant",
    )

    entries: list[KnowledgeOverlayEntry] = [entry.model_copy(update={"entry_id": None, "version_id": None}) for entry in previous_entries]
    for alias in aliases:
        entries.append(
            KnowledgeOverlayEntry(
                entry_type="concept_alias",
                canonical_term=suggestion.display_name,
                canonical_concept_id=suggestion.concept_id,
                alias=alias,
                domain=_concept_domain(suggestion.concept_id),
                source_system="canonical-gap-assistant",
                note=(
                    f"Approved canonical gap suggestion for {candidate.source} -> {candidate.target}; "
                    f"action={suggestion.action}; confidence={suggestion.confidence:.2f}."
                ),
                normalized_canonical_term=normalize_alias_text(suggestion.display_name),
                normalized_alias=normalize_alias_text(alias),
            )
        )

    saved_entries = persistence_service.save_knowledge_overlay_entries(version.overlay_id, entries)
    activated = persistence_service.activate_knowledge_overlay_version(version.overlay_id)
    metadata_knowledge_service.refresh()
    return CanonicalGapApproveResponse(
        overlay_id=activated.overlay_id or version.overlay_id,
        overlay_name=activated.name,
        saved_entry_count=len(saved_entries),
        activated=True,
    )


def _suggestion_aliases(candidate: CanonicalGapCandidate, suggestion: CanonicalGapSuggestion) -> list[str]:
    aliases = [candidate.source, candidate.target, *suggestion.aliases]
    seen: set[str] = set()
    result: list[str] = []
    for alias in aliases:
        normalized = normalize_alias_text(alias)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(alias.strip())
    return result


def _concept_domain(concept_id: str) -> str:
    return concept_id.split(".", 1)[0] if "." in concept_id else "canonical"
