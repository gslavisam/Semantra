from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ConfidenceLabel = Literal["high_confidence", "medium_confidence", "low_confidence"]
DecisionStatus = Literal["accepted", "needs_review", "rejected"]


class ScoringSignals(BaseModel):
    name: float = 0.0
    semantic: float = 0.0
    pattern: float = 0.0
    statistical: float = 0.0
    overlap: float = 0.0
    embedding: float = 0.0
    correction: float = 0.0
    llm: float = 0.0


class CandidateOption(BaseModel):
    target: str
    confidence: float
    confidence_label: ConfidenceLabel
    method: str
    signals: ScoringSignals
    explanation: list[str] = Field(default_factory=list)


class LLMValidationResult(BaseModel):
    selected_target: str
    confidence: float
    reasoning: list[str] = Field(default_factory=list)
    transformation_code: str | None = None
    raw_response: str | None = None


class MappingCandidate(BaseModel):
    source: str
    target: str | None = None
    confidence: float
    confidence_label: ConfidenceLabel
    status: DecisionStatus
    method: str
    signals: ScoringSignals
    explanation: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    transformation_code: str | None = None


class SourceMappingResult(BaseModel):
    source: str
    selected: MappingCandidate | None = None
    candidates: list[CandidateOption] = Field(default_factory=list)


class MappingDecision(BaseModel):
    source: str
    target: str
    status: DecisionStatus = "accepted"
    transformation_code: str | None = None


class AutoMappingRequest(BaseModel):
    source_dataset_id: str
    target_dataset_id: str


class AutoMappingResponse(BaseModel):
    mappings: list[MappingCandidate] = Field(default_factory=list)
    ranked_mappings: list[SourceMappingResult] = Field(default_factory=list)


class DecisionLogEntry(BaseModel):
    source: str
    candidate_targets: list[str] = Field(default_factory=list)
    heuristic_scores: dict[str, float] = Field(default_factory=dict)
    llm_result: LLMValidationResult | None = None
    final_target: str | None = None
    final_status: DecisionStatus = "needs_review"
    used_llm: bool = False


class UserCorrectionEntry(BaseModel):
    correction_id: int | None = None
    source: str
    suggested_target: str | None = None
    corrected_target: str
    note: str | None = None
    version: int = 1
    created_at: str | None = None


class RuntimeConfigSnapshot(BaseModel):
    llm_provider: str
    llm_model: str
    embedding_provider: str
    cors_origins: list[str] = Field(default_factory=list)
    sqlite_path: str
    llm_gate_min_score: float
    llm_gate_max_score: float
    admin_api_token_configured: bool = False


class BenchmarkDatasetCreateRequest(BaseModel):
    name: str
    cases: list[dict[str, Any]] = Field(default_factory=list)


class BenchmarkDatasetRecord(BaseModel):
    dataset_id: int
    name: str
    case_count: int
    version: int = 1
    created_at: str | None = None


class EvaluationMetrics(BaseModel):
    total_cases: int
    total_fields: int
    correct_matches: int
    top1_accuracy: float
    accuracy: float
    confidence_by_bucket: dict[str, float] = Field(default_factory=dict)


class EvaluationRunRecord(BaseModel):
    run_id: int
    dataset_id: int | None = None
    dataset_name: str | None = None
    provider_name: str = "none"
    total_cases: int
    total_fields: int
    correct_matches: int
    top1_accuracy: float
    accuracy: float
    confidence_by_bucket: dict[str, float] = Field(default_factory=dict)
    created_at: str | None = None


class EvaluationRunRequest(BaseModel):
    cases: list[dict[str, Any]] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    source_dataset_id: str
    mapping_decisions: list[MappingDecision]


class PreviewRow(BaseModel):
    values: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    preview: list[PreviewRow] = Field(default_factory=list)
    unresolved_targets: list[str] = Field(default_factory=list)


class CodegenRequest(BaseModel):
    mapping_decisions: list[MappingDecision]


class GeneratedArtifact(BaseModel):
    language: Literal["python-pandas"] = "python-pandas"
    code: str
    warnings: list[str] = Field(default_factory=list)


class TransformationGenerationRequest(BaseModel):
    source_dataset_id: str
    target_dataset_id: str
    source_column: str
    target_column: str
    instruction: str = Field(min_length=1)


class TransformationGenerationResponse(BaseModel):
    transformation_code: str
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
