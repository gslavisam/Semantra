from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.api.deps import require_admin
from app.models.knowledge import (
    CanonicalConceptDetailResponse,
    CanonicalConceptFieldContext,
    CanonicalConceptOverlayEntry,
    CanonicalConceptSummary,
    CanonicalConceptUsageRecord,
    CanonicalGlossaryImportResponse,
    KnowledgeAuditEntry,
    KnowledgeOverlayEntry,
    KnowledgeOverlayCreateResponse,
    KnowledgeOverlayVersion,
    KnowledgeOverlayVersionEntriesResponse,
    KnowledgeOverlayValidationResult,
    KnowledgeRuntimeStatus,
)
from app.services.knowledge_overlay_service import knowledge_overlay_validation_service
from app.models.mapping import (
    CanonicalGapApproveRequest,
    CanonicalGapApproveResponse,
    CanonicalGapCandidatesRequest,
    CanonicalGapCandidatesResponse,
    CanonicalGapRejectRequest,
    CanonicalGapSuggestion,
    CanonicalGapSuggestionRequest,
)
from app.services.canonical_gap_service import (
    approve_canonical_gap_suggestion,
    extract_canonical_gap_candidates,
    nearest_canonical_concepts,
)
from app.services.llm_service import build_provider_from_settings, call_canonical_gap_assistant
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def append_audit_entry(action: str, message: str, version: KnowledgeOverlayVersion | None = None) -> KnowledgeAuditEntry:
    return persistence_service.append_knowledge_audit_log(
        KnowledgeAuditEntry(
            overlay_id=version.overlay_id if version else None,
            overlay_name=version.name if version else None,
            action=action,
            message=message,
            created_at=datetime.now(UTC).isoformat(),
        )
    )


def build_runtime_status() -> KnowledgeRuntimeStatus:
    active_version = persistence_service.get_active_knowledge_overlay_version()
    active_entries = (
        persistence_service.get_knowledge_overlay_entries(active_version.overlay_id)
        if active_version and active_version.overlay_id is not None
        else []
    )
    entry_type_counts: dict[str, int] = {}
    for entry in active_entries:
        entry_type_counts[entry.entry_type] = entry_type_counts.get(entry.entry_type, 0) + 1

    return KnowledgeRuntimeStatus(
        mode="overlay_active" if active_version else "base_only",
        active_overlay_id=active_version.overlay_id if active_version else None,
        active_overlay_name=active_version.name if active_version else None,
        active_entry_count=len(active_entries),
        entry_type_counts=entry_type_counts,
        concept_count=metadata_knowledge_service.concept_count,
        canonical_concept_count=metadata_knowledge_service.canonical_concept_count,
    )


def _active_canonical_overlay_entries() -> tuple[KnowledgeOverlayVersion | None, dict[str, list[KnowledgeOverlayEntry]]]:
    active_version = persistence_service.get_active_knowledge_overlay_version()
    if active_version is None or active_version.overlay_id is None:
        return None, {}

    grouped: dict[str, list[KnowledgeOverlayEntry]] = {}
    for entry in persistence_service.get_knowledge_overlay_entries(active_version.overlay_id):
        if entry.entry_type != "concept_alias" or not entry.canonical_concept_id:
            continue
        grouped.setdefault(entry.canonical_concept_id, []).append(entry)
    return active_version, grouped


