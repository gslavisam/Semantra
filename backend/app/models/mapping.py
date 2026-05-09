from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ConfidenceLabel = Literal["high_confidence", "medium_confidence", "low_confidence"]
DecisionStatus = Literal["accepted", "needs_review", "rejected"]
UserCorrectionStatus = Literal["accepted", "rejected", "overridden"]
ReusableCorrectionRuleStatus = Literal["accepted", "rejected", "overridden"]
MappingSetStatus = Literal["draft", "review", "approved", "archived"]
CatalogArtifactType = Literal["standard", "canonical-only"]
TransformationPreviewMode = Literal["direct", "custom"]
TransformationPreviewStatus = Literal["direct", "validated", "fallback"]
TransformationPreviewClassification = Literal["direct", "safe", "risky", "custom"]
TransformationIssueStage = Literal["preview", "codegen"]
TransformationIssueSeverity = Literal["warning", "error"]
TransformationWarningCode = Literal[
    "syntax_error",
    "runtime_error",
    "missing_source_column",
    "null_expansion",
    "type_coercion",
    "row_count_mismatch",
    "skipped_rejected_mapping",
]


class ScoringSignals(BaseModel):
    name: float = 0.0
    semantic: float = 0.0
    knowledge: float = 0.0
    canonical: float = 0.0
    pattern: float = 0.0
    statistical: float = 0.0
    overlap: float = 0.0
    embedding: float = 0.0
    correction: float = 0.0
    llm: float = 0.0


class CanonicalConceptMatchDetail(BaseModel):
    concept_id: str
    display_name: str
    strength: float = 0.0


class CanonicalMappingDetails(BaseModel):
    source_concepts: list[CanonicalConceptMatchDetail] = Field(default_factory=list)
    target_concepts: list[CanonicalConceptMatchDetail] = Field(default_factory=list)
    shared_concepts: list[CanonicalConceptMatchDetail] = Field(default_factory=list)


class CandidateOption(BaseModel):
    target: str
    confidence: float
    confidence_label: ConfidenceLabel
    method: str
    signals: ScoringSignals
    explanation: list[str] = Field(default_factory=list)
    canonical_details: CanonicalMappingDetails = Field(default_factory=CanonicalMappingDetails)


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
    canonical_details: CanonicalMappingDetails = Field(default_factory=CanonicalMappingDetails)
    alternatives: list[str] = Field(default_factory=list)
    transformation_code: str | None = None
    llm_consulted: bool = False
    llm_recommendation: LLMValidationResult | None = None


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
    use_llm: bool = True


TargetSystem = Literal["canonical"]


class CanonicalMappingRequest(BaseModel):
    source_dataset_id: str
    target_system: TargetSystem = "canonical"
    use_llm: bool = True


class CanonicalCoverageColumnMatch(BaseModel):
    column: str
    concept_ids: list[str] = Field(default_factory=list)


class CanonicalCoverageSummary(BaseModel):
    total_columns: int = 0
    matched_columns: int = 0
    coverage_ratio: float = 0.0
    unmatched_columns: list[str] = Field(default_factory=list)
    matched_columns_detail: list[CanonicalCoverageColumnMatch] = Field(default_factory=list)


class CanonicalCoverageProjectSummary(BaseModel):
    total_columns: int = 0
    matched_columns: int = 0
    coverage_ratio: float = 0.0
    concept_count: int = 0
    shared_concept_count: int = 0
    concepts: list[str] = Field(default_factory=list)
    shared_concepts: list[str] = Field(default_factory=list)
    source_only_concepts: list[str] = Field(default_factory=list)
    target_only_concepts: list[str] = Field(default_factory=list)


class CanonicalCoverageReport(BaseModel):
    source: CanonicalCoverageSummary = Field(default_factory=CanonicalCoverageSummary)
    target: CanonicalCoverageSummary = Field(default_factory=CanonicalCoverageSummary)
    project: CanonicalCoverageProjectSummary = Field(default_factory=CanonicalCoverageProjectSummary)


class AutoMappingResponse(BaseModel):
    mappings: list[MappingCandidate] = Field(default_factory=list)
    ranked_mappings: list[SourceMappingResult] = Field(default_factory=list)
    canonical_coverage: CanonicalCoverageReport = Field(default_factory=CanonicalCoverageReport)


MappingJobStatus = Literal["queued", "running", "completed", "failed"]


class MappingJobStartResponse(BaseModel):
    job_id: str
    status: MappingJobStatus


class MappingJobStatusResponse(BaseModel):
    job_id: str
    status: MappingJobStatus
    activity: list[str] = Field(default_factory=list)
    response: AutoMappingResponse | None = None
    error: str | None = None


CanonicalGapSuggestionAction = Literal["existing_concept_alias", "new_canonical_concept", "no_action"]
CanonicalGapDisposition = Literal["ignored", "rejected"]


class CanonicalGapCandidate(BaseModel):
    source: str
    target: str
    confidence: float = 0.0
    confidence_label: ConfidenceLabel = "low_confidence"
    status: DecisionStatus = "needs_review"
    method: str = "multi_signal_heuristic"
    signals: ScoringSignals = Field(default_factory=ScoringSignals)
    explanation: list[str] = Field(default_factory=list)
    canonical_details: CanonicalMappingDetails = Field(default_factory=CanonicalMappingDetails)
    reason: str = ""


