from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.mapping import (
    AutoMappingRequest,
    AutoMappingResponse,
    CodegenRequest,
    GeneratedArtifact,
    PreviewRequest,
    PreviewResponse,
    TransformationGenerationRequest,
    TransformationGenerationResponse,
)
from app.services.llm_service import build_provider_from_settings, call_transformation_generator
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