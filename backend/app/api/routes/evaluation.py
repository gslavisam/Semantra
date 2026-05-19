"""Benchmark and evaluation endpoints for Semantra quality measurement flows."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_admin
from app.core.config import settings
from app.models.mapping import BenchmarkDatasetCreateRequest, BenchmarkDatasetRecord, BenchmarkExplanationRequest, BenchmarkExplanationResponse, CorrectionImpactMetrics, EvaluationMetrics, EvaluationRunRecord, EvaluationRunRequest, ScoringProfileComparisonResponse
from app.services.benchmark_explanation_service import build_benchmark_explanation
from app.services.evaluation_service import build_scoring_profile_comparison_response, evaluate_cases, evaluate_correction_impact
from app.services.llm_service import build_provider_from_settings
from app.services.persistence_service import persistence_service


router = APIRouter(prefix="/evaluation", tags=["evaluation"])
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mapping_gold.json"


@router.get("/benchmark", response_model=EvaluationMetrics)
async def run_benchmark() -> EvaluationMetrics:
    """Run the built-in gold benchmark fixture against the current mapping configuration."""

    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return evaluate_cases(cases)


@router.post("/run", response_model=EvaluationMetrics)
async def run_custom_benchmark(request: EvaluationRunRequest) -> EvaluationMetrics:
    """Run an ad hoc evaluation benchmark supplied in the request payload."""

    return evaluate_cases(request.cases)


@router.post("/explain", response_model=BenchmarkExplanationResponse, dependencies=[Depends(require_admin)])
async def explain_benchmark_results(request: BenchmarkExplanationRequest) -> BenchmarkExplanationResponse:
    """Generate an admin explanation of benchmark outcomes and likely quality signals."""

    provider = build_provider_from_settings()
    return build_benchmark_explanation(request, provider=provider)


@router.post("/datasets", response_model=BenchmarkDatasetRecord, dependencies=[Depends(require_admin)])
async def create_benchmark_dataset(request: BenchmarkDatasetCreateRequest) -> BenchmarkDatasetRecord:
    """Persist a reusable benchmark dataset for later comparison and reporting."""

    return persistence_service.save_benchmark_dataset(request.name, request.cases)


@router.get("/datasets", response_model=list[BenchmarkDatasetRecord], dependencies=[Depends(require_admin)])
async def list_benchmark_datasets() -> list[BenchmarkDatasetRecord]:
    """List saved benchmark datasets available to admin users."""

    return persistence_service.list_benchmark_datasets()


@router.post("/datasets/{dataset_id}/run", response_model=EvaluationMetrics, dependencies=[Depends(require_admin)])
async def run_saved_benchmark(dataset_id: int, with_configured_llm: bool = Query(default=False)) -> EvaluationMetrics:
    """Run one saved benchmark dataset, optionally with the configured LLM enabled."""

    try:
        cases = persistence_service.get_benchmark_dataset_cases(dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    dataset = next((record for record in persistence_service.list_benchmark_datasets() if record.dataset_id == dataset_id), None)
    llm_provider = build_provider_from_settings() if with_configured_llm else None
    metrics = evaluate_cases(cases, llm_provider=llm_provider)
    persistence_service.save_evaluation_run(
        dataset_id=dataset_id,
        dataset_name=dataset.name if dataset else None,
        provider_name=settings.llm_provider if with_configured_llm else "none",
        metrics=metrics,
    )
    return metrics


@router.post("/datasets/{dataset_id}/correction-impact", response_model=CorrectionImpactMetrics, dependencies=[Depends(require_admin)])
async def run_saved_benchmark_correction_impact(
    dataset_id: int,
    with_configured_llm: bool = Query(default=False),
) -> CorrectionImpactMetrics:
    """Measure how persisted correction feedback changes benchmark accuracy for one dataset."""

    try:
        cases = persistence_service.get_benchmark_dataset_cases(dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    llm_provider = build_provider_from_settings() if with_configured_llm else None
    return evaluate_correction_impact(cases, llm_provider=llm_provider)


@router.post("/datasets/{dataset_id}/compare-profiles", response_model=ScoringProfileComparisonResponse, dependencies=[Depends(require_admin)])
async def compare_saved_benchmark_profiles(
    dataset_id: int,
    with_configured_llm: bool = Query(default=False),
    profiles: str = Query(default=""),
) -> ScoringProfileComparisonResponse:
    """Compare scoring profiles on one saved benchmark dataset and recommend a default."""

    try:
        cases = persistence_service.get_benchmark_dataset_cases(dataset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    llm_provider = build_provider_from_settings() if with_configured_llm else None
    profile_names = [item.strip() for item in profiles.split(",") if item.strip()] or None
    return build_scoring_profile_comparison_response(cases, profile_names=profile_names, llm_provider=llm_provider)


@router.get("/runs", response_model=list[EvaluationRunRecord], dependencies=[Depends(require_admin)])
async def list_evaluation_runs() -> list[EvaluationRunRecord]:
    """List persisted benchmark run history for admin review."""

    return persistence_service.list_evaluation_runs()