from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile

from app.api.deps import require_admin
from app.models.knowledge import (
    CanonicalGlossaryImportResponse,
    KnowledgeAuditEntry,
    KnowledgeOverlayCreateResponse,
    KnowledgeOverlayVersion,
    KnowledgeOverlayVersionEntriesResponse,
    KnowledgeOverlayValidationResult,
    KnowledgeRuntimeStatus,
)
from app.services.knowledge_overlay_service import knowledge_overlay_validation_service
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


@router.get("/canonical-glossary/export", dependencies=[Depends(require_admin)])
async def export_canonical_glossary() -> Response:
    payload = metadata_knowledge_service.export_canonical_glossary_csv()
    return Response(
        content=payload,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="canonical_glossary.csv"'},
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
        f"Imported canonical glossary '{file.filename or 'canonical_glossary.csv'}' with {result.imported_row_count} rows.",
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


@router.post("/reload", response_model=KnowledgeRuntimeStatus, dependencies=[Depends(require_admin)])
async def reload_knowledge() -> KnowledgeRuntimeStatus:
    metadata_knowledge_service.refresh()
    return build_runtime_status()