def _canonical_concept_registry() -> tuple[dict[str, CanonicalConceptSummary], dict[str, list[CanonicalConceptFieldContext]], KnowledgeOverlayVersion | None, dict[str, list[KnowledgeOverlayEntry]]]:
    _, canonical_dicts, canonical_context_dicts = persistence_service.load_knowledge_concepts()
    usage_counts = persistence_service.list_catalog_concept_usage_counts()
    active_overlay_version, overlay_entries_by_concept = _active_canonical_overlay_entries()

    contexts_by_concept: dict[str, list[CanonicalConceptFieldContext]] = {}
    for context in canonical_context_dicts:
        contexts_by_concept.setdefault(context["concept_id"], []).append(
            CanonicalConceptFieldContext(
                system=context["system"],
                object_name=context["object_name"],
                field_name=context["field_name"],
                category=context["category"],
                object_description=context["object_description"],
                field_description=context["field_description"],
                note=context["note"],
            )
        )

    registry: dict[str, CanonicalConceptSummary] = {}
    for concept in canonical_dicts:
        concept_id = str(concept["concept_id"])
        base_aliases = sorted({str(alias) for alias in concept.get("aliases", []) if str(alias).strip()})
        overlay_entries = overlay_entries_by_concept.get(concept_id, [])
        overlay_aliases = sorted({entry.alias for entry in overlay_entries if entry.alias.strip()})
        source = "base_plus_active_overlay" if overlay_aliases else "base"
        registry[concept_id] = CanonicalConceptSummary(
            concept_id=concept_id,
            entity=str(concept.get("entity") or ""),
            attribute=str(concept.get("attribute") or ""),
            display_name=str(concept.get("display_name") or concept_id),
            description=str(concept.get("description") or ""),
            data_type=str(concept.get("data_type") or ""),
            source=source,
            base_aliases=base_aliases,
            active_overlay_aliases=overlay_aliases,
            alias_count=len(set(base_aliases) | set(overlay_aliases)),
            field_context_count=len(contexts_by_concept.get(concept_id, [])),
            usage_count=usage_counts.get(concept_id, 0),
            active_overlay_entry_count=len(overlay_entries),
        )

    for concept_id, overlay_entries in overlay_entries_by_concept.items():
        if concept_id in registry:
            continue
        entity, _, attribute = concept_id.partition(".")
        overlay_aliases = sorted({entry.alias for entry in overlay_entries if entry.alias.strip()})
        display_name = next((entry.canonical_term for entry in overlay_entries if entry.canonical_term.strip()), concept_id)
        registry[concept_id] = CanonicalConceptSummary(
            concept_id=concept_id,
            entity=entity,
            attribute=attribute,
            display_name=display_name,
            source="overlay_only",
            active_overlay_aliases=overlay_aliases,
            alias_count=len(overlay_aliases),
            usage_count=usage_counts.get(concept_id, 0),
            active_overlay_entry_count=len(overlay_entries),
        )

    return registry, contexts_by_concept, active_overlay_version, overlay_entries_by_concept


@router.get("/canonical-concepts", response_model=list[CanonicalConceptSummary], dependencies=[Depends(require_admin)])
async def list_canonical_concepts() -> list[CanonicalConceptSummary]:
    registry, _, _, _ = _canonical_concept_registry()
    return [registry[concept_id] for concept_id in sorted(registry)]


@router.get("/canonical-concepts/{concept_id}", response_model=CanonicalConceptDetailResponse, dependencies=[Depends(require_admin)])
async def get_canonical_concept(concept_id: str) -> CanonicalConceptDetailResponse:
    registry, contexts_by_concept, active_overlay_version, overlay_entries_by_concept = _canonical_concept_registry()
    concept = registry.get(concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail=f"Unknown canonical concept: {concept_id}")

    active_overlay_entries = [
        CanonicalConceptOverlayEntry(
            entry_id=entry.entry_id,
            overlay_id=active_overlay_version.overlay_id,
            overlay_name=active_overlay_version.name,
            canonical_term=entry.canonical_term,
            alias=entry.alias,
            source_system=entry.source_system,
            note=entry.note,
        )
        for entry in overlay_entries_by_concept.get(concept_id, [])
        if active_overlay_version and active_overlay_version.overlay_id is not None
    ]
    audit_entries = []
    if active_overlay_version and active_overlay_entries:
        audit_entries = [
            entry
            for entry in persistence_service.list_knowledge_audit_logs()
            if entry.overlay_id == active_overlay_version.overlay_id
        ]

    return CanonicalConceptDetailResponse(
        concept=concept,
        field_contexts=contexts_by_concept.get(concept_id, []),
        active_overlay_entries=active_overlay_entries,
        integrations=[
            CanonicalConceptUsageRecord.model_validate(record.model_dump(mode="json"))
            for record in persistence_service.list_catalog_concept_usage_records(concept_id)
        ],
        audit_entries=audit_entries,
    )


@router.get("/canonical-glossary/export", dependencies=[Depends(require_admin)])
async def export_canonical_glossary() -> Response:
    payload = metadata_knowledge_service.export_canonical_glossary_csv()
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{metadata_knowledge_service.canonical_glossary_path.name}"'},
    )


@router.post("/canonical-glossary/import", response_model=CanonicalGlossaryImportResponse, dependencies=[Depends(require_admin)])
async def import_canonical_glossary(file: UploadFile = File(...)) -> CanonicalGlossaryImportResponse:
    payload = await file.read()
    try:
        result = metadata_knowledge_service.import_canonical_glossary_csv(payload, filename=file.filename)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    append_audit_entry(
        "create",
        f"Imported canonical glossary '{file.filename or metadata_knowledge_service.canonical_glossary_path.name}' with {result.imported_row_count} rows.",
    )
    return result


