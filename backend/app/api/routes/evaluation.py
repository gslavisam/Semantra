from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_admin
from app.core.config import settings
from app.models.mapping import BenchmarkDatasetCreateRequest, BenchmarkDatasetRecord, EvaluationMetrics, EvaluationRunRecord, EvaluationRunRequest
from app.services.evaluation_service import evaluate_cases
from app.services.llm_service import build_provider_from_settings
from app.services.persistence_service import persistence_service


router = APIRouter(prefix="/evaluation", tags=["evaluation"])
FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "mapping_gold.json"


@router.get("/benchmark", response_model=EvaluationMetrics)
async def run_benchmark() -> EvaluationMetrics:
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return evaluate_cases(cases)


@router.post("/run", response_model=EvaluationMetrics)
async def run_custom_benchmark(request: EvaluationRunRequest) -> EvaluationMetrics:
    return evaluate_cases(request.cases)


@router.post("/datasets", response_model=BenchmarkDatasetRecord, dependencies=[Depends(require_admin)])
async def create_benchmark_dataset(request: BenchmarkDatasetCreateRequest) -> BenchmarkDatasetRecord:
    return persistence_service.save_benchmark_dataset(request.name, request.cases)


@router.get("/datasets", response_model=list[BenchmarkDatasetRecord], dependencies=[Depends(require_admin)])
async def list_benchmark_datasets() -> list[BenchmarkDatasetRecord]:
    return persistence_service.list_benchmark_datasets()


@router.post("/datasets/{dataset_id}/run", response_model=EvaluationMetrics, dependencies=[Depends(require_admin)])
async def run_saved_benchmark(dataset_id: int, with_configured_llm: bool = Query(default=False)) -> EvaluationMetrics:
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


@router.get("/runs", response_model=list[EvaluationRunRecord], dependencies=[Depends(require_admin)])
async def list_evaluation_runs() -> list[EvaluationRunRecord]:
    return persistence_service.list_evaluation_runs()