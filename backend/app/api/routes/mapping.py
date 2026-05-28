"""Mapping workflow endpoints for ranking, review, preview, and governance actions."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.api.deps import require_admin
from app.models.knowledge import SourceFieldHintRecord, SourceFieldHintUpsertRequest
from app.models.mapping import (
    ArtifactRefinementRequest,
    ArtifactRefinementResponse,
    AutoMappingRequest,
    AutoMappingResponse,
    MappingAnalysisAudioRequest,
    MappingAnalysisNarrationRequest,
    MappingAnalysisNarrationResponse,
    MappingAnalysisRequest,
    MappingAnalysisSummaryResponse,
    CanonicalMappingRequest,
    CodegenRequest,
    DraftSessionCreateRequest,
    DraftSessionDetail,
    DraftSessionRecord,
    GeneratedArtifact,
    MappingRefinementRequest,
    MappingDecision,
    MappingSetApplyRequest,
    MappingSetAuditEntry,
    MappingSetCreateRequest,
    MappingSetDiffResponse,
    MappingSetDetail,
    MappingSetRecord,
    MappingSetStatusUpdateRequest,
    MappingJobStartResponse,
    MappingJobStatusResponse,
    PreviewRequest,
    PreviewResponse,
    ReviewPlanRequest,
    ReviewPlanResponse,
    SourceMappingResult,
    TransformationGenerationRequest,
    TransformationGenerationResponse,
    TransformationTestSetCreateRequest,
    TransformationTestSetDetail,
    TransformationTestSetRecord,
    TransformationTestSetRunResponse,
    TransformationTemplate,
)
from app.services.llm_service import build_provider_from_settings, call_artifact_refinement, call_transformation_generator
from app.services.mapping_analysis_service import build_mapping_analysis_narration, build_mapping_analysis_summary
from app.services.mapping_audio_service import synthesize_orpheus_wav
from app.services.codegen_service import generate_dbt_code, generate_pandas_code, generate_pyspark_code
from app.services.draft_session_repository import draft_session_repository
from app.services.mapping_job_service import MappingJobCapacityError, mapping_job_store
from app.services.mapping_governance_repository import mapping_governance_repository
from app.services.review_plan_service import build_review_plan
from app.services.mapping_service import generate_mapping_candidates, refine_mapping_for_source
from app.services.persistence_service import persistence_service
from app.services.preview_service import build_preview
from app.services.source_field_hint_service import apply_inline_source_field_hint, apply_source_field_hints
from app.services.transformation_test_service import run_transformation_test_set
from app.services.transformation_template_service import list_transformation_templates
from app.services.upload_store import dataset_store
from app.services.virtual_target_service import build_virtual_target_schema


router = APIRouter(prefix="/mapping", tags=["mapping"])


def _blocked_output_decision_statuses(
    mapping_decisions: list[MappingDecision],
    *,
    allow_unaccepted: bool = False,
) -> list[str]:
    allowed_statuses = {"accepted", "needs_review"} if allow_unaccepted else {"accepted"}
    return sorted(
        {
            (str(decision.status or "").strip().lower() or "needs_review")
            for decision in mapping_decisions
            if (str(decision.status or "").strip().lower() or "needs_review") not in allowed_statuses
        }
    )


def _require_accepted_output_decisions(
    mapping_decisions: list[MappingDecision],
    *,
    action_label: str,
    allow_unaccepted: bool = False,
) -> None:
    blocked_statuses = _blocked_output_decision_statuses(mapping_decisions, allow_unaccepted=allow_unaccepted)
    if blocked_statuses:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{action_label} is blocked until all active mapping decisions are accepted. "
                f"Review statuses: {', '.join(blocked_statuses)}."
            ),
        )


def append_mapping_set_audit(
    action: str,
    mapping_set: MappingSetRecord,
    *,
    changed_by: str | None = None,
    note: str | None = None,
) -> MappingSetAuditEntry:
    """Append one audit entry for a mapping-set lifecycle action."""

    return mapping_governance_repository.append_audit_log(
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


def _prepare_source_schema_with_persistent_hints(
    source_schema,
    *,
    source_system: str | None,
    business_domain: str | None,
    integration_name: str | None,
) -> tuple[object, list[SourceFieldHintRecord]]:
    enriched_schema, applied_hints = apply_source_field_hints(
        source_schema,
        source_system=source_system,
        business_domain=business_domain,
        integration_name=integration_name,
    )
    return enriched_schema, applied_hints


def _attach_applied_source_field_hints(
    response: AutoMappingResponse,
    applied_hints: list[SourceFieldHintRecord],
) -> AutoMappingResponse:
    if not applied_hints:
        return response
    return response.model_copy(
        update={
            "applied_source_field_hints": [hint.model_dump(mode="json") for hint in applied_hints],
        }
    )


def _normalized_field_name(value: str | None) -> str:
    return str(value or "").strip().lower()


def _find_schema_column(schema_profile, column_name: str):
    normalized_name = _normalized_field_name(column_name)
    for column in schema_profile.columns:
        if _normalized_field_name(column.name) == normalized_name:
            return column
    return None


def _resolve_refinement_target_schema(request: MappingRefinementRequest):
    if request.target_dataset_id:
        try:
            target = dataset_store.get_dataset(request.target_dataset_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return target.handle.schema_profile

    if request.target_system:
        target_schema = build_virtual_target_schema(request.target_system)
        if not target_schema.columns:
            raise HTTPException(status_code=400, detail="Canonical glossary is empty; cannot build virtual canonical target.")
        return target_schema

    raise HTTPException(status_code=400, detail="Provide either target_dataset_id or target_system for mapping refinement.")


@router.post("/auto", response_model=AutoMappingResponse)
async def auto_map(request: AutoMappingRequest) -> AutoMappingResponse:
    """Generate candidate mappings between uploaded source and target datasets."""

    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
        target = dataset_store.get_dataset(request.target_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    prepared_source_schema, applied_persistent_hints = _prepare_source_schema_with_persistent_hints(
        source.handle.schema_profile,
        source_system=request.source_system,
        business_domain=request.business_domain,
        integration_name=request.integration_name,
    )

    response = generate_mapping_candidates(
        prepared_source_schema,
        target.handle.schema_profile,
        llm_provider=build_provider_from_settings() if request.use_llm else None,
        description_priority=request.description_priority or bool(applied_persistent_hints),
    )
    return _attach_applied_source_field_hints(response, applied_persistent_hints)


@router.post("/auto/jobs", response_model=MappingJobStartResponse)
async def start_auto_map_job(request: AutoMappingRequest) -> MappingJobStartResponse:
    """Start asynchronous mapping generation for uploaded source and target datasets."""

    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
        target = dataset_store.get_dataset(request.target_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    prepared_source_schema, applied_persistent_hints = _prepare_source_schema_with_persistent_hints(
        source.handle.schema_profile,
        source_system=request.source_system,
        business_domain=request.business_domain,
        integration_name=request.integration_name,
    )

    def worker(progress_callback):
        response = generate_mapping_candidates(
            prepared_source_schema,
            target.handle.schema_profile,
            llm_provider=build_provider_from_settings() if request.use_llm else None,
            progress_callback=progress_callback,
            description_priority=request.description_priority or bool(applied_persistent_hints),
        )
        return _attach_applied_source_field_hints(response, applied_persistent_hints)

    try:
        job = mapping_job_store.start(worker)
    except MappingJobCapacityError as error:
        raise HTTPException(
            status_code=429,
            detail=str(error),
            headers={"Retry-After": "5"},
        ) from error
    return MappingJobStartResponse(job_id=job.job_id, status=job.status)


@router.post("/canonical", response_model=AutoMappingResponse)
async def canonical_map(request: CanonicalMappingRequest) -> AutoMappingResponse:
    """Generate mappings from a source dataset into the virtual canonical target schema."""

    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    target_schema = build_virtual_target_schema(request.target_system)
    if not target_schema.columns:
        raise HTTPException(status_code=400, detail="Canonical glossary is empty; cannot build virtual canonical target.")

    prepared_source_schema, applied_persistent_hints = _prepare_source_schema_with_persistent_hints(
        source.handle.schema_profile,
        source_system=request.source_system,
        business_domain=request.business_domain,
        integration_name=request.integration_name,
    )

    response = generate_mapping_candidates(
        prepared_source_schema,
        target_schema,
        llm_provider=build_provider_from_settings() if request.use_llm else None,
        description_priority=request.description_priority or bool(applied_persistent_hints),
        candidate_pool_size=request.candidate_pool_size,
    )
    return _attach_applied_source_field_hints(response, applied_persistent_hints)


@router.get("/target-fields", response_model=list[str])
async def list_mapping_target_fields(target_system: str | None = Query(default=None)) -> list[str]:
    """List available target field names for a supported virtual target system."""

    normalized_target_system = str(target_system or "").strip().lower()
    if normalized_target_system:
        if normalized_target_system != "canonical":
            raise HTTPException(status_code=400, detail=f"Unsupported target_system: {target_system}")
        target_schema = build_virtual_target_schema("canonical")
        if not target_schema.columns:
            raise HTTPException(status_code=400, detail="Canonical glossary is empty; cannot build virtual canonical target.")
        return [column.name for column in target_schema.columns]

    raise HTTPException(status_code=400, detail="Provide target_system to list mapping target fields.")


@router.post("/refine", response_model=SourceMappingResult)
async def refine_mapping(request: MappingRefinementRequest) -> SourceMappingResult:
    """Re-rank candidate targets for one source field using inline refinement hints."""

    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    target_schema = _resolve_refinement_target_schema(request)
    prepared_source_schema, _applied_persistent_hints = _prepare_source_schema_with_persistent_hints(
        source.handle.schema_profile,
        source_system=request.source_system,
        business_domain=request.business_domain,
        integration_name=request.integration_name,
    )
    source_column = _find_schema_column(prepared_source_schema, request.source_field)
    if source_column is None:
        raise HTTPException(status_code=404, detail=f"Source field '{request.source_field}' was not found in the source schema.")

    refined_source_column = apply_inline_source_field_hint(
        source_column,
        meaning_hint=request.meaning_hint,
        negative_hint=request.negative_hint,
        sample_values=request.sample_values,
        refinement_instruction=request.refinement_instruction,
    )
    effective_description_priority = request.description_priority or any(
        [
            request.meaning_hint.strip(),
            request.negative_hint.strip(),
            list(request.sample_values),
            request.refinement_instruction.strip(),
        ]
    )
    try:
        return refine_mapping_for_source(
            refined_source_column,
            list(target_schema.columns),
            llm_provider=build_provider_from_settings() if request.use_llm else None,
            description_priority=effective_description_priority,
            candidate_pool_size=request.candidate_pool_size,
            candidate_target_names=request.candidate_targets,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/canonical/jobs", response_model=MappingJobStartResponse)
async def start_canonical_map_job(request: CanonicalMappingRequest) -> MappingJobStartResponse:
    """Start asynchronous canonical-only mapping generation for one source dataset."""

    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    target_schema = build_virtual_target_schema(request.target_system)
    if not target_schema.columns:
        raise HTTPException(status_code=400, detail="Canonical glossary is empty; cannot build virtual canonical target.")

    prepared_source_schema, applied_persistent_hints = _prepare_source_schema_with_persistent_hints(
        source.handle.schema_profile,
        source_system=request.source_system,
        business_domain=request.business_domain,
        integration_name=request.integration_name,
    )

    def worker(progress_callback):
        response = generate_mapping_candidates(
            prepared_source_schema,
            target_schema,
            llm_provider=build_provider_from_settings() if request.use_llm else None,
            progress_callback=progress_callback,
            description_priority=request.description_priority or bool(applied_persistent_hints),
            candidate_pool_size=request.candidate_pool_size,
        )
        return _attach_applied_source_field_hints(response, applied_persistent_hints)

    try:
        job = mapping_job_store.start(worker)
    except MappingJobCapacityError as error:
        raise HTTPException(
            status_code=429,
            detail=str(error),
            headers={"Retry-After": "5"},
        ) from error
    return MappingJobStartResponse(job_id=job.job_id, status=job.status)


@router.get("/jobs/{job_id}", response_model=MappingJobStatusResponse)
async def get_mapping_job_status(job_id: str) -> MappingJobStatusResponse:
    """Return the current runtime status for one background mapping job."""

    try:
        return mapping_job_store.get_status(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Mapping job not found: {job_id}") from error


@router.post("/jobs/{job_id}/cancel", response_model=MappingJobStatusResponse)
async def cancel_mapping_job(job_id: str) -> MappingJobStatusResponse:
    """Cancel one background mapping job if it is still running."""

    try:
        return mapping_job_store.cancel(job_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Mapping job not found: {job_id}") from error


@router.post("/preview", response_model=PreviewResponse)
async def preview_mapping(request: PreviewRequest) -> PreviewResponse:
    """Preview mapping decisions against uploaded source rows before export or apply."""

    try:
        source = dataset_store.get_dataset(request.source_dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return build_preview(source.rows, request.mapping_decisions)


@router.post("/analysis/summary", response_model=MappingAnalysisSummaryResponse)
async def summarize_mapping_analysis(request: MappingAnalysisRequest) -> MappingAnalysisSummaryResponse:
    """Generate a bounded textual analysis summary for the current mapping decisions."""

    provider = build_provider_from_settings()
    return build_mapping_analysis_summary(request, provider=provider)


@router.post("/analysis/narration", response_model=MappingAnalysisNarrationResponse)
async def narrate_mapping_analysis(request: MappingAnalysisNarrationRequest) -> MappingAnalysisNarrationResponse:
    """Generate a spoken-script style narration for the current mapping analysis."""

    provider = build_provider_from_settings()
    return build_mapping_analysis_narration(request, provider=provider)


@router.post("/analysis/audio")
async def synthesize_mapping_analysis_audio(request: MappingAnalysisAudioRequest) -> Response:
    """Synthesize WAV audio for a prepared mapping-analysis spoken script."""

    try:
        audio_bytes = synthesize_orpheus_wav(
            request.spoken_script,
            voice=request.voice,
            model=request.model,
        )
    except (ImportError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'inline; filename="mapping_analysis.wav"',
            "X-Audio-Provider": "lmstudio_orpheus",
        },
    )


@router.post("/review-plan", response_model=ReviewPlanResponse)
async def summarize_review_plan(request: ReviewPlanRequest) -> ReviewPlanResponse:
    """Generate a bounded review plan for unresolved or risky mapping decisions."""

    provider = build_provider_from_settings()
    return build_review_plan(request, provider=provider)


@router.get("/source-field-hints", response_model=list[SourceFieldHintRecord])
async def list_source_field_hints(
    source_system: str = Query(...),
    business_domain: str | None = Query(default=None),
    integration_name: str | None = Query(default=None),
    source_field: str | None = Query(default=None),
    active_only: bool = Query(default=True),
) -> list[SourceFieldHintRecord]:
    """List persisted source-field hints scoped to system, integration, or field."""

    return persistence_service.list_source_field_hints(
        source_system=source_system,
        business_domain=business_domain,
        integration_name=integration_name,
        source_field=source_field,
        active_only=active_only,
    )


@router.post("/source-field-hints", response_model=SourceFieldHintRecord)
async def save_source_field_hint(request: SourceFieldHintUpsertRequest) -> SourceFieldHintRecord:
    """Create or update one persistent source-field hint used during mapping."""

    try:
        return persistence_service.save_source_field_hint(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/codegen", response_model=GeneratedArtifact)
async def codegen_mapping(request: CodegenRequest) -> GeneratedArtifact:
    """Generate Pandas, PySpark, or dbt mapping code from accepted mapping decisions."""

    _require_accepted_output_decisions(
        request.mapping_decisions,
        action_label="Code generation",
        allow_unaccepted=request.allow_unaccepted,
    )
    if request.mode == "pyspark":
        return generate_pyspark_code(request.mapping_decisions)
    if request.mode == "dbt":
        return generate_dbt_code(request.mapping_decisions)
    return generate_pandas_code(request.mapping_decisions)


@router.post("/codegen/refine", response_model=ArtifactRefinementResponse)
async def refine_codegen_artifact(request: ArtifactRefinementRequest) -> ArtifactRefinementResponse:
    """Ask the bounded LLM to refine an already generated mapping artifact."""

    _require_accepted_output_decisions(
        request.mapping_decisions,
        action_label="Code refinement",
        allow_unaccepted=request.allow_unaccepted,
    )
    provider = build_provider_from_settings()
    if provider is None:
        raise HTTPException(status_code=503, detail="LLM provider is not configured.")

    result = call_artifact_refinement(
        mapping_decisions=[decision.model_dump() for decision in request.mapping_decisions],
        mode=request.mode,
        current_code=request.current_code,
        instruction=request.instruction,
        edge_cases=request.edge_cases,
        reference_excerpt=request.reference_excerpt,
        provider=provider,
    )
    if result is None:
        raise HTTPException(status_code=502, detail="LLM did not return a valid artifact refinement.")
    return result


@router.post("/sets", response_model=MappingSetRecord, dependencies=[Depends(require_admin)])
async def create_mapping_set(request: MappingSetCreateRequest) -> MappingSetRecord:
    """Persist a reviewed mapping set together with metadata and audit history."""

    saved = mapping_governance_repository.save_mapping_set(
        request.name,
        request.mapping_decisions,
        source_dataset_id=request.source_dataset_id,
        target_dataset_id=request.target_dataset_id,
        integration_name=request.integration_name,
        source_system=request.source_system,
        target_system=request.target_system,
        business_domain=request.business_domain,
        interface_type=request.interface_type,
        description=request.description,
        artifact_type=request.artifact_type,
        canonical_concepts=request.canonical_concepts,
        unmatched_sources=request.unmatched_sources,
        created_by=request.created_by,
        note=request.note,
        owner=request.owner,
        assignee=request.assignee,
        review_note=request.review_note,
    )
    append_mapping_set_audit("create", saved, changed_by=request.created_by, note=request.note)
    return saved


@router.post("/draft-sessions", response_model=DraftSessionRecord, dependencies=[Depends(require_admin)])
async def create_draft_session(request: DraftSessionCreateRequest) -> DraftSessionRecord:
    """Persist one minimal durable workspace snapshot for later resume."""

    if request.mapping_mode == "standard" and request.target_handle is None:
        raise HTTPException(status_code=400, detail="Standard draft sessions require a target_handle snapshot.")
    return draft_session_repository.save_draft_session(request)


@router.get("/draft-sessions", response_model=list[DraftSessionRecord], dependencies=[Depends(require_admin)])
async def list_draft_sessions() -> list[DraftSessionRecord]:
    """List saved durable workspace snapshots available for resume."""

    return draft_session_repository.list_draft_sessions()


@router.get("/draft-sessions/{draft_session_id}", response_model=DraftSessionDetail, dependencies=[Depends(require_admin)])
async def get_draft_session(draft_session_id: int) -> DraftSessionDetail:
    """Return one saved durable workspace snapshot with its restore payload."""

    try:
        return draft_session_repository.get_draft_session(draft_session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/sets", response_model=list[MappingSetRecord], dependencies=[Depends(require_admin)])
async def list_mapping_sets() -> list[MappingSetRecord]:
    """List persisted mapping sets available for governance and reuse."""

    return mapping_governance_repository.list_mapping_sets()


@router.get("/sets/{mapping_set_id}", response_model=MappingSetDetail, dependencies=[Depends(require_admin)])
async def get_mapping_set(mapping_set_id: int) -> MappingSetDetail:
    """Return one persisted mapping set with full decision and governance detail."""

    try:
        return mapping_governance_repository.get_mapping_set(mapping_set_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sets/{mapping_set_id}/status", response_model=MappingSetRecord, dependencies=[Depends(require_admin)])
async def update_mapping_set_status(
    mapping_set_id: int,
    request: MappingSetStatusUpdateRequest,
) -> MappingSetRecord:
    """Update governance status and ownership fields for one mapping set."""

    try:
        updated = mapping_governance_repository.update_mapping_set_status(
            mapping_set_id,
            request.status,
            owner=request.owner,
            assignee=request.assignee,
            review_note=request.review_note,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    append_mapping_set_audit("status_change", updated, changed_by=request.changed_by, note=request.note)
    return updated


@router.post("/sets/{mapping_set_id}/apply", response_model=MappingSetDetail, dependencies=[Depends(require_admin)])
async def apply_mapping_set(
    mapping_set_id: int,
    request: MappingSetApplyRequest,
) -> MappingSetDetail:
    """Mark an approved mapping set as applied for downstream workspace reuse flows."""

    try:
        mapping_set = mapping_governance_repository.get_mapping_set(mapping_set_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if mapping_set.status != "approved":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Mapping set #{mapping_set_id} is in status '{mapping_set.status}' and cannot be applied. "
                "Only approved mapping sets can be used in workspace apply/reuse flows."
            ),
        )
    append_mapping_set_audit("apply", mapping_set, changed_by=request.changed_by, note=request.note)
    return mapping_set


@router.get("/sets/{mapping_set_id}/audit", response_model=list[MappingSetAuditEntry], dependencies=[Depends(require_admin)])
async def get_mapping_set_audit(mapping_set_id: int) -> list[MappingSetAuditEntry]:
    """Return the audit trail for one persisted mapping set."""

    return mapping_governance_repository.list_audit_logs(mapping_set_id)


@router.get("/sets/{mapping_set_id}/diff", response_model=MappingSetDiffResponse, dependencies=[Depends(require_admin)])
async def get_mapping_set_diff(
    mapping_set_id: int,
    against_id: int = Query(...),
) -> MappingSetDiffResponse:
    """Compare one mapping set against another persisted version."""

    try:
        return mapping_governance_repository.diff_mapping_sets(mapping_set_id, against_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/transformation/templates", response_model=list[TransformationTemplate])
async def get_transformation_templates() -> list[TransformationTemplate]:
    """List reusable built-in transformation templates exposed to the mapping UI."""

    return list_transformation_templates()


@router.post(
    "/transformation/test-sets",
    response_model=TransformationTestSetRecord,
    dependencies=[Depends(require_admin)],
)
async def create_transformation_test_set(
    request: TransformationTestSetCreateRequest,
) -> TransformationTestSetRecord:
    """Persist a reusable transformation test set for accepted mapping decisions."""

    _require_accepted_output_decisions(
        request.mapping_decisions,
        action_label="Transformation test set save",
    )
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
    """List persisted transformation test sets available to admins."""

    return persistence_service.list_transformation_test_sets()


@router.get(
    "/transformation/test-sets/{test_set_id}",
    response_model=TransformationTestSetDetail,
    dependencies=[Depends(require_admin)],
)
async def get_transformation_test_set(test_set_id: int) -> TransformationTestSetDetail:
    """Return one transformation test set with its cases and mapping decisions."""

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
    """Execute one saved transformation test set against its accepted mapping decisions."""

    try:
        test_set = persistence_service.get_transformation_test_set(test_set_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    _require_accepted_output_decisions(test_set.mapping_decisions, action_label="Transformation test set run")
    return run_transformation_test_set(test_set)


@router.post("/transformation/generate", response_model=TransformationGenerationResponse)
async def generate_transformation(request: TransformationGenerationRequest) -> TransformationGenerationResponse:
    """Generate a bounded transformation suggestion for one source-target column pair."""

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