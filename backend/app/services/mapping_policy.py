"""Centralized scoring profiles and threshold policies for the Semantra mapping engine."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import settings


DEFAULT_SCORING_PROFILE = "balanced"

SCORING_PROFILES = {
    "balanced": {
        "name": 0.20,
        "semantic": 0.12,
        "knowledge": 0.10,
        "canonical": 0.05,
        "pattern": 0.20,
        "statistical": 0.15,
        "overlap": 0.10,
        "embedding": 0.12,
        "correction": 0.10,
        "llm": 0.05,
    },
    "schema_only": {
        "name": 0.22,
        "semantic": 0.16,
        "knowledge": 0.16,
        "canonical": 0.10,
        "pattern": 0.12,
        "statistical": 0.08,
        "overlap": 0.04,
        "embedding": 0.14,
        "correction": 0.10,
        "llm": 0.05,
    },
    "data_rich": {
        "name": 0.16,
        "semantic": 0.10,
        "knowledge": 0.10,
        "canonical": 0.06,
        "pattern": 0.20,
        "statistical": 0.18,
        "overlap": 0.16,
        "embedding": 0.10,
        "correction": 0.08,
        "llm": 0.05,
    },
    "canonical_first": {
        "name": 0.10,
        "semantic": 0.12,
        "knowledge": 0.22,
        "canonical": 0.18,
        "pattern": 0.12,
        "statistical": 0.08,
        "overlap": 0.05,
        "embedding": 0.08,
        "correction": 0.10,
        "llm": 0.05,
    },
    "description_priority": {
        "name": 0.12,
        "semantic": 0.22,
        "knowledge": 0.18,
        "canonical": 0.12,
        "pattern": 0.08,
        "statistical": 0.05,
        "overlap": 0.03,
        "embedding": 0.12,
        "correction": 0.03,
        "llm": 0.05,
    },
}

WEIGHTS = SCORING_PROFILES[DEFAULT_SCORING_PROFILE]
SIGNAL_WEIGHT_NAMES = tuple(WEIGHTS.keys())


@dataclass(frozen=True)
class DecisionThresholdPolicy:
    high_confidence: float
    medium_confidence: float
    auto_accept: float


@dataclass(frozen=True)
class SapSignalPolicy:
    strong_canonical_knowledge_min: float = 0.85
    strong_canonical_canonical_min: float = 0.60
    table_field_knowledge_min: float = 0.65
    table_field_canonical_min: float = 0.45
    pir_table_field_knowledge_min: float = 0.75
    pir_table_field_canonical_min: float = 0.55
    exact_code_canonical_strong_min: float = 0.85
    exact_code_canonical_medium_min: float = 0.70
    exact_code_knowledge_medium_min: float = 0.60
    exact_code_pir_canonical_min: float = 0.55
    exact_code_pir_knowledge_min: float = 0.55
    anchor_preserved_knowledge_min: float = 0.75
    anchor_preserved_canonical_min: float = 0.60
    business_anchor_primary_knowledge_weight: float = 0.85
    business_anchor_primary_canonical_weight: float = 0.15
    business_anchor_secondary_knowledge_weight: float = 0.70
    business_anchor_secondary_canonical_weight: float = 0.30


@dataclass(frozen=True)
class SignalEvidencePolicy:
    business_concept_lock_semantic_min: float = 0.60
    business_concept_lock_knowledge_min: float = 0.95
    business_concept_lock_canonical_min: float = 0.75
    weak_pattern_deemphasis_max: float = 0.20
    weak_overlap_deemphasis_max: float = 0.10
    identifier_business_knowledge_min: float = 0.95
    identifier_business_canonical_min: float = 0.75
    identifier_value_overlap_min: float = 0.95
    identifier_value_statistical_min: float = 0.95
    identifier_pattern_min: float = 0.95
    canonical_core_identifier_knowledge_min: float = 0.85
    canonical_core_identifier_unique_ratio_min: float = 0.90
    canonical_core_identifier_null_ratio_max: float = 0.20
    canonical_core_identifier_floor_offset: float = 0.45
    fallback_name_min: float = 0.75
    fallback_semantic_min: float = 0.60
    fallback_knowledge_min: float = 0.60
    fallback_canonical_min: float = 0.60
    fallback_pattern_min: float = 0.80
    fallback_overlap_min: float = 0.50
    fallback_embedding_min: float = 0.65
    explanation_semantic_min: float = 0.60
    explanation_name_min: float = 0.75
    explanation_embedding_min: float = 0.65


def normalize_scoring_profile_name(profile_name: str | None) -> str:
    normalized = (profile_name or DEFAULT_SCORING_PROFILE).strip().lower().replace("-", "_")
    return normalized or DEFAULT_SCORING_PROFILE


def resolve_scoring_weights(
    profile_name: str | None = None,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    resolved_profile = normalize_scoring_profile_name(profile_name or settings.scoring_profile)
    base_weights = SCORING_PROFILES.get(resolved_profile)
    if base_weights is None:
        available = ", ".join(sorted(SCORING_PROFILES))
        raise ValueError(f"Unknown scoring profile '{resolved_profile}'. Available profiles: {available}.")

    merged = dict(base_weights)
    configured_overrides = overrides if overrides is not None else settings.scoring_weight_overrides
    for signal_name, signal_weight in configured_overrides.items():
        normalized_name = str(signal_name).strip().lower().replace("-", "_")
        if normalized_name not in merged:
            available = ", ".join(SIGNAL_WEIGHT_NAMES)
            raise ValueError(f"Unknown scoring signal '{signal_name}' in overrides. Expected one of: {available}.")
        merged[normalized_name] = float(signal_weight)
        if merged[normalized_name] < 0:
            raise ValueError(f"Scoring weight for '{normalized_name}' cannot be negative.")
    return merged


def resolve_decision_threshold_policy(*, is_sap_pir: bool) -> DecisionThresholdPolicy:
    if is_sap_pir:
        return DecisionThresholdPolicy(
            high_confidence=settings.sap_pir_high_confidence_threshold,
            medium_confidence=settings.sap_pir_medium_confidence_threshold,
            auto_accept=settings.sap_pir_auto_accept_threshold,
        )
    return DecisionThresholdPolicy(
        high_confidence=settings.high_confidence_threshold,
        medium_confidence=settings.medium_confidence_threshold,
        auto_accept=settings.auto_accept_threshold,
    )


def resolve_sap_signal_policy() -> SapSignalPolicy:
    return SapSignalPolicy()


def resolve_signal_evidence_policy() -> SignalEvidencePolicy:
    return SignalEvidencePolicy()