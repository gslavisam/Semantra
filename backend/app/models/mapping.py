"""Domain models for Semantra mapping, governance, preview, and evaluation payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.schema import DatasetHandle


ConfidenceLabel = Literal["high_confidence", "medium_confidence", "low_confidence"]
DecisionStatus = Literal["accepted", "needs_review", "rejected"]
MappingResolutionType = Literal["direct_mapping", "derived_value", "fixed_value", "target_managed", "out_of_scope"]
UserCorrectionStatus = Literal["accepted", "rejected", "overridden"]
ReusableCorrectionRuleStatus = Literal["accepted", "rejected", "overridden"]
MappingSetStatus = Literal["draft", "review", "approved", "archived"]
WorkspaceMappingMode = Literal["standard", "canonical"]
WorkspaceSection = Literal["Setup", "Review", "Decisions", "Output"]
CatalogArtifactType = Literal["standard", "canonical-only"]
TargetProjectionMode = Literal["dataset_to_dataset", "canonical_only", "target_aware_canonical"]
TransformationPreviewMode = Literal["direct", "custom"]
TransformationPreviewStatus = Literal["direct", "validated", "fallback"]
TransformationPreviewClassification = Literal["direct", "safe", "risky", "custom"]
TransformationIssueStage = Literal["preview", "codegen"]
TransformationIssueSeverity = Literal["warning", "error"]
CodegenMode = Literal["pandas", "pyspark", "dbt"]
TransformationSpecState = Literal["invalid", "incomplete", "ready"]
TransformationWarningCode = Literal[
    "syntax_error",
    "runtime_error",
    "missing_source_column",
    "null_expansion",
    "privacy_classification",
    "type_coercion",
    "row_count_mismatch",
    "skipped_rejected_mapping",
    "untranslated_custom_transformation",
]


class ScoringSignals(BaseModel):
    """Per-signal score breakdown used to rank one mapping candidate."""

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
    """Strength-weighted canonical concept match attached to a source or target field."""

    concept_id: str
    display_name: str
    strength: float = 0.0


class CanonicalMappingDetails(BaseModel):
    """Canonical concept resolution details for a source-target comparison."""

    source_concepts: list[CanonicalConceptMatchDetail] = Field(default_factory=list)
    target_concepts: list[CanonicalConceptMatchDetail] = Field(default_factory=list)
    shared_concepts: list[CanonicalConceptMatchDetail] = Field(default_factory=list)


class CandidateOption(BaseModel):
    """One candidate target option considered for a source field."""

    target: str
    confidence: float
    confidence_label: ConfidenceLabel
    method: str
    signals: ScoringSignals
    explanation: list[str] = Field(default_factory=list)
    canonical_details: CanonicalMappingDetails = Field(default_factory=CanonicalMappingDetails)


class LLMValidationResult(BaseModel):
    """Closed-set LLM validator result for one source field and candidate shortlist."""

    selected_target: str
    confidence: float
    reasoning: list[str] = Field(default_factory=list)
    transformation_code: str | None = None
    raw_response: str | None = None


class LLMDecisionProposition(BaseModel):
    """Structured explanation of how an LLM recommendation related to the final decision."""

    proposition_type: Literal["confirm", "challenge", "no_match"]
    proposed_target: str | None = None
    final_target: str | None = None
    confidence: float = 0.0
    reasoning: list[str] = Field(default_factory=list)
    considered_targets: list[str] = Field(default_factory=list)
    rejected_targets: list[str] = Field(default_factory=list)
    aligns_with_final: bool = False
    applied_to_final_decision: bool = False
    summary: str = ""


class MappingCandidate(BaseModel):
    """Selected mapping candidate outcome for one source field."""

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
    llm_decision_proposition: LLMDecisionProposition | None = None


class SourceMappingResult(BaseModel):
    """Ranked candidate set for one source field, including the selected choice."""

    source: str
    selected: MappingCandidate | None = None
    candidates: list[CandidateOption] = Field(default_factory=list)


class MappingDecision(BaseModel):
    """Persistable mapping decision chosen during review."""

    source: str
    target: str
    status: DecisionStatus = "accepted"
    resolution_type: MappingResolutionType = "direct_mapping"
    resolution_payload: dict[str, Any] = Field(default_factory=dict)
    transformation_code: str | None = None


class AutoMappingRequest(BaseModel):
    """Request payload for standard source-to-target auto-mapping."""

    source_dataset_id: str
    target_dataset_id: str
    use_llm: bool = True
    description_priority: bool = False
    source_system: str | None = None
    business_domain: str | None = None
    integration_name: str | None = None
    created_by: str | None = None
    workspace_id: str | None = None


TargetSystem = Literal["canonical", "sap"]


class TargetIntentOption(BaseModel):
    """One supported target-intent option exposed to workspace and mapping flows."""

    target_system: TargetSystem
    label: str
    description: str
    projection_mode: TargetProjectionMode
    artifact_type: CatalogArtifactType = "canonical-only"
    target_profile: str | None = None


class CanonicalMappingRequest(BaseModel):
    """Request payload for mapping a source dataset into the virtual canonical target."""

    source_dataset_id: str
    target_system: TargetSystem = "canonical"
    use_llm: bool = True
    description_priority: bool = False
    candidate_pool_size: int | None = Field(default=None, ge=1, le=25)
    source_system: str | None = None
    business_domain: str | None = None
    integration_name: str | None = None
    created_by: str | None = None
    workspace_id: str | None = None


class MappingRefinementRequest(BaseModel):
    """Request payload for re-ranking targets for one source field."""

    source_dataset_id: str
    source_field: str
    target_dataset_id: str | None = None
    target_system: TargetSystem | None = None
    candidate_targets: list[str] = Field(default_factory=list)
    use_llm: bool = True
    description_priority: bool = False
    candidate_pool_size: int | None = Field(default=None, ge=1, le=25)
    meaning_hint: str = ""
    negative_hint: str = ""
    sample_values: list[str] = Field(default_factory=list)
    refinement_instruction: str = ""
    source_system: str | None = None
    business_domain: str | None = None
    integration_name: str | None = None


class CanonicalCoverageColumnMatch(BaseModel):
    """Canonical concept matches attached to one schema column."""

    column: str
    concept_ids: list[str] = Field(default_factory=list)


class CanonicalCoverageSummary(BaseModel):
    """Coverage statistics for canonical resolution across one side of a mapping."""

    total_columns: int = 0
    matched_columns: int = 0
    coverage_ratio: float = 0.0
    unmatched_columns: list[str] = Field(default_factory=list)
    matched_columns_detail: list[CanonicalCoverageColumnMatch] = Field(default_factory=list)


class CanonicalCoverageProjectSummary(BaseModel):
    """Project-level canonical coverage summary across both source and target."""

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
    """Combined canonical coverage report for source, target, and project scopes."""

    source: CanonicalCoverageSummary = Field(default_factory=CanonicalCoverageSummary)
    target: CanonicalCoverageSummary = Field(default_factory=CanonicalCoverageSummary)
    project: CanonicalCoverageProjectSummary = Field(default_factory=CanonicalCoverageProjectSummary)


class MappingRuntimeFingerprint(BaseModel):
    """Runtime metadata describing the scoring code and settings used for one mapping run."""

    generated_at: str = ""
    app_version: str = ""
    scoring_profile: str = ""
    description_priority: bool = False
    code_fingerprint: str = ""
    target_system: str | None = None
    target_profile: str | None = None
    target_projection_mode: TargetProjectionMode = "dataset_to_dataset"


class AutoMappingResponse(BaseModel):
    """Response returned after generating ranked mapping candidates."""

    mappings: list[MappingCandidate] = Field(default_factory=list)
    ranked_mappings: list[SourceMappingResult] = Field(default_factory=list)
    canonical_coverage: CanonicalCoverageReport = Field(default_factory=CanonicalCoverageReport)
    applied_source_field_hints: list[dict[str, Any]] = Field(default_factory=list)
    mapping_runtime: MappingRuntimeFingerprint = Field(default_factory=MappingRuntimeFingerprint)


MappingAnalysisAudience = Literal["technical_implementor"]
MappingAnalysisOverallRisk = Literal["low", "medium", "high"]
MappingAnalysisCoverageStrength = Literal["low", "moderate", "strong"]
MappingAnalysisTransformationRisk = Literal["low", "medium", "high"]


class MappingAnalysisWorkspaceContext(BaseModel):
    """Workspace metadata used to contextualize mapping analysis generation."""

    mapping_mode: Literal["standard", "canonical"] = "standard"
    source_dataset_name: str = "Source dataset"
    target_dataset_name: str = "Target dataset"
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    integration_name: str | None = None


class MappingAnalysisOptions(BaseModel):
    """Options controlling how mapping analysis summaries are generated."""

    audience: MappingAnalysisAudience = "technical_implementor"
    include_narration_seed: bool = True


class MappingAnalysisRequest(BaseModel):
    """Request payload for generating a mapping-analysis summary."""

    mapping_response: AutoMappingResponse
    workspace: MappingAnalysisWorkspaceContext = Field(default_factory=MappingAnalysisWorkspaceContext)
    options: MappingAnalysisOptions = Field(default_factory=MappingAnalysisOptions)


class MappingAnalysisOverallMappingHealth(BaseModel):
    """Top-level health summary for the current mapping response."""

    summary: str = ""
    accepted_count: int = 0
    needs_review_count: int = 0
    rejected_count: int = 0
    unmatched_count: int = 0
    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0
    overall_risk: MappingAnalysisOverallRisk = "low"


class MappingAnalysisConfidenceDistribution(BaseModel):
    """Confidence-bucket distribution used in analysis summaries."""

    high_confidence_count: int = 0
    medium_confidence_count: int = 0
    low_confidence_count: int = 0
    high_confidence_ratio: float = 0.0
    medium_confidence_ratio: float = 0.0
    low_confidence_ratio: float = 0.0
    interpretation: str = ""


class MappingAnalysisStrongestMatch(BaseModel):
    """One standout high-confidence match highlighted in the analysis summary."""

    source: str
    target: str
    confidence: float = 0.0
    why_it_is_strong: str = ""
    supporting_signals: list[str] = Field(default_factory=list)
    canonical_path: str = ""


class MappingAnalysisNeedsReviewItem(BaseModel):
    """One highlighted review queue item from the mapping analysis summary."""

    source: str
    proposed_target: str = ""
    confidence: float = 0.0
    review_reason: str = ""
    competing_targets: list[str] = Field(default_factory=list)
    canonical_status: str = ""
    recommended_check: str = ""


class MappingAnalysisUnmatchedSource(BaseModel):
    """One unmatched source field highlighted by the analysis summary."""

    source: str
    reason: str = ""
    recommended_follow_up: str = ""


class MappingAnalysisCanonicalCoverageSummary(BaseModel):
    """Canonical coverage interpretation included in mapping analysis responses."""

    source_coverage: float = 0.0
    target_coverage: float = 0.0
    project_coverage: float = 0.0
    shared_concepts: list[str] = Field(default_factory=list)
    source_only_concepts: list[str] = Field(default_factory=list)
    target_only_concepts: list[str] = Field(default_factory=list)
    coverage_strength: MappingAnalysisCoverageStrength = "low"
    coverage_interpretation: str = ""


class MappingAnalysisTransformationHotspot(BaseModel):
    """One mapping row flagged as a transformation hotspot."""

    source: str
    target: str = ""
    transformation_required: bool = False
    transformation_risk: MappingAnalysisTransformationRisk = "low"
    reason: str = ""


class MappingAnalysisGenerationMetadata(BaseModel):
    """Generation metadata describing whether analysis used the LLM or fallback logic."""

    used_llm: bool = False
    fallback_used: bool = True
    llm_provider: str | None = None
    llm_model: str | None = None


class MappingAnalysisSummaryResponse(BaseModel):
    """Structured mapping-analysis overview returned to the UI."""

    title: str = ""
    audience: MappingAnalysisAudience = "technical_implementor"
    mapping_mode: Literal["standard", "canonical"] = "standard"
    overall_mapping_health: MappingAnalysisOverallMappingHealth = Field(
        default_factory=MappingAnalysisOverallMappingHealth
    )
    confidence_distribution: MappingAnalysisConfidenceDistribution = Field(
        default_factory=MappingAnalysisConfidenceDistribution
    )
    strongest_matches: list[MappingAnalysisStrongestMatch] = Field(default_factory=list)
    needs_review_items: list[MappingAnalysisNeedsReviewItem] = Field(default_factory=list)
    unmatched_sources: list[MappingAnalysisUnmatchedSource] = Field(default_factory=list)
    canonical_coverage_summary: MappingAnalysisCanonicalCoverageSummary = Field(
        default_factory=MappingAnalysisCanonicalCoverageSummary
    )
    transformation_hotspots: list[MappingAnalysisTransformationHotspot] = Field(default_factory=list)
    implementation_risks: list[str] = Field(default_factory=list)
    recommended_next_actions: list[str] = Field(default_factory=list)
    narration_script_seed: str = ""
    generation_metadata: MappingAnalysisGenerationMetadata = Field(default_factory=MappingAnalysisGenerationMetadata)


class MappingAnalysisNarrationRequest(BaseModel):
    """Request payload for turning an analysis summary into spoken narration."""

    summary: MappingAnalysisSummaryResponse


class MappingAnalysisNarrationResponse(BaseModel):
    """Narration payload generated from a mapping-analysis summary."""

    spoken_script: str = ""
    generation_metadata: MappingAnalysisGenerationMetadata = Field(default_factory=MappingAnalysisGenerationMetadata)


class MappingAnalysisAudioRequest(BaseModel):
    """Request payload for synthesizing audio from a spoken narration script."""

    spoken_script: str
    voice: str | None = None
    model: str | None = None


ReviewPlanPriority = Literal["high", "medium", "low"]
WorkspaceCopilotProblemDisposition = Literal["in_scope", "partial", "out_of_scope"]


class ReviewPlanGenerationMetadata(BaseModel):
    """Generation metadata describing whether the review plan used the LLM or fallback logic."""

    used_llm: bool = False
    fallback_used: bool = True
    llm_provider: str | None = None
    llm_model: str | None = None


class ReviewPlanCluster(BaseModel):
    """Cluster of related review items grouped into one suggested follow-up theme."""

    issue_type: str = ""
    focus: str = ""
    canonical_status: str = ""
    priority: ReviewPlanPriority = "medium"
    count: int = 0
    source_examples: list[str] = Field(default_factory=list)
    summary: str = ""
    recommended_follow_up: str = ""


class ReviewPlanRequest(BaseModel):
    """Request payload for generating a queue-level mapping review plan."""

    filtered_rows: list[dict[str, Any]] = Field(default_factory=list)
    attention_summary_rows: list[dict[str, Any]] = Field(default_factory=list)
    filters: dict[str, str] = Field(default_factory=dict)


class ReviewPlanResponse(BaseModel):
    """Structured queue-level review plan returned to the UI."""

    title: str = ""
    queue_summary: str = ""
    clusters: list[ReviewPlanCluster] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    generation_metadata: ReviewPlanGenerationMetadata = Field(default_factory=ReviewPlanGenerationMetadata)


class WorkspaceCopilotProblemGuidanceGenerationMetadata(BaseModel):
    """Generation metadata describing whether workspace problem guidance used the LLM or fallback logic."""

    used_llm: bool = False
    fallback_used: bool = True
    llm_provider: str | None = None
    llm_model: str | None = None


class WorkspaceCopilotProblemStatementRequest(BaseModel):
    """Request payload for turning a user-defined workspace problem into bounded app actions."""

    problem_statement: str
    workspace: MappingAnalysisWorkspaceContext = Field(default_factory=MappingAnalysisWorkspaceContext)
    capability_snapshot: dict[str, Any] = Field(default_factory=dict)


class WorkspaceCopilotProblemStatementResponse(BaseModel):
    """Structured bounded guidance for one user-defined workspace problem statement."""

    title: str = ""
    disposition: WorkspaceCopilotProblemDisposition = "partial"
    normalized_problem: str = ""
    scope_reason: str = ""
    answer: str = ""
    capability_hits: list[str] = Field(default_factory=list)
    recommended_sections: list[str] = Field(default_factory=list)
    recommended_steps: list[str] = Field(default_factory=list)
    prompt_template: str = ""
    input_format_fields: list[str] = Field(default_factory=list)
    generation_metadata: WorkspaceCopilotProblemGuidanceGenerationMetadata = Field(
        default_factory=WorkspaceCopilotProblemGuidanceGenerationMetadata
    )


MappingJobStatus = Literal["queued", "running", "cancel_requested", "completed", "failed", "canceled"]
MappingJobStorageMode = Literal["in_memory", "sqlite_status"]


class MappingJobStartResponse(BaseModel):
    """Response returned when a background mapping job is started."""

    job_id: str
    status: MappingJobStatus
    created_by: str | None = None
    workspace_id: str | None = None


class MappingJobStatusResponse(BaseModel):
    """Runtime status for one background mapping job."""

    job_id: str
    status: MappingJobStatus
    created_by: str | None = None
    workspace_id: str | None = None
    worker_id: str | None = None
    claimed_at: str | None = None
    heartbeat_at: str | None = None
    lease_expires_at: str | None = None
    recovery_signal: str | None = None
    activity: list[str] = Field(default_factory=list)
    response: AutoMappingResponse | None = None
    error: str | None = None


class MappingJobCancelRequest(BaseModel):
    """Optional caller context used to guard background job cancellation."""

    created_by: str | None = None
    workspace_id: str | None = None


class MappingJobRuntimeStatusResponse(BaseModel):
    """Aggregate runtime status for the mapping job subsystem."""

    storage_mode: MappingJobStorageMode = "in_memory"
    restart_safe: bool = False
    cross_process_safe: bool = False
    active_jobs: int = 0
    max_active_jobs: int = 0
    finished_jobs: int = 0
    max_finished_jobs: int = 0
    finished_job_ttl_seconds: int = 0
    oldest_active_job_age_seconds: int = 0
    durable_backend_recommended: bool = False
    durable_backend_triggers: list[str] = Field(default_factory=list)


CanonicalGapSuggestionAction = Literal["existing_concept_alias", "new_canonical_concept", "no_action"]
CanonicalGapDisposition = Literal["ignored", "rejected"]
CanonicalGapProposalState = Literal["new", "needs_review", "ready_for_approval"]


class CanonicalGapCandidate(BaseModel):
    """Mapping row that appears to need a new or expanded canonical concept path."""

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
    """Request payload for extracting canonical-gap candidates from a mapping response."""

    mapping_response: AutoMappingResponse
    min_confidence: float = 0.65


class CanonicalGapCandidatesResponse(BaseModel):
    """Response containing canonical-gap candidates extracted from a mapping response."""

    candidates: list[CanonicalGapCandidate] = Field(default_factory=list)


class CanonicalGapSuggestionRequest(BaseModel):
    """Request payload for generating a canonical-gap suggestion for one candidate."""

    candidate: CanonicalGapCandidate


class CanonicalGapSuggestion(BaseModel):
    """LLM-assisted suggestion describing how to resolve one canonical gap."""

    action: CanonicalGapSuggestionAction = "no_action"
    concept_id: str | None = None
    display_name: str | None = None
    aliases: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    reasoning: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    raw_response: str | None = None


class CanonicalGapApproveRequest(BaseModel):
    """Request payload for approving a canonical-gap suggestion into an overlay."""

    candidate: CanonicalGapCandidate
    suggestion: CanonicalGapSuggestion
    approved_by: str | None = None
    overlay_name: str | None = None


class CanonicalGapApproveResponse(BaseModel):
    """Response returned after persisting an approved canonical-gap overlay update."""

    overlay_id: int
    overlay_name: str
    saved_entry_count: int = 0
    activated: bool = True


class CanonicalGapRejectRequest(BaseModel):
    """Request payload for rejecting or ignoring a canonical-gap suggestion."""

    candidate: CanonicalGapCandidate
    suggestion: CanonicalGapSuggestion | None = None
    disposition: CanonicalGapDisposition = "rejected"
    rejected_by: str | None = None
    note: str | None = None


class CanonicalGapProposalStateRequest(BaseModel):
    """Request payload for persisting triage state on a canonical-gap candidate."""

    candidate_key: str
    candidate: CanonicalGapCandidate
    proposal_state: CanonicalGapProposalState = "new"
    reviewed_by: str | None = None
    note: str | None = None


class CanonicalGapProposalStateRecord(BaseModel):
    """Persisted triage state for one canonical-gap candidate."""

    candidate_key: str
    source: str
    target: str
    proposal_state: CanonicalGapProposalState = "new"
    reviewed_by: str | None = None
    note: str | None = None
    created_at: str | None = None


class CanonicalGapTriageGenerationMetadata(BaseModel):
    """Generation metadata describing whether canonical-gap triage used the LLM or fallback logic."""

    used_llm: bool = False
    fallback_used: bool = True
    llm_provider: str | None = None
    llm_model: str | None = None


class CanonicalGapTriageGroup(BaseModel):
    """Grouped canonical-gap queue family used in triage summaries."""

    priority: Literal["high", "medium", "low"] = "medium"
    focus: str = ""
    count: int = 0
    suggestion_action: str = ""
    proposal_state: str = ""
    source_examples: list[str] = Field(default_factory=list)
    summary: str = ""
    recommended_follow_up: str = ""


class CanonicalGapTriageSummaryRequest(BaseModel):
    """Request payload for generating a queue-level canonical-gap triage summary."""

    candidates: list[CanonicalGapCandidate] = Field(default_factory=list)
    suggestions: dict[str, CanonicalGapSuggestion] = Field(default_factory=dict)
    proposal_states: dict[str, CanonicalGapProposalState] = Field(default_factory=dict)


class CanonicalGapTriageSummaryResponse(BaseModel):
    """Structured summary of grouped canonical-gap review work."""

    title: str = ""
    summary: str = ""
    groups: list[CanonicalGapTriageGroup] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    generation_metadata: CanonicalGapTriageGenerationMetadata = Field(
        default_factory=CanonicalGapTriageGenerationMetadata
    )


class DecisionLogEntry(BaseModel):
    """Observed decision log entry capturing heuristics, LLM output, and the final choice."""

    source: str
    created_by: str | None = None
    workspace_id: str | None = None
    candidate_targets: list[str] = Field(default_factory=list)
    heuristic_scores: dict[str, float] = Field(default_factory=dict)
    llm_result: LLMValidationResult | None = None
    final_target: str | None = None
    final_status: DecisionStatus = "needs_review"
    used_llm: bool = False


class UserCorrectionEntry(BaseModel):
    """Persisted user correction captured from review feedback."""

    correction_id: int | None = None
    source: str
    suggested_target: str | None = None
    corrected_target: str | None = None
    status: UserCorrectionStatus = "overridden"
    note: str | None = None
    version: int = 1
    created_at: str | None = None


class CorrectionRuleCandidate(BaseModel):
    """Suggested reusable correction rule mined from repeated feedback."""

    source: str
    suggested_target: str | None = None
    corrected_target: str | None = None
    status: UserCorrectionStatus
    occurrence_count: int = 0
    recommendation: str
    already_promoted: bool = False
    promoted_rule_id: int | None = None


class ReusableCorrectionRule(BaseModel):
    """Promoted correction rule that can be reused in future mapping runs."""

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
    """Request payload used to promote a mined correction rule into active reuse."""

    source: str
    suggested_target: str | None = None
    corrected_target: str | None = None
    status: ReusableCorrectionRuleStatus
    occurrence_count: int = 0
    created_by: str | None = None
    note: str | None = None


class MappingSetCreateRequest(BaseModel):
    """Request payload for saving the current workspace as a governed mapping set."""

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
    workspace_id: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None


class MappingSetRecord(BaseModel):
    """Summary record for one persisted versioned mapping set."""

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
    workspace_id: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None
    created_at: str | None = None


class MappingSetDetail(MappingSetRecord):
    """Expanded mapping-set record including the full mapping decisions."""

    mapping_decisions: list[MappingDecision] = Field(default_factory=list)


class DraftSessionEditorEntry(BaseModel):
    """Minimal durable workspace editor state needed to resume review and decisions."""

    target: str = ""
    status: DecisionStatus = "needs_review"
    resolution_type: MappingResolutionType = "direct_mapping"
    resolution_payload: dict[str, Any] = Field(default_factory=dict)
    suggested_target: str = ""
    suggested_transformation_code: str = ""
    manual_transformation_code: str = ""
    llm_transformation_instruction: str = ""
    manual_apply_transformation: bool = False
    manual: bool = False


class DraftSessionDecisionAuditEntry(BaseModel):
    """Durable decision-audit metadata attached to one source field in a draft session."""

    origin: str = "manual_or_imported"
    applied_at: str = ""
    created_by: str | None = None
    workspace_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class DraftSessionTargetContext(BaseModel):
    """Stable target/projection context needed to resume the same workspace intent later."""

    target_system: str | None = None
    target_profile: str | None = None
    target_projection_mode: TargetProjectionMode = "dataset_to_dataset"
    artifact_type: CatalogArtifactType = "standard"


class DraftSessionReviewState(BaseModel):
    """Minimal durable review-state snapshot that can be safely restored across sessions."""

    status_filter: str = "All"
    confidence_filter: str = "All"
    source_filter: str = "All"
    canonical_concept_filter: str = "All"


class DraftSessionOutputState(BaseModel):
    """Bounded output snapshot that can be safely resumed without re-running generation."""

    preview_response: dict[str, Any] = Field(default_factory=dict)
    codegen_response: dict[str, Any] = Field(default_factory=dict)
    codegen_refinement_response: dict[str, Any] = Field(default_factory=dict)
    mapping_analysis_summary: dict[str, Any] = Field(default_factory=dict)
    mapping_analysis_spoken_script: str = ""


class DraftSessionCreateRequest(BaseModel):
    """Request payload for saving one durable draft workspace session snapshot."""

    name: str
    created_by: str | None = None
    workspace_id: str | None = None
    api_base_url: str = ""
    mapping_mode: WorkspaceMappingMode = "standard"
    active_workspace_section: WorkspaceSection = "Review"
    source_handle: DatasetHandle
    target_handle: DatasetHandle | None = None
    canonical_target_system: str | None = None
    workspace_target_context: DraftSessionTargetContext = Field(default_factory=DraftSessionTargetContext)
    review_state: DraftSessionReviewState = Field(default_factory=DraftSessionReviewState)
    mapping_runtime: MappingRuntimeFingerprint = Field(default_factory=MappingRuntimeFingerprint)
    mapping_editor_state: dict[str, DraftSessionEditorEntry] = Field(default_factory=dict)
    mapping_decision_audit: dict[str, DraftSessionDecisionAuditEntry] = Field(default_factory=dict)
    transformation_spec: dict[str, Any] = Field(default_factory=dict)
    output_state: DraftSessionOutputState = Field(default_factory=DraftSessionOutputState)


class DraftSessionUpdateRequest(DraftSessionCreateRequest):
    """Request payload for updating one durable draft workspace snapshot."""

    expected_version: int = Field(..., ge=1)
    last_writer: str | None = None


class DraftSessionDecisionStateUpdateRequest(BaseModel):
    """Request payload for persisting durable decision state against an existing draft session."""

    created_by: str | None = None
    workspace_id: str | None = None
    expected_version: int = Field(..., ge=1)
    last_writer: str | None = None
    active_workspace_section: WorkspaceSection = "Decisions"
    mapping_editor_state: dict[str, DraftSessionEditorEntry] = Field(default_factory=dict)
    mapping_decision_audit: dict[str, DraftSessionDecisionAuditEntry] = Field(default_factory=dict)
    transformation_spec: dict[str, Any] = Field(default_factory=dict)
    output_state: DraftSessionOutputState = Field(default_factory=DraftSessionOutputState)


class DraftSessionReviewStateUpdateRequest(BaseModel):
    """Request payload for persisting durable review-state filters against an existing draft session."""

    created_by: str | None = None
    workspace_id: str | None = None
    expected_version: int = Field(..., ge=1)
    last_writer: str | None = None
    active_workspace_section: WorkspaceSection = "Review"
    review_state: DraftSessionReviewState = Field(default_factory=DraftSessionReviewState)


class DraftSessionRecord(BaseModel):
    """Summary record for one saved draft workspace session."""

    draft_session_id: int
    name: str
    created_by: str | None = None
    workspace_id: str | None = None
    api_base_url: str = ""
    mapping_mode: WorkspaceMappingMode = "standard"
    active_workspace_section: WorkspaceSection = "Review"
    source_dataset_name: str = ""
    target_dataset_name: str = ""
    canonical_target_system: str | None = None
    workspace_target_context: DraftSessionTargetContext = Field(default_factory=DraftSessionTargetContext)
    review_state: DraftSessionReviewState = Field(default_factory=DraftSessionReviewState)
    decision_count: int = 0
    version: int = 1
    last_writer: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DraftSessionDetail(DraftSessionRecord):
    """Expanded draft session record including the persisted restore payload."""

    source_handle: DatasetHandle
    target_handle: DatasetHandle | None = None
    mapping_runtime: MappingRuntimeFingerprint = Field(default_factory=MappingRuntimeFingerprint)
    mapping_editor_state: dict[str, DraftSessionEditorEntry] = Field(default_factory=dict)
    mapping_decision_audit: dict[str, DraftSessionDecisionAuditEntry] = Field(default_factory=dict)
    transformation_spec: dict[str, Any] = Field(default_factory=dict)
    output_state: DraftSessionOutputState = Field(default_factory=DraftSessionOutputState)


class CatalogIntegrationRecord(BaseModel):
    """Catalog summary record for one saved integration version."""

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
    workspace_id: str | None = None
    owner: str | None = None
    assignee: str | None = None
    created_at: str | None = None


class CatalogIntegrationDetail(BaseModel):
    """Detailed catalog view for one integration across versions and similar assets."""

    integration_name: str
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    interface_type: str | None = None
    description: str | None = None
    canonical_concepts: list[str] = Field(default_factory=list)
    unmatched_sources: list[str] = Field(default_factory=list)
    workspace_id: str | None = None
    latest_version: CatalogIntegrationRecord
    latest_approved_version: CatalogIntegrationRecord | None = None
    versions: list[CatalogIntegrationRecord] = Field(default_factory=list)
    similar_integrations: list["CatalogSimilarIntegrationRecord"] = Field(default_factory=list)


class CatalogSimilarIntegrationRecord(BaseModel):
    """Catalog record describing one integration that is similar to another."""

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
    """Catalog usage record showing where one canonical concept appears."""

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
    """Detail response for one catalog concept and its integration usage."""

    concept_id: str
    usage_count: int = 0
    integrations: list[CatalogConceptUsageRecord] = Field(default_factory=list)


CatalogReuseFitAssessment = Literal["strong_fit", "partial_fit", "low_fit"]


class CatalogReuseFitGenerationMetadata(BaseModel):
    """Generation metadata describing whether reuse-fit analysis used the LLM or fallback logic."""

    used_llm: bool = False
    fallback_used: bool = True
    llm_provider: str | None = None
    llm_model: str | None = None


class CatalogReuseFitWorkspaceContext(BaseModel):
    """Current workspace context used to assess catalog reuse fit."""

    workspace_loaded: bool = False
    mapping_mode: str = ""
    source_dataset_name: str = ""
    target_dataset_name: str = ""
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    current_decision_count: int = 0
    current_status_counts: dict[str, int] = Field(default_factory=dict)
    current_shared_concepts: list[str] = Field(default_factory=list)
    current_unmatched_sources: list[str] = Field(default_factory=list)
    current_concept_count: int = 0


class CatalogReuseFitRequest(BaseModel):
    """Request payload for evaluating how well a catalog asset fits the current workspace."""

    mapping_set_detail: MappingSetDetail
    workspace_context: CatalogReuseFitWorkspaceContext = Field(default_factory=CatalogReuseFitWorkspaceContext)


class CatalogReuseFitResponse(BaseModel):
    """Structured reuse-fit assessment returned for a selected catalog mapping set."""

    title: str = ""
    fit_assessment: CatalogReuseFitAssessment = "partial_fit"
    summary: str = ""
    key_matches: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    generation_metadata: CatalogReuseFitGenerationMetadata = Field(default_factory=CatalogReuseFitGenerationMetadata)


class CatalogIntegrationCompareRequest(BaseModel):
    """Request payload for comparing two catalog integrations."""

    base_integration_name: str
    peer_integration_name: str


class CatalogIntegrationCompareResponse(BaseModel):
    """Deterministic compare summary between two catalog integrations."""

    base_integration: CatalogIntegrationDetail
    peer_integration: CatalogIntegrationDetail
    shared_concepts: list[str] = Field(default_factory=list)
    base_only_concepts: list[str] = Field(default_factory=list)
    peer_only_concepts: list[str] = Field(default_factory=list)
    same_source_system: bool = False
    same_target_system: bool = False
    same_business_domain: bool = False
    same_artifact_type: bool = False
    compare_summary: str = ""
    suggested_next_actions: list[str] = Field(default_factory=list)


class CatalogWorkspaceReuseShortlistRequest(BaseModel):
    """Request payload for ranking catalog reuse candidates against workspace context."""

    workspace_context: CatalogReuseFitWorkspaceContext = Field(default_factory=CatalogReuseFitWorkspaceContext)
    top_n: int = Field(default=5, ge=1, le=25)


class CatalogWorkspaceReuseCandidate(BaseModel):
    """One ranked catalog reuse candidate for the current workspace snapshot."""

    integration_name: str
    mapping_set_id: int
    version: int
    status: MappingSetStatus = "approved"
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    artifact_type: CatalogArtifactType = "standard"
    score: float = 0.0
    concept_overlap_score: float = 0.0
    system_match_score: float = 0.0
    domain_match_score: float = 0.0
    accepted_quality_score: float = 0.0
    shared_concepts: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class CatalogWorkspaceReuseShortlistResponse(BaseModel):
    """Ranked shortlist for workspace-aware catalog reuse discovery."""

    workspace_loaded: bool = False
    considered_integrations: int = 0
    candidates: list[CatalogWorkspaceReuseCandidate] = Field(default_factory=list)


class CatalogFieldReuseSelection(BaseModel):
    """One selected workspace field used for field-scoped Catalog reuse discovery."""

    source_field: str
    current_target: str | None = None
    current_status: DecisionStatus | None = None


class CatalogFieldReuseMatch(BaseModel):
    """One saved mapping decision that overlaps a selected workspace source field."""

    source_field: str
    target: str | None = None
    status: DecisionStatus = "needs_review"
    transformation_present: bool = False
    current_target_match: bool = False


class CatalogFieldReuseShortlistRequest(BaseModel):
    """Request payload for ranking catalog candidates against selected workspace fields."""

    workspace_context: CatalogReuseFitWorkspaceContext = Field(default_factory=CatalogReuseFitWorkspaceContext)
    selected_fields: list[CatalogFieldReuseSelection] = Field(default_factory=list)
    top_n: int = Field(default=5, ge=1, le=25)


class CatalogFieldReuseCandidate(BaseModel):
    """One ranked Catalog candidate for field-scoped reuse discovery."""

    integration_name: str
    mapping_set_id: int
    version: int
    status: MappingSetStatus = "approved"
    source_system: str | None = None
    target_system: str | None = None
    business_domain: str | None = None
    artifact_type: CatalogArtifactType = "standard"
    score: float = 0.0
    matched_field_count: int = 0
    selected_field_count: int = 0
    source_field_overlap_score: float = 0.0
    current_target_match_score: float = 0.0
    system_match_score: float = 0.0
    domain_match_score: float = 0.0
    accepted_quality_score: float = 0.0
    matched_fields: list[CatalogFieldReuseMatch] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class CatalogFieldReuseShortlistResponse(BaseModel):
    """Ranked shortlist for field-scoped Catalog reuse discovery."""

    workspace_loaded: bool = False
    selected_field_count: int = 0
    considered_integrations: int = 0
    candidates: list[CatalogFieldReuseCandidate] = Field(default_factory=list)


class MappingSetStatusUpdateRequest(BaseModel):
    """Request payload for changing mapping-set governance status or ownership metadata."""

    status: MappingSetStatus
    changed_by: str | None = None
    note: str | None = None
    owner: str | None = None
    assignee: str | None = None
    review_note: str | None = None


class MappingSetApplyRequest(BaseModel):
    """Request payload for marking a mapping set as applied in workspace flows."""

    changed_by: str | None = None
    workspace_id: str | None = None
    note: str | None = None


class MappingSetAuditEntry(BaseModel):
    """Audit log entry describing one mapping-set lifecycle action."""

    audit_id: int | None = None
    mapping_set_id: int
    mapping_set_name: str
    version: int
    action: str
    status: MappingSetStatus
    changed_by: str | None = None
    workspace_id: str | None = None
    note: str | None = None
    created_at: str | None = None


class MappingSetDecisionDiffEntry(BaseModel):
    """One row-level change between two mapping-set versions."""

    change_type: Literal["added", "removed", "changed"]
    source: str
    from_target: str | None = None
    to_target: str | None = None
    from_status: DecisionStatus | None = None
    to_status: DecisionStatus | None = None
    from_transformation_code: str | None = None
    to_transformation_code: str | None = None


class MappingSetDiffResponse(BaseModel):
    """Diff summary comparing one mapping-set version against another."""

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
    """Admin-facing runtime configuration snapshot for backend observability."""

    app_version: str = ""
    backend_build: str = ""
    llm_provider: str
    llm_model: str
    llm_timeout_seconds: float
    lmstudio_base_url: str
    tts_provider: str = "none"
    tts_timeout_seconds: float = 0.0
    lmstudio_tts_base_url: str = ""
    lmstudio_orpheus_model: str = ""
    lmstudio_orpheus_voice: str = ""
    dbt_materialization: str = "view"
    dbt_source_mode: str = "ref"
    dbt_source_name: str = "raw"
    dbt_source_table_name: str = "source_model"
    dbt_ref_name: str = "source_model"
    dbt_quote_identifiers: bool = True
    dbt_source_cte_name: str = "source_data"
    dbt_source_reference: str = "{{ ref('source_model') }}"
    scoring_profile: str = "balanced"
    available_scoring_profiles: list[str] = Field(default_factory=list)
    llm_status: str = "configured"
    llm_reachable: bool | None = None
    llm_status_detail: str = ""
    llm_resolved_model: str = ""
    tts_status: str = "configured"
    tts_reachable: bool | None = None
    tts_status_detail: str = ""
    embedding_provider: str
    cors_origins: list[str] = Field(default_factory=list)
    sqlite_path: str
    llm_gate_min_score: float
    llm_gate_max_score: float
    admin_api_token_configured: bool = False


class ScoringProfileUpdateRequest(BaseModel):
    """Request payload for switching the active runtime scoring profile."""

    scoring_profile: str


class BenchmarkDatasetCreateRequest(BaseModel):
    """Request payload for saving a reusable benchmark dataset."""

    name: str
    cases: list[dict[str, Any]] = Field(default_factory=list)
    created_by: str | None = None
    workspace_id: str | None = None


class BenchmarkDatasetRecord(BaseModel):
    """Summary record for one saved benchmark dataset."""

    dataset_id: int
    name: str
    case_count: int
    version: int = 1
    created_by: str | None = None
    workspace_id: str | None = None
    created_at: str | None = None


class EvaluationMetrics(BaseModel):
    """Accuracy metrics produced by benchmark evaluation runs."""

    total_cases: int
    total_fields: int
    correct_matches: int
    top1_accuracy: float
    accuracy: float
    confidence_by_bucket: dict[str, float] = Field(default_factory=dict)


class ScoringProfileMetrics(BaseModel):
    """Evaluation metrics for one scoring profile in a profile comparison."""

    profile: str
    total_cases: int
    total_fields: int
    correct_matches: int
    top1_accuracy: float
    accuracy: float
    confidence_by_bucket: dict[str, float] = Field(default_factory=dict)


class ScoringProfileComparisonResponse(BaseModel):
    """Comparison response for multiple scoring profiles on the same benchmark set."""

    profiles: list[ScoringProfileMetrics] = Field(default_factory=list)
    recommended_profile: str | None = None
    recommendation_reason: str = ""


class CorrectionImpactMetrics(BaseModel):
    """Benchmark metrics comparing baseline and correction-aware evaluation modes."""

    baseline: EvaluationMetrics
    correction_aware: EvaluationMetrics
    accuracy_delta: float = 0.0
    top1_accuracy_delta: float = 0.0
    correct_matches_delta: int = 0


class BenchmarkExplanationGenerationMetadata(BaseModel):
    """Generation metadata describing whether benchmark explanation used the LLM or fallback logic."""

    used_llm: bool = False
    fallback_used: bool = True
    llm_provider: str | None = None
    llm_model: str | None = None


class BenchmarkExplanationRequest(BaseModel):
    """Request payload for generating a narrative explanation of benchmark results."""

    dataset_name: str = ""
    benchmark_result: EvaluationMetrics | None = None
    correction_impact: CorrectionImpactMetrics | None = None
    profile_comparison: ScoringProfileComparisonResponse | None = None


class BenchmarkExplanationResponse(BaseModel):
    """Structured explanation of benchmark findings, risks, and next actions."""

    title: str = ""
    summary: str = ""
    key_findings: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    generation_metadata: BenchmarkExplanationGenerationMetadata = Field(
        default_factory=BenchmarkExplanationGenerationMetadata
    )


class EvaluationRunRecord(BaseModel):
    """Persisted record of one executed benchmark run."""

    run_id: int
    dataset_id: int | None = None
    dataset_name: str | None = None
    provider_name: str = "none"
    created_by: str | None = None
    workspace_id: str | None = None
    total_cases: int
    total_fields: int
    correct_matches: int
    top1_accuracy: float
    accuracy: float
    confidence_by_bucket: dict[str, float] = Field(default_factory=dict)
    created_at: str | None = None


class EvaluationRunRequest(BaseModel):
    """Request payload for running an ad hoc evaluation benchmark."""

    cases: list[dict[str, Any]] = Field(default_factory=list)


class TransformationSpecFieldRule(BaseModel):
    """One field-level rule inside a structured transformation design spec."""

    target_field: str
    rule: str = ""
    source_fields: list[str] = Field(default_factory=list)


class TransformationSpec(BaseModel):
    """Structured, reviewable transformation design contract used ahead of preview/codegen."""

    target_grain: str = ""
    global_rules: str = ""
    defaults: str = ""
    examples: str = ""
    target_fields: list[str] = Field(default_factory=list)
    field_rules: list[TransformationSpecFieldRule] = Field(default_factory=list)


class TransformationSpecSummary(BaseModel):
    """Compact validation summary for a transformation design spec against active targets."""

    state: TransformationSpecState = "invalid"
    title: str = ""
    message: str = ""
    target_count: int = 0
    described_count: int = 0
    missing_fields: list[str] = Field(default_factory=list)


class PreviewRequest(BaseModel):
    """Request payload for previewing mapping decisions against uploaded source rows."""

    source_dataset_id: str
    source_preview_rows: list[dict[str, Any]] | None = None
    mapping_decisions: list[MappingDecision]
    transformation_spec: TransformationSpec | None = None


class PreviewRow(BaseModel):
    """One preview output row together with any row-level warnings."""

    values: dict[str, Any]
    warnings: list[str] = Field(default_factory=list)


class TransformationPreviewWarning(BaseModel):
    """Structured warning emitted while previewing or generating transformations."""

    code: TransformationWarningCode
    message: str
    source: str | None = None
    target: str | None = None
    stage: TransformationIssueStage = "preview"
    severity: TransformationIssueSeverity = "warning"
    fallback_applied: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class TransformationPreviewResult(BaseModel):
    """Per-mapping transformation preview result including samples and warnings."""

    source: str
    target: str
    mode: TransformationPreviewMode = "direct"
    status: TransformationPreviewStatus = "direct"
    classification: TransformationPreviewClassification = "direct"
    before_samples: list[str] = Field(default_factory=list)
    after_samples: list[str] = Field(default_factory=list)
    warnings: list[TransformationPreviewWarning] = Field(default_factory=list)
    spec_rule: str = ""
    spec_source_fields: list[str] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    """Preview response including output rows, unresolved targets, and transformation results."""

    preview: list[PreviewRow] = Field(default_factory=list)
    unresolved_targets: list[str] = Field(default_factory=list)
    transformation_previews: list[TransformationPreviewResult] = Field(default_factory=list)
    transformation_spec_summary: TransformationSpecSummary | None = None


class TransformationTestAssertion(BaseModel):
    """Assertion describing expected transformation preview behavior for one target."""

    target: str
    expected_status: TransformationPreviewStatus | None = None
    expected_classification: TransformationPreviewClassification | None = None
    expected_warning_codes: list[TransformationWarningCode] | None = None
    expected_output_values: list[str] | None = None


class TransformationTestCase(BaseModel):
    """Transformation test case containing source rows and expected assertions."""

    case_name: str
    source_rows: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[TransformationTestAssertion] = Field(default_factory=list)


class TransformationTestSetCreateRequest(BaseModel):
    """Request payload for saving a reusable transformation test set."""

    name: str
    mapping_decisions: list[MappingDecision] = Field(default_factory=list)
    cases: list[TransformationTestCase] = Field(default_factory=list)


class TransformationTestSetRecord(BaseModel):
    """Summary record for one saved transformation test set."""

    test_set_id: int
    name: str
    mapping_count: int
    case_count: int
    version: int = 1
    created_at: str | None = None


class TransformationTestSetDetail(TransformationTestSetRecord):
    """Expanded transformation test set including mapping decisions and test cases."""

    mapping_decisions: list[MappingDecision] = Field(default_factory=list)
    cases: list[TransformationTestCase] = Field(default_factory=list)


class TransformationTestCaseResult(BaseModel):
    """Execution result for one transformation test case."""

    case_name: str
    passed: bool
    failures: list[str] = Field(default_factory=list)
    preview: list[PreviewRow] = Field(default_factory=list)
    transformation_previews: list[TransformationPreviewResult] = Field(default_factory=list)


class TransformationTestSetRunResponse(BaseModel):
    """Aggregate execution response for a saved transformation test set."""

    test_set_id: int
    name: str
    passed: bool
    total_cases: int
    passed_cases: int
    case_results: list[TransformationTestCaseResult] = Field(default_factory=list)


class CodegenRequest(BaseModel):
    """Request payload for generating Pandas, PySpark, or dbt mapping code."""

    mapping_decisions: list[MappingDecision]
    mode: CodegenMode = "pandas"
    allow_unaccepted: bool = False
    transformation_spec: TransformationSpec | None = None


class GeneratedArtifact(BaseModel):
    """Generated code artifact returned from a mapping codegen request."""

    language: Literal["python-pandas", "python-pyspark", "sql-dbt"] = "python-pandas"
    code: str
    warnings: list[TransformationPreviewWarning] = Field(default_factory=list)
    transformation_spec_summary: TransformationSpecSummary | None = None


class ArtifactRefinementRequest(BaseModel):
    """Request payload for refining an already generated code artifact."""

    mapping_decisions: list[MappingDecision] = Field(default_factory=list)
    mode: CodegenMode = "pandas"
    allow_unaccepted: bool = False
    current_code: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    edge_cases: str = ""
    reference_excerpt: str = ""


class ArtifactRefinementResponse(BaseModel):
    """Response containing refined code, reasoning, and warnings from artifact refinement."""

    language: Literal["python-pandas", "python-pyspark", "sql-dbt"]
    code: str
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TransformationGenerationRequest(BaseModel):
    """Request payload for generating a transformation for one source-target column pair."""

    source_dataset_id: str
    target_dataset_id: str
    source_column: str
    target_column: str
    instruction: str = Field(min_length=1)


class TransformationGenerationResponse(BaseModel):
    """Response containing generated transformation code plus reasoning and warnings."""

    transformation_code: str
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TransformationSpecProposalRequest(BaseModel):
    """Request payload for bounded natural-language to structured transformation spec proposals."""

    mapping_decisions: list[MappingDecision] = Field(default_factory=list)
    instruction: str = Field(min_length=1)
    current_spec: TransformationSpec | None = None


class TransformationSpecProposalResponse(BaseModel):
    """Structured transformation spec proposal returned by the bounded LLM helper."""

    transformation_spec: TransformationSpec
    summary: TransformationSpecSummary
    reasoning: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TransformationTemplate(BaseModel):
    """Reusable transformation template exposed to the Streamlit editor."""

    template_id: str
    name: str
    description: str
    code_template: str