class CanonicalGapCandidatesRequest(BaseModel):
    mapping_response: AutoMappingResponse
    min_confidence: float = 0.65


class CanonicalGapCandidatesResponse(BaseModel):
    candidates: list[CanonicalGapCandidate] = Field(default_factory=list)


class CanonicalGapSuggestionRequest(BaseModel):
    candidate: CanonicalGapCandidate


class CanonicalGapSuggestion(BaseModel):
    action: CanonicalGapSuggestionAction = "no_action"
    concept_id: str | None = None
    display_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reasoning: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    raw_response: str | None = None


class CanonicalGapApproveRequest(BaseModel):
    candidate: CanonicalGapCandidate
    suggestion: CanonicalGapSuggestion
    approved_by: str | None = None
    overlay_name: str | None = None


class CanonicalGapApproveResponse(BaseModel):
    overlay_id: int
    overlay_name: str
    saved_entry_count: int = 0
    activated: bool = True


class CanonicalGapRejectRequest(BaseModel):
    candidate: CanonicalGapCandidate
    suggestion: CanonicalGapSuggestion | None = None
    disposition: CanonicalGapDisposition = "rejected"
    rejected_by: str | None = None
    note: str | None = None


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
    corrected_target: str | None = None
    status: UserCorrectionStatus = "overridden"
    note: str | None = None
    version: int = 1
    created_at: str | None = None


class CorrectionRuleCandidate(BaseModel):
    source: str
    suggested_target: str | None = None
    corrected_target: str | None = None
    status: UserCorrectionStatus
    occurrence_count: int = 0
    recommendation: str
    already_promoted: bool = False
    promoted_rule_id: int | None = None


class ReusableCorrectionRule(BaseModel):
    rule_id: int | None = None
    source: str
    suggested_target: str | None = None
    corrected_target: str | None = None
    status: ReusableCorrectionRuleStatus
    occurrence_count: int = 0
    created_by: str | None = None
    note: str | None = None
    active: bool = True
    created_at: str | None = None


class ReusableCorrectionRulePromotionRequest(BaseModel):
    source: str
    suggested_target: str | None = None
    corrected_target: str | None = None
    status: ReusableCorrectionRuleStatus
    occurrence_count: int = 0
    created_by: str | None = None
    note: str | None = None


class MappingSetCreateRequest(BaseModel):
    name: str
    source_dataset_id: str | None = None
    target_dataset_id: str | None = None
    mapping_decisions: list[MappingDecision] = Field(default_factory=list)
    integration_name: str | None = None
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    interface_type: str | None = None
    description: str | None = None
    artifact_type: CatalogArtifactType | None = None
    canonical_concepts: list[str] = Field(default_factory=list)
    unmatched_sources: list[str] = Field(default_factory=list)
    created_by: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None


class MappingSetRecord(BaseModel):
    mapping_set_id: int
    name: str
    status: MappingSetStatus = "draft"
    version: int = 1
    decision_count: int = 0
    source_dataset_id: str | None = None
    target_dataset_id: str | None = None
    integration_name: str | None = None
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    interface_type: str | None = None
    description: str | None = None
    artifact_type: CatalogArtifactType = "standard"
    canonical_concepts: list[str] = Field(default_factory=list)
    unmatched_sources: list[str] = Field(default_factory=list)
    created_by: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None
    created_at: str | None = None


class MappingSetDetail(MappingSetRecord):
    mapping_decisions: list[MappingDecision] = Field(default_factory=list)


class CatalogIntegrationRecord(BaseModel):
    mapping_set_id: int
    name: str
    integration_name: str
    version: int = 1
    status: MappingSetStatus = "draft"
    artifact_type: CatalogArtifactType = "standard"
    decision_count: int = 0
    source_dataset_id: str | None = None
    target_dataset_id: str | None = None
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    interface_type: str | None = None
    description: str | None = None
    canonical_concepts: list[str] = Field(default_factory=list)
    unmatched_sources: list[str] = Field(default_factory=list)
    created_by: str | None = None
    owner: str | None = None
    assignee: str | None = None
    created_at: str | None = None


class CatalogIntegrationDetail(BaseModel):
    integration_name: str
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    interface_type: str | None = None
    description: str | None = None
    canonical_concepts: list[str] = Field(default_factory=list)
    unmatched_sources: list[str] = Field(default_factory=list)
    latest_version: CatalogIntegrationRecord
    latest_approved_version: CatalogIntegrationRecord | None = None
    versions: list[CatalogIntegrationRecord] = Field(default_factory=list)
    similar_integrations: list["CatalogSimilarIntegrationRecord"] = Field(default_factory=list)