@router.post("/overlays/validate", response_model=KnowledgeOverlayValidationResult, dependencies=[Depends(require_admin)])
async def validate_knowledge_overlay(file: UploadFile = File(...)) -> KnowledgeOverlayValidationResult:
    payload = await file.read()
    return knowledge_overlay_validation_service.validate_csv_payload(payload, filename=file.filename)


@router.post("/overlays", response_model=KnowledgeOverlayCreateResponse, dependencies=[Depends(require_admin)])
async def create_knowledge_overlay(
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    created_by: str | None = Form(default=None),
) -> KnowledgeOverlayCreateResponse:
    payload = await file.read()
    validation = knowledge_overlay_validation_service.validate_csv_payload(payload, filename=file.filename)
    if validation.invalid_rows > 0:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Knowledge overlay contains invalid rows and cannot be saved.",
                "validation": validation.model_dump(mode="json"),
            },
        )

    version = persistence_service.save_knowledge_overlay_version(
        name=name or (file.filename or "knowledge-overlay"),
        status="validated",
        created_by=(created_by or "").strip() or None,
        source_filename=file.filename,
    )
    entries = [
        knowledge_overlay_validation_service.build_entry(row)
        for row in validation.normalized_preview
        if row.status == "valid"
    ]
    saved_entries = persistence_service.save_knowledge_overlay_entries(version.overlay_id, entries)
    append_audit_entry(
        "create",
        f"Created knowledge overlay '{version.name}' with {len(saved_entries)} entries.",
        version,
    )
    return KnowledgeOverlayCreateResponse(version=version, saved_entry_count=len(saved_entries), validation=validation)


@router.get("/overlays", response_model=list[KnowledgeOverlayVersion], dependencies=[Depends(require_admin)])
async def list_knowledge_overlays() -> list[KnowledgeOverlayVersion]:
    return persistence_service.list_knowledge_overlay_versions()


@router.get("/audit", response_model=list[KnowledgeAuditEntry], dependencies=[Depends(require_admin)])
async def list_knowledge_audit_logs() -> list[KnowledgeAuditEntry]:
    return persistence_service.list_knowledge_audit_logs()


