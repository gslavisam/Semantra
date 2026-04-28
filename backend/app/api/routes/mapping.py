from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.mapping import (
    AutoMappingRequest,
    AutoMappingResponse,
    CodegenRequest,
    GeneratedArtifact,
    PreviewRequest,
    PreviewResponse,
)
from app.services.codegen_service import generate_pandas_code
from app.services.mapping_service import generate_mapping_candidates
from app.services.preview_service import build_preview
from app.services.upload_store import dataset_store


router = APIRouter(prefix="/mapping", tags=["mapping"])


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