class CatalogSimilarIntegrationRecord(BaseModel):
    integration_name: str
    similarity_score: float = 0.0
    shared_concepts: list[str] = Field(default_factory=list)
    shared_concept_count: int = 0
    same_source_system: bool = False
    same_target_system: bool = False
    same_business_domain: bool = False
    same_artifact_type: bool = False
    latest_version: CatalogIntegrationRecord
    latest_approved_version: CatalogIntegrationRecord | None = None


class CatalogConceptUsageRecord(BaseModel):
    concept_id: str
    mapping_set_id: int
    name: str
    integration_name: str
    version: int = 1
    status: MappingSetStatus = "draft"
    artifact_type: CatalogArtifactType = "standard"
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    owner: str | None = None
    created_at: str | None = None


class CatalogConceptDetail(BaseModel):
    concept_id: str
    usage_count: int = 0
    integrations: list[CatalogConceptUsageRecord] = Field(default_factory=list)


class MappingSetStatusUpdateRequest(BaseModel):
    status: MappingSetStatus
    changed_by: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None


class MappingSetApplyRequest(BaseModel):
    changed_by: str | None = None
    note: str | None = None


class MappingSetAuditEntry(BaseModel):
    audit_id: int | None = None
    mapping_set_id: int
    mapping_set_name: str
    version: int
    action: str
    status: MappingSetStatus
    changed_by: str | None = None
    note: str | None = None
    created_at: str | None = None


class MappingSetDecisionDiffEntry(BaseModel):
    change_type: Literal["added", "removed", "changed"]
    source: str
    from_target: str | None = None
    to_target: str | None = None
    from_status: DecisionStatus | None = None
    to_status: DecisionStatus | None = None
    from_transformation_code: str | None = None
    to_transformation_code: str | None = None


class MappingSetDiffResponse(BaseModel):
    current_mapping_set_id: int
    current_name: str
    current_version: int
    against_mapping_set_id: int
    against_name: str
    against_version: int
    added_count: int = 0
    removed_count: int = 0
    changed_count: int = 0
    changes: list[MappingSetDecisionDiffEntry] = Field(default_factory=list)


class RuntimeConfigSnapshot(BaseModel):
    llm_provider: str
    llm_model: str
    llm_timeout_seconds: float
    lmstudio_base_url: str
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


class CorrectionImpactMetrics(BaseModel):
    baseline: EvaluationMetrics
    correction_aware: EvaluationMetrics
    accuracy_delta: float = 0.0
    top1_accuracy_delta: float = 0.0
    correct_matches_delta: int = 0


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


class TransformationPreviewWarning(BaseModel):
    code: TransformationWarningCode
    message: str
    source: str | None = None
    target: str | None = None
    stage: TransformationIssueStage = "preview"
    severity: TransformationIssueSeverity = "warning"
    fallback_applied: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class TransformationPreviewResult(BaseModel):
    source: str
    target: str
    mode: TransformationPreviewMode = "direct"
    status: TransformationPreviewStatus = "direct"
    classification: TransformationPreviewClassification = "direct"
    before_samples: list[str] = Field(default_factory=list)
    after_samples: list[str] = Field(default_factory=list)
    warnings: list[TransformationPreviewWarning] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    preview: list[PreviewRow] = Field(default_factory=list)
    unresolved_targets: list[str] = Field(default_factory=list)
    transformation_previews: list[TransformationPreviewResult] = Field(default_factory=list)


class TransformationTestAssertion(BaseModel):
    target: str
    expected_status: TransformationPreviewStatus | None = None
    expected_classification: TransformationPreviewClassification | None = None
    expected_warning_codes: list[TransformationWarningCode] | None = None
    expected_output_values: list[str] | None = None


class TransformationTestCase(BaseModel):
    case_name: str
    source_rows: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[TransformationTestAssertion] = Field(default_factory=list)


class TransformationTestSetCreateRequest(BaseModel):
    name: str
    mapping_decisions: list[MappingDecision] = Field(default_factory=list)
    cases: list[TransformationTestCase] = Field(default_factory=list)


class TransformationTestSetRecord(BaseModel):
    test_set_id: int
    name: str
    mapping_count: int
    case_count: int
    version: int = 1
    created_at: str | None = None


class TransformationTestSetDetail(TransformationTestSetRecord):
    mapping_decisions: list[MappingDecision] = Field(default_factory=list)
    cases: list[TransformationTestCase] = Field(default_factory=list)


class TransformationTestCaseResult(BaseModel):
    case_name: str
    passed: bool
    failures: list[str] = Field(default_factory=list)
    preview: list[PreviewRow] = Field(default_factory=list)
    transformation_previews: list[TransformationPreviewResult] = Field(default_factory=list)


class TransformationTestSetRunResponse(BaseModel):
    test_set_id: int
    name: str
    passed: bool
    total_cases: int
    passed_cases: int
    case_results: list[TransformationTestCaseResult] = Field(default_factory=list)


class CodegenRequest(BaseModel):
    mapping_decisions: list[MappingDecision]


class GeneratedArtifact(BaseModel):
    language: Literal["python-pandas"] = "python-pandas"
    code: str
    warnings: list[TransformationPreviewWarning] = Field(default_factory=list)


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


class TransformationTemplate(BaseModel):
    template_id: str
    name: str
    description: str
    code_template: str