@router.get("/overlays/{overlay_id}", response_model=KnowledgeOverlayVersionEntriesResponse, dependencies=[Depends(require_admin)])
async def get_knowledge_overlay(overlay_id: int) -> KnowledgeOverlayVersionEntriesResponse:
    try:
        version = persistence_service.get_knowledge_overlay_version(overlay_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    entries = persistence_service.get_knowledge_overlay_entries(overlay_id)
    return KnowledgeOverlayVersionEntriesResponse(version=version, entries=entries)


@router.post("/overlays/{overlay_id}/activate", response_model=KnowledgeOverlayVersion, dependencies=[Depends(require_admin)])
async def activate_knowledge_overlay(overlay_id: int) -> KnowledgeOverlayVersion:
    try:
        version = persistence_service.activate_knowledge_overlay_version(overlay_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    metadata_knowledge_service.refresh()
    append_audit_entry("activate", f"Activated knowledge overlay '{version.name}'.", version)
    return version


@router.post("/overlays/{overlay_id}/deactivate", response_model=KnowledgeOverlayVersion, dependencies=[Depends(require_admin)])
async def deactivate_knowledge_overlay(overlay_id: int) -> KnowledgeOverlayVersion:
    try:
        version = persistence_service.deactivate_knowledge_overlay_version(overlay_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    metadata_knowledge_service.refresh()
    append_audit_entry("deactivate", f"Deactivated knowledge overlay '{version.name}'.", version)
    return version


@router.post("/overlays/{overlay_id}/archive", response_model=KnowledgeOverlayVersion, dependencies=[Depends(require_admin)])
async def archive_knowledge_overlay(overlay_id: int) -> KnowledgeOverlayVersion:
    try:
        version = persistence_service.archive_knowledge_overlay_version(overlay_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    metadata_knowledge_service.refresh()
    append_audit_entry("archive", f"Archived knowledge overlay '{version.name}'.", version)
    return version


@router.post("/overlays/rollback", response_model=KnowledgeRuntimeStatus, dependencies=[Depends(require_admin)])
async def rollback_knowledge_overlay() -> KnowledgeRuntimeStatus:
    try:
        rolled_back_to = persistence_service.rollback_knowledge_overlay_version()
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    metadata_knowledge_service.refresh()
    if rolled_back_to is not None:
        append_audit_entry("rollback", f"Rolled back to knowledge overlay '{rolled_back_to.name}'.", rolled_back_to)
    else:
        append_audit_entry("rollback", "Rolled back to base-only knowledge mode.")
    return build_runtime_status()


@router.post("/canonical-gaps/candidates", response_model=CanonicalGapCandidatesResponse, dependencies=[Depends(require_admin)])
async def canonical_gap_candidates(request: CanonicalGapCandidatesRequest) -> CanonicalGapCandidatesResponse:
    return CanonicalGapCandidatesResponse(
        candidates=extract_canonical_gap_candidates(
            request.mapping_response,
            min_confidence=request.min_confidence,
        )
    )


@router.post("/canonical-gaps/suggest", response_model=CanonicalGapSuggestion, dependencies=[Depends(require_admin)])
async def suggest_canonical_gap(request: CanonicalGapSuggestionRequest) -> CanonicalGapSuggestion:
    nearest = nearest_canonical_concepts(request.candidate)
    suggestion = call_canonical_gap_assistant(request.candidate, nearest, build_provider_from_settings())
    if suggestion is None:
        return CanonicalGapSuggestion(
            action="no_action",
            confidence=0.0,
            reasoning=["No usable LLM canonical gap suggestion was returned."],
            risk_notes=["Review the mapping and glossary manually."],
        )
    return suggestion


@router.post("/canonical-gaps/approve", response_model=CanonicalGapApproveResponse, dependencies=[Depends(require_admin)])
async def approve_canonical_gap(request: CanonicalGapApproveRequest) -> CanonicalGapApproveResponse:
    try:
        response = approve_canonical_gap_suggestion(
            request.candidate,
            request.suggestion,
            approved_by=request.approved_by,
            overlay_name=request.overlay_name,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    append_audit_entry(
        "create",
        f"Approved canonical gap suggestion for {request.candidate.source} -> {request.candidate.target} into overlay '{response.overlay_name}'.",
    )
    return response


@router.post("/canonical-gaps/reject", response_model=KnowledgeAuditEntry, dependencies=[Depends(require_admin)])
async def reject_canonical_gap(request: CanonicalGapRejectRequest) -> KnowledgeAuditEntry:
    suggestion_action = request.suggestion.action if request.suggestion is not None else "no_suggestion"
    concept_id = request.suggestion.concept_id if request.suggestion is not None else None
    note = (request.note or "").strip()
    actor = (request.rejected_by or "").strip() or "unknown"
    audit_action = "ignore" if request.disposition == "ignored" else "reject"
    verb = "Ignored" if request.disposition == "ignored" else "Rejected"
    message_parts = [
        f"{verb} canonical gap suggestion for {request.candidate.source} -> {request.candidate.target}.",
        f"Disposition={request.disposition}.",
        f"Suggestion action={suggestion_action}.",
        f"Reviewed by={actor}.",
    ]
    if concept_id:
        message_parts.append(f"Concept={concept_id}.")
    if note:
        message_parts.append(f"Note={note}.")
    return append_audit_entry(audit_action, " ".join(message_parts))


@router.post("/reload", response_model=KnowledgeRuntimeStatus, dependencies=[Depends(require_admin)])
async def reload_knowledge() -> KnowledgeRuntimeStatus:
    metadata_knowledge_service.refresh()
    return build_runtime_status()


@router.post("/reseed", response_model=KnowledgeRuntimeStatus, dependencies=[Depends(require_admin)])
async def reseed_knowledge() -> KnowledgeRuntimeStatus:
    """Force reload of all knowledge from source files and re-persist to SQLite.

    Use this after modifying any of the source CSV/XLSX/XML knowledge files.
    After the reseed completes, subsequent restarts will load from the DB only
    (unless source files change again).
    """
    stats = metadata_knowledge_service.reseed_from_files()
    append_audit_entry(
        "reseed",
        (
            f"Reseeded knowledge from source files: "
            f"{stats['concept_count']} concepts, "
            f"{stats['canonical_count']} canonical, "
            f"{stats['alias_count']} aliases."
        ),
    )
    return build_runtime_status()