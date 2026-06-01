"""Upload and enrichment endpoints for Semantra dataset ingestion flows."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.schema import (
    DatasetHandle,
    MetadataEnrichmentResponse,
    SpecDetectionResponse,
    SpecLayoutHint,
    SpecRecoveryResponse,
    SqlTableDiscoveryResponse,
    UploadResponse,
)
from app.services.llm_service import build_provider_from_settings
from app.services.schema_snapshot_service import build_schema_profile_from_sql_snapshot, list_tables_from_sql_snapshot
from app.services.spec_recovery_service import recover_spec_layout
from app.services.spec_upload_service import build_spec_layout_hint, parse_spec_payload, parse_spec_source_rows
from app.services.tabular_upload_service import SUPPORTED_ROW_FORMATS, parse_tabular_payload
from app.services.upload_store import dataset_store
from app.utils.tabular import decode_text_payload


router = APIRouter(tags=["upload"])


@router.post("/upload/sql/tables", response_model=SqlTableDiscoveryResponse)
async def discover_sql_tables(file: UploadFile = File(...)) -> SqlTableDiscoveryResponse:
    """Inspect an uploaded SQL snapshot and list the discovered table names."""

    filename = (file.filename or "").lower()
    if not filename.endswith(".sql"):
        raise HTTPException(status_code=400, detail="SQL table discovery only supports .sql files.")

    payload = await file.read()
    try:
        decoded = decode_text_payload(payload)
        return SqlTableDiscoveryResponse(tables=list_tables_from_sql_snapshot(decoded))
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Failed to inspect SQL schema snapshot: {error}") from error


@router.post("/upload/spec/detect", response_model=SpecDetectionResponse)
async def detect_spec_upload(file: UploadFile = File(...)) -> SpecDetectionResponse:
    """Detect likely schema-spec columns from an uploaded tabular metadata file."""

    filename = (file.filename or "").lower()
    if not filename.endswith(SUPPORTED_ROW_FORMATS):
        raise HTTPException(
            status_code=400,
            detail="Spec detection supports CSV, JSON, XML, and XLSX tabular uploads.",
        )

    payload = await file.read()
    try:
        rows, _header_row_index = parse_spec_source_rows(payload, file.filename or "spec.csv")
    except Exception:
        return SpecDetectionResponse(hint=None)
    return SpecDetectionResponse(hint=build_spec_layout_hint(rows))


@router.post("/upload/spec/recover", response_model=SpecRecoveryResponse)
async def recover_spec_upload(file: UploadFile = File(...)) -> SpecRecoveryResponse:
    """Analyze a parseable metadata file and return a bounded schema-spec recovery suggestion."""

    filename = (file.filename or "").lower()
    if not filename.endswith(SUPPORTED_ROW_FORMATS):
        raise HTTPException(
            status_code=400,
            detail="Spec recovery supports CSV, JSON, XML, and XLSX tabular uploads.",
        )

    payload = await file.read()
    upload_name = file.filename or "spec.csv"
    try:
        return recover_spec_layout(payload, upload_name, provider=build_provider_from_settings())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=f"Failed to parse tabular file: {error}") from error


@router.post("/upload/spec", response_model=DatasetHandle)
async def upload_schema_spec(
    file: UploadFile = File(...),
    header_row_index: int | None = Form(default=None),
    name_col: str | None = Form(default=None),
    description_col: str | None = Form(default=None),
    type_col: str | None = Form(default=None),
    sample_values_col: str | None = Form(default=None),
) -> DatasetHandle:
    """Upload a schema-spec file and persist its parsed schema profile as a dataset handle."""

    filename = (file.filename or "").lower()
    if not filename.endswith(SUPPORTED_ROW_FORMATS):
        raise HTTPException(
            status_code=400,
            detail="Spec upload supports CSV, JSON, XML, and XLSX tabular uploads.",
        )

    payload = await file.read()
    upload_name = file.filename or "spec.csv"
    try:
        profile = parse_spec_payload(
            payload,
            upload_name,
            header_row_index=header_row_index,
            name_col=name_col,
            description_col=description_col,
            type_col=type_col,
            sample_values_col=sample_values_col,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return dataset_store.save_schema_profile(
        profile,
        dataset_name=upload_name,
        rows=[],
        source_format="schema_spec",
        storage_mode="schema_only",
    )


@router.post("/upload/handle", response_model=DatasetHandle)
async def upload_dataset_handle(
    file: UploadFile = File(...),
    selected_table: str | None = Form(default=None),
) -> DatasetHandle:
    """Upload one dataset or SQL schema snapshot and return its stored dataset handle."""

    return await parse_and_store_upload(file, fallback_name="dataset.csv", selected_table=selected_table)


@router.post("/upload/handle/metadata", response_model=MetadataEnrichmentResponse)
async def enrich_dataset_metadata(
    dataset_id: str = Form(...),
    file: UploadFile = File(...),
    header_row_index: int | None = Form(default=None),
    name_col: str | None = Form(default=None),
    description_col: str | None = Form(default=None),
    type_col: str | None = Form(default=None),
    sample_values_col: str | None = Form(default=None),
) -> MetadataEnrichmentResponse:
    """Merge companion schema metadata into an already uploaded dataset profile."""

    filename = (file.filename or "").lower()
    if not filename.endswith(SUPPORTED_ROW_FORMATS):
        raise HTTPException(
            status_code=400,
            detail="Companion metadata upload supports CSV, JSON, XML, and XLSX tabular uploads.",
        )

    payload = await file.read()
    upload_name = file.filename or "companion_spec.csv"
    try:
        companion_profile = parse_spec_payload(
            payload,
            upload_name,
            header_row_index=header_row_index,
            name_col=name_col,
            description_col=description_col,
            type_col=type_col,
            sample_values_col=sample_values_col,
        )
        dataset_handle, matched_columns, unmatched_columns = dataset_store.merge_companion_metadata(
            dataset_id,
            companion_profile,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return MetadataEnrichmentResponse(
        dataset=dataset_handle,
        matched_columns=matched_columns,
        unmatched_columns=unmatched_columns,
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_datasets(
    source_file: UploadFile = File(...),
    target_file: UploadFile = File(...),
    source_table: str | None = Form(default=None),
    target_table: str | None = Form(default=None),
) -> UploadResponse:
    """Upload paired source and target datasets and return both stored handles."""

    source_handle = await parse_and_store_upload(source_file, fallback_name="source.csv", selected_table=source_table)
    target_handle = await parse_and_store_upload(target_file, fallback_name="target.csv", selected_table=target_table)
    return UploadResponse(source=source_handle, target=target_handle)


async def parse_and_store_upload(upload: UploadFile, fallback_name: str, selected_table: str | None = None):
    """Parse one uploaded file and persist it as either row data or a schema profile handle."""

    filename = (upload.filename or "").lower()
    payload = await upload.read()
    upload_name = upload.filename or fallback_name

    if filename.endswith(SUPPORTED_ROW_FORMATS):
        rows = read_tabular_payload(payload, upload_name)
        return dataset_store.save_rows(rows, upload_name, source_format=filename.rsplit(".", 1)[-1])
    if filename.endswith(".sql"):
        profile = read_sql_snapshot_payload(payload, dataset_name=upload_name, selected_table=selected_table)
        return dataset_store.save_schema_profile(
            profile,
            dataset_name=upload_name,
            rows=[],
            source_format="sql",
            storage_mode="schema_only",
            selected_table=selected_table,
        )

    raise HTTPException(
        status_code=400,
        detail="Supported upload formats are CSV, JSON, XML, XLSX row data and SQL schema snapshots.",
    )


def read_tabular_payload(payload: bytes, filename: str) -> list[dict[str, object]]:
    """Parse a tabular upload payload and convert parser failures into HTTP 400 errors."""

    try:
        return parse_tabular_payload(payload, filename)
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Failed to parse tabular file: {error}") from error


def read_sql_snapshot_payload(payload: bytes, dataset_name: str, selected_table: str | None = None):
    """Parse a SQL schema snapshot payload and convert parser failures into HTTP 400 errors."""

    try:
        decoded = decode_text_payload(payload)
        return build_schema_profile_from_sql_snapshot(
            decoded,
            dataset_id=str(uuid4()),
            dataset_name=dataset_name,
            selected_table=selected_table,
        )
    except Exception as error:
        raise HTTPException(status_code=400, detail=f"Failed to parse SQL schema snapshot: {error}") from error