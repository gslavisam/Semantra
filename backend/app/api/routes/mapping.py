from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_admin
from app.models.mapping import (
    AutoMappingRequest,
    AutoMappingResponse,
    CodegenRequest,
    GeneratedArtifact,
    MappingSetAuditEntry,
    MappingSetCreateRequest,
    MappingSetDetail,
    MappingSetRecord,
    MappingSetStatusUpdateRequest,
    PreviewRequest,
    PreviewResponse,
    TransformationGenerationRequest,
    TransformationGenerationResponse,
    TransformationTestSetCreateRequest,
    TransformationTestSetDetail,
    TransformationTestSetRecord,
    TransformationTestSetRunResponse,
    TransformationTemplate,
)
from app.services.llm_service import build_provider_from_settings, call_transformation_generator
from app.services.codegen_service import generate_pandas_code
from app.services.mapping_service import generate_mapping_candidates
from app.services.persistence_service import persistence_service
from app.services.preview_service import build_preview
from app.services.transformation_test_service import run_transformation_test_set
from app.services.transformation_template_service import list_transformation_templates
from app.services.upload_store import dataset_store


router = APIRouter(prefix="/mapping", tags=["mapping"])


def append_mapping_set_audit(
    action: str,
    mapping_set: MappingSetRecord,
    *,
    changed_by: str | None = None,
    note: str | None = None,
) -> MappingSetAuditEntry:
    return persistence_service.append_mapping_set_audit_log(
        MappingSetAuditEntry(
            mapping_set_id=mapping_set.mapping_set_id,
            mapping_set_name=mapping_set.name,
            version=mapping_set.version,
            action=action,
            status=mapping_set.status,
            changed_by=changed_by,
            note=note,
            created_at=datetime.now(UTC).isoformat(),
        )
    )


@router.post("/auto", response_model=AutoMappingResponse)
async def auto_map(request: AutoMappingRequest) -> AutoMappingResponse:
    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
        target = dataset_store.get_dataset(request.target_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return generate_mapping_candidates(source.handle.schema_profile, target.handle.schema_profile)


@router.post("/preview", response_model=PreviewResponse)
async def preview_mapping(request: PreviewRequest) -> PreviewResponse:
    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return build_preview(source.rows, request.mapping_decisions)


@router.post("/codegen", response_model=GeneratedArtifact)
async def codegen_mapping(request: CodegenRequest) -> GeneratedArtifact:
    return generate_pandas_code(request.mapping_decisions)


@router.post("/sets", response_model=MappingSetRecord, dependencies=[Depends(require_admin)])
async def create_mapping_set(request: MappingSetCreateRequest) -> MappingSetRecord:
    saved = persistence_service.save_mapping_set(
        request.name,
        request.mapping_decisions,
        source_dataset_id=request.source_dataset_id,
        target_dataset_id=request.target_dataset_id,
        created_by=request.created_by,
        note=request.note,
    )
    append_mapping_set_audit("create", saved, changed_by=request.created_by, note=request.note)
    return saved


@router.get("/sets", response_model=list[MappingSetRecord], dependencies=[Depends(require_admin)])
async def list_mapping_sets() -> list[MappingSetRecord]:
    return persistence_service.list_mapping_sets()


@router.get("/sets/{mapping_set_id}", response_model=MappingSetDetail, dependencies=[Depends(require_admin)])
async def get_mapping_set(mapping_set_id: int) -> MappingSetDetail:
    try:
        return persistence_service.get_mapping_set(mapping_set_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sets/{mapping_set_id}/status", response_model=MappingSetRecord, dependencies=[Depends(require_admin)])
async def update_mapping_set_status(
    mapping_set_id: int,
    request: MappingSetStatusUpdateRequest,
) -> MappingSetRecord:
    try:
        updated = persistence_service.update_mapping_set_status(mapping_set_id, request.status)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    append_mapping_set_audit("status_change", updated, changed_by=request.changed_by, note=request.note)
    return updated


@router.get("/sets/{mapping_set_id}/audit", response_model=list[MappingSetAuditEntry], dependencies=[Depends(require_admin)])
async def get_mapping_set_audit(mapping_set_id: int) -> list[MappingSetAuditEntry]:
    return persistence_service.list_mapping_set_audit_logs(mapping_set_id)


@router.get("/transformation/templates", response_model=list[TransformationTemplate])
async def get_transformation_templates() -> list[TransformationTemplate]:
    return list_transformation_templates()


@router.post(
    "/transformation/test-sets",
    response_model=TransformationTestSetRecord,
    dependencies=[Depends(require_admin)],
)
async def create_transformation_test_set(
    request: TransformationTestSetCreateRequest,
) -> TransformationTestSetRecord:
    return persistence_service.save_transformation_test_set(
        request.name,
        request.mapping_decisions,
        request.cases,
    )


@router.get(
    "/transformation/test-sets",
    response_model=list[TransformationTestSetRecord],
    dependencies=[Depends(require_admin)],
)
async def list_transformation_test_sets() -> list[TransformationTestSetRecord]:
    return persistence_service.list_transformation_test_sets()


@router.get(
    "/transformation/test-sets/{test_set_id}",
    response_model=TransformationTestSetDetail,
    dependencies=[Depends(require_admin)],
)
async def get_transformation_test_set(test_set_id: int) -> TransformationTestSetDetail:
    try:
        return persistence_service.get_transformation_test_set(test_set_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post(
    "/transformation/test-sets/{test_set_id}/run",
    response_model=TransformationTestSetRunResponse,
    dependencies=[Depends(require_admin)],
)
async def execute_transformation_test_set(test_set_id: int) -> TransformationTestSetRunResponse:
    try:
        test_set = persistence_service.get_transformation_test_set(test_set_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return run_transformation_test_set(test_set)


@router.post("/transformation/generate", response_model=TransformationGenerationResponse)
async def generate_transformation(request: TransformationGenerationRequest) -> TransformationGenerationResponse:
    provider = build_provider_from_settings()
    if provider is None:
        raise HTTPException(status_code=503, detail="LLM provider is not configured.")

    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
        target = dataset_store.get_dataset(request.target_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    source_column = next((column for column in source.handle.schema_profile.columns if column.name == request.source_column), None)
    if source_column is None:
        raise HTTPException(status_code=404, detail=f"Unknown source column: {request.source_column}")

    target_column = next((column for column in target.handle.schema_profile.columns if column.name == request.target_column), None)
    if target_column is None:
        raise HTTPException(status_code=404, detail=f"Unknown target column: {request.target_column}")

    result = call_transformation_generator(
        source_field={
            "name": source_column.name,
            "sample_values": source_column.sample_values,
            "pattern": source_column.detected_patterns,
            "dtype": source_column.dtype,
            "unique_ratio": source_column.unique_ratio,
            "null_ratio": source_column.null_ratio,
        },
        target_field={
            "name": target_column.name,
            "sample_values": target_column.sample_values,
            "pattern": target_column.detected_patterns,
            "dtype": target_column.dtype,
            "unique_ratio": target_column.unique_ratio,
            "null_ratio": target_column.null_ratio,
        },
        user_instruction=request.instruction,
        provider=provider,
    )
    if result is None:
        raise HTTPException(status_code=502, detail="LLM did not return a valid transformation suggestion.")

    return result