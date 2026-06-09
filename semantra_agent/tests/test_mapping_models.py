"""Unit tests for semantra_core.models.mapping.

Covers the scoring, candidate, and request/response models used by mapping
flows: ``ScoringSignals``, ``CandidateOption``, ``MappingCandidate``,
``MappingDecision``, ``AutoMappingRequest``, ``MappingRefinementRequest``,
``AutoMappingResponse``, ``MappingAnalysisRequest``, and the canonical
coverage reporting models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from semantra_core.models.mapping import (
    AutoMappingRequest,
    AutoMappingResponse,
    CanonicalCoverageColumnMatch,
    CanonicalCoverageProjectSummary,
    CanonicalCoverageReport,
    CanonicalCoverageSummary,
    CanonicalMappingDetails,
    CanonicalMappingRequest,
    CandidateOption,
    LLMDecisionProposition,
    LLMValidationResult,
    MappingAnalysisAudience,
    MappingAnalysisConfidenceDistribution,
    MappingAnalysisGenerationMetadata,
    MappingAnalysisNarrationRequest,
    MappingAnalysisNarrationResponse,
    MappingAnalysisOptions,
    MappingAnalysisOverallMappingHealth,
    MappingAnalysisRequest,
    MappingAnalysisStrongestMatch,
    MappingAnalysisSummaryResponse,
    MappingAnalysisTransformationHotspot,
    MappingAnalysisUnmatchedSource,
    MappingAnalysisWorkspaceContext,
    MappingCandidate,
    MappingDecision,
    MappingRefinementRequest,
    MappingRuntimeFingerprint,
    ScoringSignals,
    SourceMappingResult,
    TargetIntentOption,
)


# ---------------------------------------------------------------------------
# ScoringSignals
# ---------------------------------------------------------------------------


def test_scoring_signals_all_zero_by_default() -> None:
    """Every signal in ScoringSignals should default to 0.0."""
    signals = ScoringSignals()
    assert signals.name == 0.0
    assert signals.semantic == 0.0
    assert signals.knowledge == 0.0
    assert signals.canonical == 0.0
    assert signals.pattern == 0.0
    assert signals.statistical == 0.0
    assert signals.overlap == 0.0
    assert signals.embedding == 0.0
    assert signals.correction == 0.0
    assert signals.llm == 0.0


def test_scoring_signals_round_trip_custom_values() -> None:
    """Custom signal values should round-trip without modification."""
    signals = ScoringSignals(name=0.5, semantic=0.7, llm=0.9)
    assert signals.name == 0.5
    assert signals.semantic == 0.7
    assert signals.llm == 0.9


# ---------------------------------------------------------------------------
# CandidateOption
# ---------------------------------------------------------------------------


def test_candidate_option_defaults() -> None:
    """CandidateOption should default explanation and canonical_details."""
    candidate = CandidateOption(
        target="user_id",
        confidence=0.8,
        confidence_label="high_confidence",
        method="name",
        signals=ScoringSignals(name=0.9),
    )
    assert candidate.explanation == []
    assert isinstance(candidate.canonical_details, CanonicalMappingDetails)
    assert candidate.canonical_details.source_concepts == []


def test_candidate_option_rejects_invalid_confidence_label() -> None:
    """confidence_label must validate against the ConfidenceLabel literal."""
    with pytest.raises(ValidationError):
        CandidateOption(
            target="x",
            confidence=0.0,
            confidence_label="super_high",  # type: ignore[arg-type]
            method="name",
            signals=ScoringSignals(),
        )


# ---------------------------------------------------------------------------
# LLMValidationResult / LLMDecisionProposition
# ---------------------------------------------------------------------------


def test_llm_validation_result_optional_fields() -> None:
    """transformation_code and raw_response should be optional and default to None."""
    result = LLMValidationResult(selected_target="x", confidence=0.5)
    assert result.transformation_code is None
    assert result.raw_response is None
    assert result.reasoning == []


def test_llm_decision_proposition_defaults() -> None:
    """LLMDecisionProposition should expose well-formed defaults."""
    prop = LLMDecisionProposition(proposition_type="confirm")
    assert prop.proposed_target is None
    assert prop.final_target is None
    assert prop.confidence == 0.0
    assert prop.aligns_with_final is False
    assert prop.applied_to_final_decision is False


def test_llm_decision_proposition_rejects_invalid_proposition_type() -> None:
    """proposition_type must validate against the literal set."""
    with pytest.raises(ValidationError):
        LLMDecisionProposition(proposition_type="agree")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# MappingCandidate
# ---------------------------------------------------------------------------


def test_mapping_target_optional_for_unmatched() -> None:
    """A MappingCandidate with no target should represent an unmatched field."""
    candidate = MappingCandidate(
        source="unknown_field",
        target=None,
        confidence=0.0,
        confidence_label="low_confidence",
        status="rejected",
        method="none",
        signals=ScoringSignals(),
    )
    assert candidate.target is None
    assert candidate.llm_consulted is False
    assert candidate.llm_recommendation is None
    assert candidate.llm_decision_proposition is None


def test_mapping_candidate_with_llm_payload_round_trip() -> None:
    """LLM payload fields should round-trip exactly when supplied."""
    candidate = MappingCandidate(
        source="email",
        target="email_address",
        confidence=0.7,
        confidence_label="medium_confidence",
        status="needs_review",
        method="llm",
        signals=ScoringSignals(llm=0.7),
        llm_consulted=True,
        llm_recommendation=LLMValidationResult(
            selected_target="email_address", confidence=0.7
        ),
        llm_decision_proposition=LLMDecisionProposition(
            proposition_type="confirm", proposed_target="email_address"
        ),
    )
    assert candidate.llm_consulted is True
    assert candidate.llm_recommendation is not None
    assert candidate.llm_recommendation.selected_target == "email_address"
    assert candidate.llm_decision_proposition is not None
    assert candidate.llm_decision_proposition.proposed_target == "email_address"


# ---------------------------------------------------------------------------
# SourceMappingResult
# ---------------------------------------------------------------------------


def test_source_mapping_result_selected_optional() -> None:
    """A SourceMappingResult should be valid even without a selected candidate."""
    result = SourceMappingResult(source="x", selected=None, candidates=[])
    assert result.selected is None
    assert result.candidates == []


# ---------------------------------------------------------------------------
# MappingDecision
# ---------------------------------------------------------------------------


def test_mapping_decision_defaults() -> None:
    """MappingDecision should default to accepted/direct_mapping with empty payload."""
    decision = MappingDecision(source="email", target="email_address")
    assert decision.status == "accepted"
    assert decision.resolution_type == "direct_mapping"
    assert decision.resolution_payload == {}
    assert decision.transformation_code is None


def test_mapping_decision_rejects_invalid_resolution_type() -> None:
    """resolution_type must validate against the MappingResolutionType literal."""
    with pytest.raises(ValidationError):
        MappingDecision(
            source="x",
            target="y",
            resolution_type="magic",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Request payloads
# ---------------------------------------------------------------------------


def test_auto_mapping_request_minimal_required_fields() -> None:
    """AutoMappingRequest should be constructible from the minimum required fields."""
    request = AutoMappingRequest(
        source_dataset_id="src", target_dataset_id="tgt"
    )
    assert request.use_llm is True
    assert request.description_priority is False
    assert request.source_system is None
    assert request.workspace_id is None


def test_auto_mapping_request_rejects_missing_dataset_ids() -> None:
    """Source and target dataset ids are required."""
    with pytest.raises(ValidationError):
        AutoMappingRequest()  # type: ignore[call-arg]


def test_canonical_mapping_request_default_target_system() -> None:
    """CanonicalMappingRequest should default target_system to 'canonical'."""
    request = CanonicalMappingRequest(source_dataset_id="src")
    assert request.target_system == "canonical"
    assert request.use_llm is True


def test_canonical_mapping_request_candidate_pool_size_bounds() -> None:
    """candidate_pool_size must be within [1, 25] per the ge/le constraints."""
    CanonicalMappingRequest(source_dataset_id="x", candidate_pool_size=1)
    CanonicalMappingRequest(source_dataset_id="x", candidate_pool_size=25)

    with pytest.raises(ValidationError):
        CanonicalMappingRequest(source_dataset_id="x", candidate_pool_size=0)
    with pytest.raises(ValidationError):
        CanonicalMappingRequest(source_dataset_id="x", candidate_pool_size=26)


def test_mapping_refinement_request_defaults() -> None:
    """MappingRefinementRequest should default all optional text fields to ''."""
    request = MappingRefinementRequest(
        source_dataset_id="x", source_field="email"
    )
    assert request.meaning_hint == ""
    assert request.negative_hint == ""
    assert request.refinement_instruction == ""
    assert request.candidate_targets == []
    assert request.target_dataset_id is None


# ---------------------------------------------------------------------------
# TargetIntentOption
# ---------------------------------------------------------------------------


def test_target_intent_option_required_fields() -> None:
    """TargetIntentOption should require the three descriptive fields."""
    option = TargetIntentOption(
        target_system="canonical",
        label="Canonical (recommended)",
        description="Map to the canonical layer.",
        projection_mode="canonical_only",
    )
    assert option.artifact_type == "canonical-only"
    assert option.target_profile is None

    with pytest.raises(ValidationError):
        TargetIntentOption(  # type: ignore[call-arg]
            target_system="canonical",
        )


# ---------------------------------------------------------------------------
# Coverage report models
# ---------------------------------------------------------------------------


def test_canonical_coverage_column_match_defaults() -> None:
    """CanonicalCoverageColumnMatch should default concept_ids to []."""
    match = CanonicalCoverageColumnMatch(column="email")
    assert match.concept_ids == []


def test_canonical_coverage_summary_defaults() -> None:
    """CanonicalCoverageSummary should expose zero-value defaults."""
    summary = CanonicalCoverageSummary()
    assert summary.total_columns == 0
    assert summary.matched_columns == 0
    assert summary.coverage_ratio == 0.0
    assert summary.unmatched_columns == []
    assert summary.matched_columns_detail == []


def test_canonical_coverage_project_summary_defaults() -> None:
    """CanonicalCoverageProjectSummary should default concept lists to []."""
    summary = CanonicalCoverageProjectSummary()
    assert summary.concept_count == 0
    assert summary.shared_concepts == []


def test_canonical_coverage_report_empty_factory() -> None:
    """CanonicalCoverageReport should be constructible with no arguments."""
    report = CanonicalCoverageReport()
    assert isinstance(report.source, CanonicalCoverageSummary)
    assert isinstance(report.target, CanonicalCoverageSummary)
    assert isinstance(report.project, CanonicalCoverageProjectSummary)


# ---------------------------------------------------------------------------
# Runtime fingerprint + response
# ---------------------------------------------------------------------------


def test_mapping_runtime_fingerprint_defaults() -> None:
    """MappingRuntimeFingerprint should expose string/None defaults."""
    fp = MappingRuntimeFingerprint()
    assert fp.generated_at == ""
    assert fp.app_version == ""
    assert fp.scoring_profile == ""
    assert fp.description_priority is False
    assert fp.target_system is None
    assert fp.target_projection_mode == "dataset_to_dataset"


def test_auto_mapping_response_defaults() -> None:
    """AutoMappingResponse should default all collections to [] / empty factories."""
    response = AutoMappingResponse()
    assert response.mappings == []
    assert response.ranked_mappings == []
    assert isinstance(response.canonical_coverage, CanonicalCoverageReport)
    assert response.applied_source_field_hints == []
    assert isinstance(response.mapping_runtime, MappingRuntimeFingerprint)


# ---------------------------------------------------------------------------
# Mapping analysis / narration
# ---------------------------------------------------------------------------


def test_mapping_analysis_workspace_context_defaults() -> None:
    """Workspace context should default mode, names, and optional fields."""
    ctx = MappingAnalysisWorkspaceContext()
    assert ctx.mapping_mode == "standard"
    assert ctx.source_dataset_name == "Source dataset"
    assert ctx.target_dataset_name == "Target dataset"
    assert ctx.source_system is None
    assert ctx.business_domain is None


def test_mapping_analysis_options_defaults() -> None:
    """MappingAnalysisOptions should default audience and narration seed flag."""
    opts = MappingAnalysisOptions()
    assert opts.audience == "technical_implementor"
    assert opts.include_narration_seed is True


def test_mapping_analysis_overall_mapping_health_defaults() -> None:
    """Overall health should default to zero counts and 'low' risk."""
    health = MappingAnalysisOverallMappingHealth()
    assert health.accepted_count == 0
    assert health.needs_review_count == 0
    assert health.rejected_count == 0
    assert health.unmatched_count == 0
    assert health.overall_risk == "low"


def test_mapping_analysis_confidence_distribution_defaults() -> None:
    """Confidence distribution should default ratios to 0.0 and interpretation to ''."""
    dist = MappingAnalysisConfidenceDistribution()
    assert dist.high_confidence_count == 0
    assert dist.high_confidence_ratio == 0.0
    assert dist.interpretation == ""


def test_mapping_analysis_strongest_match_defaults() -> None:
    """Strongest match should default lists and supporting signals to []."""
    match = MappingAnalysisStrongestMatch(source="email", target="email_address", confidence=0.9)
    assert match.why_it_is_strong == ""
    assert match.supporting_signals == []
    assert match.canonical_path == ""


def test_mapping_analysis_unmatched_source_defaults() -> None:
    """Unmatched source entry should default reason/follow-up to ''."""
    item = MappingAnalysisUnmatchedSource(source="unknown")
    assert item.reason == ""
    assert item.recommended_follow_up == ""


def test_mapping_analysis_transformation_hotspot_defaults() -> None:
    """Transformation hotspot should default target to '' and risk to 'low'."""
    hotspot = MappingAnalysisTransformationHotspot(source="x")
    assert hotspot.target == ""
    assert hotspot.transformation_required is False
    assert hotspot.transformation_risk == "low"


def test_mapping_analysis_generation_metadata_defaults() -> None:
    """Generation metadata should default to fallback (no LLM used)."""
    meta = MappingAnalysisGenerationMetadata()
    assert meta.used_llm is False
    assert meta.fallback_used is True
    assert meta.llm_provider is None
    assert meta.llm_model is None


def test_mapping_analysis_summary_response_defaults() -> None:
    """Summary response should be valid with no arguments; audience default."""
    summary = MappingAnalysisSummaryResponse()
    assert summary.audience == "technical_implementor"
    assert summary.title == ""
    assert summary.strongest_matches == []
    assert summary.needs_review_items == []
    assert summary.unmatched_sources == []
    assert summary.transformation_hotspots == []
    assert summary.implementation_risks == []
    assert summary.recommended_next_actions == []
    assert summary.narration_script_seed == ""


def test_mapping_analysis_narration_request_holds_summary() -> None:
    """MappingAnalysisNarrationRequest should embed the summary unchanged."""
    summary = MappingAnalysisSummaryResponse(title="X")
    request = MappingAnalysisNarrationRequest(summary=summary)
    assert request.summary is summary
    assert request.summary.title == "X"


def test_mapping_analysis_narration_response_defaults() -> None:
    """Narration response should default spoken_script to '' and metadata to fallback."""
    response = MappingAnalysisNarrationResponse()
    assert response.spoken_script == ""
    assert response.generation_metadata.used_llm is False
    assert response.generation_metadata.fallback_used is True


def test_mapping_analysis_request_round_trip() -> None:
    """MappingAnalysisRequest should preserve workspace and options instances."""
    response = AutoMappingResponse()
    workspace = MappingAnalysisWorkspaceContext(mapping_mode="canonical")
    options = MappingAnalysisOptions(audience="technical_implementor")
    request = MappingAnalysisRequest(
        mapping_response=response, workspace=workspace, options=options
    )
    assert request.mapping_response is response
    assert request.workspace.mapping_mode == "canonical"
    assert request.options.audience == "technical_implementor"
