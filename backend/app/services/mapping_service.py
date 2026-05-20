"""Core mapping engine for scoring, assignment, explanations, and ranking behavior."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from collections.abc import Callable
from datetime import UTC, datetime

from app.core.config import backend_code_fingerprint, settings
from app.models.mapping import (
    AutoMappingResponse,
    CanonicalCoverageReport,
    CandidateOption,
    CanonicalMappingDetails,
    DecisionLogEntry,
    LLMDecisionProposition,
    LLMValidationResult,
    MappingRuntimeFingerprint,
    MappingCandidate,
    ScoringSignals,
    SourceMappingResult,
)
from app.services.correction_service import correction_store
from app.services.decision_log_service import decision_log_store
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.llm_service import LLMProvider, call_validator
from app.services.embedding_service import cosine_similarity, get_embedding, is_enabled as embedding_enabled
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.utils.normalization import semantic_token_set
from app.utils.similarity import clamp_score, fuzzy_similarity, jaccard_similarity, score_distance


DEFAULT_SCORING_PROFILE = "balanced"
AUTO_DESCRIPTION_PRIORITY_MIN_METADATA_COLUMNS = 1
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


def normalize_scoring_profile_name(profile_name: str | None) -> str:
    """Normalize a scoring profile name into the canonical internal identifier."""

    normalized = (profile_name or DEFAULT_SCORING_PROFILE).strip().lower().replace("-", "_")
    return normalized or DEFAULT_SCORING_PROFILE


def resolve_scoring_weights(
    profile_name: str | None = None,
    overrides: dict[str, float] | None = None,
) -> dict[str, float]:
    """Resolve the active scoring weights for a profile plus any runtime overrides."""

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


def build_mapping_runtime_fingerprint(*, description_priority: bool) -> MappingRuntimeFingerprint:
    """Build a short fingerprint describing the scoring/runtime code used for one mapping response."""

    return MappingRuntimeFingerprint(
        generated_at=datetime.now(UTC).isoformat(),
        app_version=settings.app_version,
        scoring_profile=settings.scoring_profile,
        description_priority=bool(description_priority),
        code_fingerprint=backend_code_fingerprint(),
    )


TOTAL_WEIGHT = sum(WEIGHTS.values())
ProgressCallback = Callable[[str], None]


class ProgressCallbackCancelled(RuntimeError):
    """Raised when a caller cancels an in-flight progress callback during mapping."""

    pass


@dataclass
class CandidateScore:
    """Internal scored candidate bundle used during ranking, validation, and assignment."""

    source: ColumnProfile
    target: ColumnProfile
    score: float
    signals: ScoringSignals
    explanation: list[str]
    active_signal_names: set[str] = field(default_factory=set)
    canonical_details: CanonicalMappingDetails = field(default_factory=CanonicalMappingDetails)
    llm_result: LLMValidationResult | None = None
    llm_selected: bool = False


@dataclass(frozen=True)
class SourceSapContextProfile:
    """Precomputed SAP context hints for a source column used in confidence calibration."""

    exact_canonical_concept_id: str | None = None
    has_sap_table_field_context: bool = False
    has_pir_table_field_context: bool = False


def generate_mapping_candidates(
    source_schema: SchemaProfile,
    target_schema: SchemaProfile,
    llm_provider: LLMProvider | None = None,
    write_decision_log: bool = True,
    progress_callback: ProgressCallback | None = None,
    description_priority: bool = False,
    candidate_pool_size: int | None = None,
) -> AutoMappingResponse:
    """Generate the full Semantra mapping response for one source-target schema pair.

    The function ranks candidates per source field, optionally applies bounded LLM
    validation inside the ambiguity band, enforces unique target assignment, and
    assembles the final response consumed by API and UI workflows.
    """

    effective_description_priority = description_priority or should_auto_enable_description_priority(target_schema)
    source_columns = list(source_schema.columns)
    target_columns = list(target_schema.columns)
    target_embedding_cache: dict[str, list[float] | None] = {}
    _emit_progress(
        progress_callback,
        f"Loaded {len(source_columns)} source fields and {len(target_columns)} target fields for mapping.",
    )
    if candidate_pool_size:
        _emit_progress(
            progress_callback,
            f"Canonical shortlist enabled: scoring up to {candidate_pool_size} likely targets per source field.",
        )
    per_source_scores: dict[str, list[CandidateScore]] = {}
    for index, source_column in enumerate(source_columns, start=1):
        _emit_progress(progress_callback, f"Ranking {index}/{len(source_columns)}: {source_column.name}.")
        per_source_scores[source_column.name] = rank_targets_for_source(
            source_column,
            target_columns,
            target_embedding_cache=target_embedding_cache,
            description_priority=effective_description_priority,
            candidate_pool_size=candidate_pool_size,
        )

    _emit_progress(progress_callback, "Applying LLM validation gates." if llm_provider else "LLM validation disabled; using heuristic ranking only.")
    llm_decisions = apply_llm_validation(per_source_scores, llm_provider, progress_callback=progress_callback)

    _emit_progress(progress_callback, "Assigning unique target fields across the full schema.")
    assigned_scores = assign_unique_targets(per_source_scores)
    selected_mappings: list[MappingCandidate] = []
    ranked_results: list[SourceMappingResult] = []


    for index, source_column in enumerate(source_columns, start=1):
        rankings = per_source_scores[source_column.name]
        selected_score = assigned_scores.get(source_column.name)
        candidate_options = [build_candidate_option(score) for score in rankings[: settings.top_k_candidates]]

        llm_result = llm_decisions.get(source_column.name)
        transformation_code = llm_result.transformation_code if llm_result and hasattr(llm_result, 'transformation_code') else None

        if not rankings:
            ranked_results.append(
                SourceMappingResult(
                    source=source_column.name,
                    selected=None,
                    candidates=[],
                )
            )
            selected_mappings.append(
                MappingCandidate(
                    source=source_column.name,
                    target=None,
                    confidence=0.0,
                    confidence_label="low_confidence",
                    status="needs_review",
                    method="no_match",
                    signals=ScoringSignals(),
                    explanation=["No compatible target fields were found."],
                    alternatives=[],
                    # transformation_code intentionally omitted
                )
            )
            _emit_progress(progress_callback, f"Selected {index}/{len(source_columns)}: {source_column.name} -> no_match.")
            continue

        if llm_result and llm_result.selected_target == "no_match":
            considered_targets = [candidate.target.name for candidate in rankings[: settings.top_k_candidates]]
            selected = MappingCandidate(
                source=source_column.name,
                target=None,
                confidence=0.0,
                confidence_label="low_confidence",
                status="needs_review",
                method="llm_validator_no_match",
                signals=ScoringSignals(llm=llm_result.confidence),
                explanation=[
                    "LLM validator rejected the available candidates inside the closed candidate set.",
                    *[f"LLM: {reason}" for reason in llm_result.reasoning],
                ],
                alternatives=[candidate.target.name for candidate in rankings[: settings.top_k_candidates]],
                transformation_code=transformation_code,
                llm_consulted=True,
                llm_recommendation=llm_result,
                llm_decision_proposition=build_llm_decision_proposition(
                    llm_result,
                    final_target=None,
                    considered_targets=considered_targets,
                ),
            )
            ranked_results.append(
                SourceMappingResult(
                    source=source_column.name,
                    selected=selected,
                    candidates=candidate_options,
                )
            )
            selected_mappings.append(selected)
            _emit_progress(progress_callback, f"Selected {index}/{len(source_columns)}: {source_column.name} -> no_match by LLM.")
            if write_decision_log:
                log_decision(source_column.name, rankings[: settings.top_k_candidates], llm_result, selected)
            continue

        if selected_score is None:
            extra_explanation = ["No unique target was assigned by the global matching step; manual review required."]
            if llm_result and llm_result.selected_target != "no_match":
                extra_explanation.insert(
                    0,
                    f"LLM validator preferred '{llm_result.selected_target}', but that target was already assigned elsewhere by the global one-to-one matching step.",
                )
            selected = build_selected_mapping(
                source_column.name,
                rankings[0],
                status="needs_review",
                extra_explanation=extra_explanation,
                alternatives=[candidate.target.name for candidate in rankings[1:settings.top_k_candidates]],
                llm_result=llm_result,
                considered_targets=[candidate.target.name for candidate in rankings[: settings.top_k_candidates]],
            )
        else:
            extra_explanation: list[str] = []
            if llm_result and llm_result.selected_target != "no_match" and llm_result.selected_target != selected_score.target.name:
                extra_explanation.append(
                    f"LLM validator preferred '{llm_result.selected_target}', but global one-to-one assignment selected this target instead."
                )
            if rankings[0].target.name != selected_score.target.name:
                extra_explanation.append(
                    "Global assignment selected this target to maximize one-to-one mapping coverage across the full schema."
                )
            selected = build_selected_mapping(
                source_column.name,
                selected_score,
                status=label_to_status(selected_score.score, source=source_column),
                extra_explanation=extra_explanation,
                alternatives=[
                    candidate.target.name
                    for candidate in rankings[: settings.top_k_candidates]
                    if candidate.target.name != selected_score.target.name
                ],
                llm_result=llm_result,
                considered_targets=[candidate.target.name for candidate in rankings[: settings.top_k_candidates]],
            )
        # Attach transformation_code if present
        if transformation_code:
            selected.transformation_code = transformation_code

        if write_decision_log:
            log_decision(source_column.name, rankings[: settings.top_k_candidates], llm_result, selected)

        ranked_results.append(
            SourceMappingResult(
                source=source_column.name,
                selected=selected,
                candidates=candidate_options,
            )
        )
        selected_mappings.append(selected)
        _emit_progress(
            progress_callback,
            f"Selected {index}/{len(source_columns)}: {source_column.name} -> {selected.target or 'no_match'} "
            f"({selected.confidence:.0%}, {selected.method}).",
        )

    source_canonical_coverage = metadata_knowledge_service.canonical_coverage(
        source_schema,
        prefer_metadata_text=description_priority,
    )
    target_canonical_coverage = metadata_knowledge_service.canonical_coverage(
        target_schema,
        prefer_metadata_text=description_priority,
    )
    canonical_coverage = CanonicalCoverageReport(
        source=source_canonical_coverage,
        target=target_canonical_coverage,
        project=metadata_knowledge_service.canonical_project_coverage(
            source_canonical_coverage,
            target_canonical_coverage,
        ),
    )

    _emit_progress(progress_callback, "Computing canonical coverage summary.")

    response = AutoMappingResponse(
        mappings=selected_mappings,
        ranked_mappings=ranked_results,
        canonical_coverage=canonical_coverage,
        mapping_runtime=build_mapping_runtime_fingerprint(description_priority=effective_description_priority),
    )
    _emit_progress(progress_callback, "Mapping response assembled.")
    return response


def refine_mapping_for_source(
    source: ColumnProfile,
    targets: list[ColumnProfile],
    *,
    llm_provider: LLMProvider | None,
    description_priority: bool = False,
    candidate_pool_size: int | None = None,
    candidate_target_names: list[str] | None = None,
) -> SourceMappingResult:
    """Re-rank one source field and let the bounded validator choose within a closed candidate set."""

    rankings = rank_targets_for_source(
        source,
        targets,
        description_priority=description_priority,
        candidate_pool_size=candidate_pool_size,
    )
    if candidate_target_names:
        allowed_names = {str(name or "").strip() for name in candidate_target_names if str(name or "").strip()}
        rankings = [score for score in rankings if score.target.name in allowed_names]

    candidate_scores = rankings[: settings.top_k_candidates]
    candidate_options = [build_candidate_option(score) for score in candidate_scores]
    if not candidate_scores:
        return SourceMappingResult(source=source.name, selected=None, candidates=[])
    if llm_provider is None:
        raise ValueError("LLM mapping refinement requires an active runtime provider.")

    llm_result = call_validator(
        source_field={
            "name": source.name,
            "description": source.description,
            "declared_type": source.declared_type,
            "sample_values": source.sample_values,
            "pattern": source.detected_patterns,
            "detected_patterns": source.detected_patterns,
            "unique_ratio": source.unique_ratio,
        },
        candidate_targets=[
            {
                "name": candidate.target.name,
                "description": candidate.target.description,
                "declared_type": candidate.target.declared_type,
                "sample_values": candidate.target.sample_values,
                "pattern": candidate.target.detected_patterns,
                "detected_patterns": candidate.target.detected_patterns,
                "confidence": candidate.score,
            }
            for candidate in candidate_scores
        ],
        provider=llm_provider,
    )
    if llm_result is None:
        raise ValueError("LLM returned no usable mapping refinement for this field.")

    if source.description or source.declared_type:
        llm_result.reasoning = list(llm_result.reasoning) + [
            "LLM received source field metadata context (description/type) for this refinement."
        ]

    considered_targets = [candidate.target.name for candidate in candidate_scores]
    if llm_result.selected_target == "no_match":
        selected = MappingCandidate(
            source=source.name,
            target=None,
            confidence=0.0,
            confidence_label="low_confidence",
            status="needs_review",
            method="llm_validator_no_match",
            signals=ScoringSignals(llm=llm_result.confidence),
            explanation=[
                "LLM refinement rejected the available candidates inside the closed candidate set.",
                *[f"LLM: {reason}" for reason in llm_result.reasoning],
            ],
            alternatives=considered_targets,
            transformation_code=llm_result.transformation_code,
            llm_consulted=True,
            llm_recommendation=llm_result,
            llm_decision_proposition=build_llm_decision_proposition(
                llm_result,
                final_target=None,
                considered_targets=considered_targets,
            ),
        )
        return SourceMappingResult(source=source.name, selected=selected, candidates=candidate_options)

    selected_score = next((candidate for candidate in candidate_scores if candidate.target.name == llm_result.selected_target), None)
    if selected_score is None:
        raise ValueError("LLM selected a target outside the candidate set.")

    selected_score.signals.llm = round(llm_result.confidence, 4)
    selected_score.active_signal_names.add("llm")
    selected_score.score = compute_final_score(
        selected_score.signals,
        selected_score.active_signal_names,
        profile_name="description_priority" if description_priority else None,
        source=source,
        target=selected_score.target,
    )
    selected_score.llm_result = llm_result
    selected_score.llm_selected = True
    refresh_signal_breakdown(selected_score.explanation, selected_score.signals)
    selected_score.explanation.append("LLM validator re-ranked this candidate within the closed candidate set.")
    if has_strong_identifier_consensus(selected_score.signals, selected_score.active_signal_names):
        selected_score.explanation.append(
            "Strong identifier consensus detected: business metadata, value behavior, and LLM confirmation all point to this target."
        )

    selected = build_selected_mapping(
        source.name,
        selected_score,
        status="needs_review",
        extra_explanation=[],
        alternatives=[candidate.target.name for candidate in candidate_scores if candidate.target.name != selected_score.target.name],
        llm_result=llm_result,
        considered_targets=considered_targets,
    )
    if llm_result.transformation_code:
        selected.transformation_code = llm_result.transformation_code
    return SourceMappingResult(source=source.name, selected=selected, candidates=candidate_options)


def rank_targets_for_source(
    source: ColumnProfile,
    targets: list[ColumnProfile],
    *,
    target_embedding_cache: dict[str, list[float] | None] | None = None,
    description_priority: bool = False,
    candidate_pool_size: int | None = None,
) -> list[CandidateScore]:
    """Score and sort viable target fields for a single source column."""

    sap_source_anchor = has_strong_sap_source_anchor(source, prefer_metadata_text=description_priority)
    source_sap_profile = build_source_sap_context_profile(source, prefer_metadata_text=description_priority)
    candidate_targets = shortlist_targets_for_source(
        source,
        targets,
        candidate_pool_size=candidate_pool_size,
        description_priority=description_priority,
    )
    scored: list[CandidateScore] = []
    for target in candidate_targets:
        signals, active_signal_names = compute_signals(
            source,
            target,
            target_embedding_cache=target_embedding_cache,
            description_priority=description_priority,
        )
        deemphasized_signal_names = strong_concept_lock_deemphasized_signals(signals, active_signal_names, source)
        if deemphasized_signal_names:
            active_signal_names = set(active_signal_names)
            active_signal_names.difference_update(deemphasized_signal_names)
        final_score = compute_final_score(
            signals,
            active_signal_names,
            profile_name="description_priority" if description_priority else None,
            source=source,
            target=target,
            source_sap_profile=source_sap_profile,
        )
        explanation = build_explanation(source, target, signals, description_priority=description_priority)
        sap_boost = compute_sap_confidence_boost(signals, source_sap_profile)
        if sap_boost > 0:
            explanation.append(
                f"SAP context prior boosted confidence by +{sap_boost:.2f} (table+field and/or exact SAP code canonical evidence)."
            )
        if deemphasized_signal_names:
            explanation.append(
                "Weak physical evidence was de-emphasized because semantic, knowledge, and canonical signals already formed a strong business concept lock."
            )
        if sap_source_anchor and is_sap_anchor_preserved(signals):
            explanation.append(
                "Strong SAP source-alias evidence is preserved as a business anchor for this candidate; weak heuristic signals cannot heavily dilute the concept match."
            )
        scored.append(
            CandidateScore(
                source=source,
                target=target,
                score=final_score,
                signals=signals,
                active_signal_names=active_signal_names,
                explanation=explanation,
                canonical_details=metadata_knowledge_service.canonical_mapping_details(
                    source,
                    target,
                    prefer_metadata_text=description_priority,
                ),
            )
        )
    return sorted(scored, key=lambda item: item.score, reverse=True)


def shortlist_targets_for_source(
    source: ColumnProfile,
    targets: list[ColumnProfile],
    *,
    candidate_pool_size: int | None = None,
    description_priority: bool = False,
) -> list[ColumnProfile]:
    """Build a likely-target shortlist before full scoring when candidate pooling is enabled."""

    if not candidate_pool_size or candidate_pool_size >= len(targets):
        return targets

    target_by_name = {target.name: target for target in targets}
    shortlisted_names: list[str] = []
    seen_names: set[str] = set()

    source_canonical_matches = metadata_knowledge_service.match_canonical_concepts(
        source,
        prefer_metadata_text=description_priority,
    )
    for match in sorted(source_canonical_matches, key=lambda item: item.strength, reverse=True):
        target = target_by_name.get(match.concept_id)
        if target is None or target.name in seen_names:
            continue
        shortlisted_names.append(target.name)
        seen_names.add(target.name)
        if len(shortlisted_names) >= candidate_pool_size:
            return [target_by_name[name] for name in shortlisted_names]

    source_tokens = set(source.tokenized_name)
    source_semantic = semantic_token_set(source.name) | metadata_knowledge_service.expand_semantic_tokens(
        source,
        prefer_metadata_text=description_priority,
    )
    ranked_by_likelihood = sorted(
        targets,
        key=lambda target: (
            0.45 * fuzzy_similarity(source.normalized_name, target.normalized_name)
            + 0.35 * jaccard_similarity(
                source_semantic,
                semantic_token_set(target.name) | set(target.tokenized_name),
            )
            + 0.20 * jaccard_similarity(source_tokens, set(target.tokenized_name))
        ),
        reverse=True,
    )
    for target in ranked_by_likelihood:
        if target.name in seen_names:
            continue
        shortlisted_names.append(target.name)
        seen_names.add(target.name)
        if len(shortlisted_names) >= candidate_pool_size:
            break

    return [target_by_name[name] for name in shortlisted_names]


def apply_llm_validation(
    per_source_scores: dict[str, list[CandidateScore]],
    llm_provider: LLMProvider | None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, LLMValidationResult]:
    """Run bounded LLM validation only for rankings that meet Semantra's review gates."""

    llm_decisions: dict[str, LLMValidationResult] = {}

    if llm_provider is None:
        return llm_decisions

    for source_name, rankings in per_source_scores.items():
        if not rankings:
            continue
        rescue_mode = should_run_canonical_semantic_rescue(rankings[0])
        if not should_run_llm_validation(rankings):
            _emit_progress(progress_callback, f"LLM skipped for {source_name}: ranking is outside the ambiguity band.")
            continue

        candidate_scores = rankings[: settings.top_k_candidates]
        source_column = candidate_scores[0].source
        source_sap_profile = build_source_sap_context_profile(source_column)
        _emit_progress(progress_callback, f"LLM validating {source_name} against top {len(candidate_scores)} candidates.")
        llm_result = call_validator(
            source_field={
                "name": source_column.name,
                "description": source_column.description,
                "declared_type": source_column.declared_type,
                "sample_values": source_column.sample_values,
                "pattern": source_column.detected_patterns,
                "detected_patterns": source_column.detected_patterns,
                "unique_ratio": source_column.unique_ratio,
            },
            candidate_targets=[
                {
                    "name": candidate.target.name,
                    "description": candidate.target.description,
                    "declared_type": candidate.target.declared_type,
                    "sample_values": candidate.target.sample_values,
                    "pattern": candidate.target.detected_patterns,
                    "detected_patterns": candidate.target.detected_patterns,
                    "confidence": candidate.score,
                }
                for candidate in candidate_scores
            ],
            provider=llm_provider,
            low_confidence_fallback_to_no_match=rescue_mode,
        )
        if llm_result is None:
            _emit_progress(progress_callback, f"LLM returned no usable recommendation for {source_name}; keeping heuristic ranking.")
            continue
        llm_decisions[source_name] = llm_result
        if source_column.description or source_column.declared_type:
            llm_result.reasoning = list(llm_result.reasoning) + [
                "LLM received source field metadata context (description/type) for this decision."
            ]

        if llm_result.selected_target == "no_match":
            _emit_progress(progress_callback, f"LLM rejected all candidates for {source_name}.")
            continue

        for candidate in candidate_scores:
            if candidate.target.name != llm_result.selected_target:
                continue
            candidate.signals.llm = round(llm_result.confidence, 4)
            candidate.active_signal_names.add("llm")
            candidate.score = compute_final_score(
                candidate.signals,
                candidate.active_signal_names,
                source=candidate.source,
                target=candidate.target,
                source_sap_profile=source_sap_profile,
            )
            candidate.llm_result = llm_result
            candidate.llm_selected = True
            refresh_signal_breakdown(candidate.explanation, candidate.signals)
            if has_strong_identifier_consensus(candidate.signals, candidate.active_signal_names):
                candidate.explanation.append(
                    "Strong identifier consensus detected: business metadata, value behavior, and LLM confirmation all point to this target."
                )
            candidate.explanation.extend(
                ["LLM validator re-ranked this candidate within the closed candidate set."]
                + [f"LLM: {reason}" for reason in llm_result.reasoning]
            )
            _emit_progress(progress_callback, f"LLM preferred {source_name} -> {llm_result.selected_target} ({llm_result.confidence:.0%}).")
            break

        rankings.sort(key=lambda item: (item.llm_selected, item.score), reverse=True)

    return llm_decisions


def _emit_progress(progress_callback: ProgressCallback | None, message: str) -> None:
    if progress_callback is None:
        return
    try:
        progress_callback(message)
    except ProgressCallbackCancelled:
        raise
    except Exception:
        return


def should_run_llm_validation(rankings: list[CandidateScore]) -> bool:
    """Return whether a ranked candidate list should enter the bounded LLM validation gate."""

    if not rankings:
        return False

    top_candidate = rankings[0]
    top_score = top_candidate.score
    # When a strong canonical concept lock is active (explicit KC→CC bridge evidence),
    # the mapping is already well-grounded unless another strong canonical target
    # is effectively tied and needs arbitration.
    if is_strong_canonical_concept_match(top_candidate.target, top_candidate.signals.knowledge, top_candidate.signals.canonical):
        if has_close_strong_canonical_competitor(rankings):
            return True
        return False
    if settings.llm_gate_min_score < top_score < settings.llm_gate_max_score:
        return True
    return should_run_canonical_semantic_rescue(top_candidate)


def has_close_strong_canonical_competitor(rankings: list[CandidateScore]) -> bool:
    """Return whether the top candidate has a near-tied strong canonical competitor."""

    if len(rankings) < 2:
        return False

    top_candidate = rankings[0]
    for challenger in rankings[1:settings.top_k_candidates]:
        if not is_strong_canonical_concept_match(
            challenger.target,
            challenger.signals.knowledge,
            challenger.signals.canonical,
        ):
            continue
        if (top_candidate.score - challenger.score) < settings.strong_canonical_llm_margin:
            return True
    return False


def should_run_canonical_semantic_rescue(top_candidate: CandidateScore) -> bool:
    """Return whether a canonical-looking top candidate should trigger semantic rescue via the LLM."""

    if top_candidate.score >= settings.llm_gate_max_score or top_candidate.score < 0.2:
        return False
    if not is_canonical_target_name(top_candidate.target.name):
        return False
    if top_candidate.signals.semantic < 0.45:
        return False
    if top_candidate.signals.knowledge > 0 or top_candidate.signals.canonical > 0:
        return False
    return True


def should_auto_enable_description_priority(target_schema: SchemaProfile) -> bool:
    """Return whether a schema-spec target should automatically prefer descriptive metadata."""

    if target_schema.row_count != 0:
        return False
    described_columns = sum(1 for column in target_schema.columns if column.description or column.declared_type)
    return described_columns >= AUTO_DESCRIPTION_PRIORITY_MIN_METADATA_COLUMNS


def is_canonical_target_name(target_name: str) -> bool:
    """Return whether a target name is itself a canonical concept id."""

    return metadata_knowledge_service.resolve_canonical_concept_id(target_name) == target_name


def compute_signals(
    source: ColumnProfile,
    target: ColumnProfile,
    *,
    target_embedding_cache: dict[str, list[float] | None] | None = None,
    description_priority: bool = False,
) -> tuple[ScoringSignals, set[str]]:
    """Compute the raw multi-signal evidence for one source-target candidate pair."""

    source_tokens = set(source.tokenized_name)
    target_tokens = set(target.tokenized_name)
    source_semantic = semantic_token_set(source.name) | metadata_knowledge_service.expand_semantic_tokens(
        source,
        prefer_metadata_text=description_priority,
    )
    target_semantic = semantic_token_set(target.name) | metadata_knowledge_service.expand_semantic_tokens(
        target,
        prefer_metadata_text=description_priority,
    )
    source_patterns = set(source.detected_patterns)
    target_patterns = set(target.detected_patterns)
    source_values = set(source.distinct_sample_values)
    target_values = set(target.distinct_sample_values)

    name_signal = (0.6 * fuzzy_similarity(source.normalized_name, target.normalized_name)) + (
        0.4 * jaccard_similarity(source_tokens, target_tokens)
    )
    semantic_signal = jaccard_similarity(source_semantic, target_semantic)
    knowledge_signal = metadata_knowledge_service.knowledge_alignment(
        source,
        target,
        prefer_metadata_text=description_priority,
    )
    canonical_signal = metadata_knowledge_service.canonical_alignment(
        source,
        target,
        prefer_metadata_text=description_priority,
    )
    pattern_signal = jaccard_similarity(source_patterns, target_patterns)
    stat_signal = (
        score_distance(source.unique_ratio, target.unique_ratio)
        + score_distance(source.null_ratio, target.null_ratio)
        + score_distance(min(source.avg_length, 50) / 50, min(target.avg_length, 50) / 50)
    ) / 3
    overlap_signal = sample_overlap_score(source_values, target_values)
    embedding_signal = embedding_similarity(
        source,
        target,
        target_embedding_cache=target_embedding_cache,
    )
    correction_feedback = correction_store.describe_feedback(source.name, target.name)
    correction_signal = float(correction_feedback["strength"])

    active_signal_names = {
        "name",
        "semantic",
        "knowledge",
        "canonical",
        "pattern",
        "statistical",
    }
    if source_values and target_values:
        active_signal_names.add("overlap")
    if embedding_enabled():
        active_signal_names.add("embedding")
    if any(
        int(correction_feedback[key]) > 0
        for key in (
            "accepted_matches",
            "rejected_targets",
            "overridden_away",
            "promoted_preferred_rules",
            "promoted_rejected_rules",
            "promoted_overridden_away_rules",
        )
    ):
        active_signal_names.add("correction")

    if is_strong_canonical_concept_match(target, knowledge_signal, canonical_signal):
        # Virtual canonical targets represent normalized business concepts rather than
        # physical field labels, so weak lexical/pattern alignment should not dilute
        # a strong concept lock.
        active_signal_names.discard("name")
        if not target_patterns or source_patterns.isdisjoint(target_patterns):
            active_signal_names.discard("pattern")

    return (
        ScoringSignals(
            name=round(clamp_score(name_signal), 4),
            semantic=round(clamp_score(semantic_signal), 4),
            knowledge=round(clamp_score(knowledge_signal), 4),
            canonical=round(clamp_score(canonical_signal), 4),
            pattern=round(clamp_score(pattern_signal), 4),
            statistical=round(clamp_score(stat_signal), 4),
            overlap=round(clamp_score(overlap_signal), 4),
            embedding=round(clamp_score(embedding_signal), 4),
            correction=round(correction_signal, 4),
            llm=0.0,
        ),
        active_signal_names,
    )


def is_strong_canonical_concept_match(target: ColumnProfile, knowledge_signal: float, canonical_signal: float) -> bool:
    """Return whether a target is locked by strong canonical concept evidence."""

    resolved_concept_id = metadata_knowledge_service.resolve_canonical_concept_id(target.name)
    if resolved_concept_id != target.name:
        return False
    return knowledge_signal >= 0.85 and canonical_signal >= 0.6


def compute_final_score(
    signals: ScoringSignals,
    active_signal_names: set[str] | None = None,
    *,
    profile_name: str | None = None,
    source: ColumnProfile | None = None,
    target: ColumnProfile | None = None,
    source_sap_profile: SourceSapContextProfile | None = None,
) -> float:
    """Combine active scoring signals into the final normalized candidate score."""

    weights = resolve_scoring_weights(profile_name=profile_name)
    if active_signal_names is None:
        active_signal_names = {
            signal_name
            for signal_name in weights
            if float(getattr(signals, signal_name, 0.0) or 0.0) != 0.0
        }
    deemphasized_signal_names = strong_concept_lock_deemphasized_signals(signals, active_signal_names, source)
    if deemphasized_signal_names:
        active_signal_names = set(active_signal_names)
        active_signal_names.difference_update(deemphasized_signal_names)

    raw_score = (
        (signals.name * weights["name"] if "name" in active_signal_names else 0.0)
        + (signals.semantic * weights["semantic"] if "semantic" in active_signal_names else 0.0)
        + (signals.knowledge * weights["knowledge"] if "knowledge" in active_signal_names else 0.0)
        + (signals.canonical * weights["canonical"] if "canonical" in active_signal_names else 0.0)
        + (signals.pattern * weights["pattern"] if "pattern" in active_signal_names else 0.0)
        + (signals.statistical * weights["statistical"] if "statistical" in active_signal_names else 0.0)
        + (signals.overlap * weights["overlap"] if "overlap" in active_signal_names else 0.0)
        + (signals.embedding * weights["embedding"] if "embedding" in active_signal_names else 0.0)
        + (signals.correction * weights["correction"] if "correction" in active_signal_names else 0.0)
        + (signals.llm * weights["llm"] if "llm" in active_signal_names else 0.0)
    )
    active_total_weight = sum(weights[signal_name] for signal_name in active_signal_names)
    normalized_score = raw_score / active_total_weight if active_total_weight else 0.0
    if has_strong_identifier_consensus(signals, active_signal_names):
        return 1.0
    adjusted_score = clamp_score(normalized_score)
    if source is not None and target is not None:
        if source_sap_profile is None:
            source_sap_profile = build_source_sap_context_profile(source)
        adjusted_score = clamp_score(adjusted_score + compute_sap_confidence_boost(signals, source_sap_profile))
        adjusted_score = max(adjusted_score, sap_business_anchor_floor(source, signals))
    return round(clamp_score(adjusted_score), 4)


def should_deemphasize_name_signal(
    signals: ScoringSignals,
    active_signal_names: set[str],
    source: ColumnProfile | None,
) -> bool:
    """Return whether weak lexical name evidence should be excluded from the active score.

    This is intentionally narrow: only strong SAP source-anchor cases with an explicit
    semantic/knowledge/canonical concept lock qualify.
    """

    if source is None or "name" not in active_signal_names:
        return False
    if signals.name > settings.name_signal_deemphasis_max:
        return False
    required_signals = {"semantic", "knowledge", "canonical"}
    if not required_signals.issubset(active_signal_names):
        return False
    has_semantic_concept_lock = (
        signals.semantic >= settings.strong_concept_lock_min
        and signals.knowledge >= settings.strong_concept_lock_min
        and signals.canonical >= settings.strong_concept_lock_min
    )
    has_business_concept_lock = (
        signals.semantic >= 0.60
        and signals.knowledge >= 0.95
        and signals.canonical >= 0.75
    )
    return has_semantic_concept_lock or has_business_concept_lock


def strong_concept_lock_deemphasized_signals(
    signals: ScoringSignals,
    active_signal_names: set[str],
    source: ColumnProfile | None,
) -> set[str]:
    """Return the weak physical signals that should not dilute a strong concept lock."""

    if not should_deemphasize_name_signal(signals, active_signal_names, source):
        return set()

    deemphasized = {"name"}
    if "pattern" in active_signal_names and signals.pattern <= 0.2:
        deemphasized.add("pattern")
    if "overlap" in active_signal_names and signals.overlap <= 0.1:
        deemphasized.add("overlap")
    return deemphasized


def has_strong_sap_source_anchor(
    source: ColumnProfile,
    *,
    prefer_metadata_text: bool = False,
) -> bool:
    """Return whether the source field is explicitly recognized as a SAP field alias."""

    return any(
        match.strength >= 0.9 and any(context.system.upper() == "SAP" for context in match.contexts)
        for match in metadata_knowledge_service.match_concepts(source, prefer_metadata_text=prefer_metadata_text)
    )


def build_source_sap_context_profile(
    source: ColumnProfile,
    *,
    prefer_metadata_text: bool = False,
) -> SourceSapContextProfile:
    """Resolve reusable SAP context hints for one source field."""

    normalized_source_name = source.name.strip().lower()
    has_sap_table_field_context = False
    for match in metadata_knowledge_service.match_concepts(source, prefer_metadata_text=prefer_metadata_text):
        for context in match.contexts:
            if context.system.upper() != "SAP":
                continue
            if context.field_name.strip().lower() != normalized_source_name:
                continue
            has_sap_table_field_context = True

    exact_canonical_concept_id = metadata_knowledge_service.resolve_canonical_concept_id(source.name)
    if exact_canonical_concept_id == source.name:
        exact_canonical_concept_id = None

    # Confidence calibration is reserved for precise SAP technical-code fields
    # with explicit table+field context and an exact canonical concept resolution.
    is_sap_technical_code = source.name.isupper() and len(source.name) <= 10
    has_pir_table_field_context = (
        has_sap_table_field_context and exact_canonical_concept_id is not None and is_sap_technical_code
    )

    return SourceSapContextProfile(
        exact_canonical_concept_id=exact_canonical_concept_id,
        has_sap_table_field_context=has_sap_table_field_context,
        has_pir_table_field_context=has_pir_table_field_context,
    )


def compute_sap_confidence_boost(signals: ScoringSignals, sap_profile: SourceSapContextProfile | None) -> float:
    """Compute additive confidence boost from SAP field-context and exact-code evidence."""

    if sap_profile is None:
        return 0.0

    boost = 0.0
    if sap_profile.has_sap_table_field_context and signals.knowledge >= 0.65 and signals.canonical >= 0.45:
        boost = settings.sap_table_field_context_boost
        if sap_profile.has_pir_table_field_context and signals.knowledge >= 0.75 and signals.canonical >= 0.55:
            boost = settings.sap_pir_table_field_context_boost

    exact_code_boost = 0.0
    if sap_profile.exact_canonical_concept_id:
        if signals.canonical >= 0.85:
            exact_code_boost = settings.sap_exact_code_canonical_strong_boost
        elif signals.canonical >= 0.70 and signals.knowledge >= 0.60:
            exact_code_boost = settings.sap_exact_code_canonical_medium_boost
        elif sap_profile.has_pir_table_field_context and signals.canonical >= 0.55 and signals.knowledge >= 0.55:
            exact_code_boost = settings.sap_exact_code_canonical_pir_boost

    return boost + exact_code_boost


def is_sap_pir_slice_source(source: ColumnProfile) -> bool:
    """Return whether this source column belongs to the SAP PIR mapping slice."""

    sap_profile = build_source_sap_context_profile(source, prefer_metadata_text=True)
    return sap_profile.has_pir_table_field_context


def is_sap_anchor_preserved(signals: ScoringSignals) -> bool:
    """Return whether a candidate has enough business evidence to preserve a SAP anchor."""

    return signals.knowledge >= 0.75 or signals.canonical >= 0.6


def sap_business_anchor_floor(source: ColumnProfile, signals: ScoringSignals) -> float:
    """Return the minimum score preserved for strong SAP business matches."""

    if not has_strong_sap_source_anchor(source):
        return 0.0
    if not is_sap_anchor_preserved(signals):
        return 0.0

    business_anchor = max(
        signals.knowledge,
        (0.85 * signals.knowledge) + (0.15 * signals.canonical),
        (0.70 * signals.knowledge) + (0.30 * signals.canonical),
    )
    return clamp_score(business_anchor - settings.sap_business_signal_max_dilution)


def has_strong_identifier_consensus(
    signals: ScoringSignals,
    active_signal_names: set[str] | None = None,
) -> bool:
    """Return whether business, value, pattern, and LLM evidence all align strongly."""

    if active_signal_names is None:
        active_signal_names = {
            signal_name
            for signal_name in SIGNAL_WEIGHT_NAMES
            if float(getattr(signals, signal_name, 0.0) or 0.0) != 0.0
        }

    has_business_consensus = (
        ("knowledge" in active_signal_names and signals.knowledge >= 0.95)
        or ("canonical" in active_signal_names and signals.canonical >= 0.75)
    )
    has_value_consensus = (
        "overlap" in active_signal_names
        and signals.overlap >= 0.95
        and "statistical" in active_signal_names
        and signals.statistical >= 0.95
    )
    has_pattern_consensus = "pattern" not in active_signal_names or signals.pattern >= 0.95
    has_llm_consensus = "llm" in active_signal_names and signals.llm >= settings.strong_identifier_llm_min_confidence
    return has_business_consensus and has_value_consensus and has_pattern_consensus and has_llm_consensus


def sample_overlap_score(source_values: set[str], target_values: set[str]) -> float:
    """Compute simple sample-value overlap between source and target distinct values."""

    if not source_values or not target_values:
        return 0.0
    return len(source_values & target_values) / max(len(source_values), len(target_values), 1)


def embedding_similarity(
    source: ColumnProfile,
    target: ColumnProfile,
    *,
    target_embedding_cache: dict[str, list[float] | None] | None = None,
) -> float:
    """Compute embedding similarity for a source-target pair when embeddings are enabled."""

    if not embedding_enabled():
        return 0.0
    source_embedding = get_embedding(source.normalized_name)
    if target_embedding_cache is None:
        target_embedding = get_embedding(target.normalized_name)
    else:
        target_embedding = target_embedding_cache.get(target.normalized_name)
        if target.normalized_name not in target_embedding_cache:
            target_embedding = get_embedding(target.normalized_name)
            target_embedding_cache[target.normalized_name] = target_embedding
    return cosine_similarity(source_embedding, target_embedding)


def assign_unique_targets(per_source_scores: dict[str, list[CandidateScore]]) -> dict[str, CandidateScore]:
    """Choose one final target per source while keeping target assignment unique across the schema."""

    source_names = list(per_source_scores)
    if not source_names:
        return {}

    target_names = list(
        dict.fromkeys(
            score.target.name
            for rankings in per_source_scores.values()
            for score in rankings
        )
    )
    if not target_names:
        return {}

    source_count = len(source_names)
    target_count = len(target_names)
    matrix_size = max(source_count, target_count)
    target_index = {name: index for index, name in enumerate(target_names, start=1)}
    score_lookup: dict[tuple[str, str], CandidateScore] = {}
    max_weight = 0.0
    weights = [[0.0] * (matrix_size + 1) for _ in range(matrix_size + 1)]

    for row_index, source_name in enumerate(source_names, start=1):
        for score in per_source_scores[source_name]:
            column_index = target_index[score.target.name]
            weight = assignment_weight(score)
            weights[row_index][column_index] = weight
            score_lookup[(source_name, score.target.name)] = score
            max_weight = max(max_weight, weight)

    costs = [[0.0] * (matrix_size + 1) for _ in range(matrix_size + 1)]
    for row_index in range(1, matrix_size + 1):
        for column_index in range(1, matrix_size + 1):
            costs[row_index][column_index] = max_weight - weights[row_index][column_index]

    assignment = solve_min_cost_assignment(costs)
    assigned_by_source: dict[str, CandidateScore] = {}
    for row_index, source_name in enumerate(source_names, start=1):
        column_index = assignment[row_index]
        if column_index < 1 or column_index > target_count:
            continue
        target_name = target_names[column_index - 1]
        selected = score_lookup.get((source_name, target_name))
        if selected is not None:
            assigned_by_source[source_name] = selected

    return assigned_by_source


def assignment_weight(score: CandidateScore) -> float:
    """Return the global-assignment objective weight for one source-target edge."""

    return (
        float(score.score)
        + (0.000001 if score.llm_selected else 0.0)
        + (float(score.signals.canonical) * 0.0000001)
        + (float(score.signals.semantic) * 0.00000001)
    )


def solve_min_cost_assignment(costs: list[list[float]]) -> list[int]:
    """Solve a square assignment matrix with the Hungarian algorithm."""

    size = len(costs) - 1
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)

    for row in range(1, size + 1):
        p[0] = row
        minv = [float("inf")] * (size + 1)
        used = [False] * (size + 1)
        column = 0
        while True:
            used[column] = True
            row0 = p[column]
            delta = float("inf")
            next_column = 0
            for candidate_column in range(1, size + 1):
                if used[candidate_column]:
                    continue
                cur = costs[row0][candidate_column] - u[row0] - v[candidate_column]
                if cur < minv[candidate_column]:
                    minv[candidate_column] = cur
                    way[candidate_column] = column
                if minv[candidate_column] < delta:
                    delta = minv[candidate_column]
                    next_column = candidate_column
            for candidate_column in range(size + 1):
                if used[candidate_column]:
                    u[p[candidate_column]] += delta
                    v[candidate_column] -= delta
                else:
                    minv[candidate_column] -= delta
            column = next_column
            if p[column] == 0:
                break
        while True:
            next_column = way[column]
            p[column] = p[next_column]
            column = next_column
            if column == 0:
                break

    assignment = [0] * (size + 1)
    for column in range(1, size + 1):
        assignment[p[column]] = column
    return assignment


def build_candidate_option(score: CandidateScore) -> CandidateOption:
    """Convert an internal CandidateScore into the API-facing candidate option model."""

    return CandidateOption(
        target=score.target.name,
        confidence=round(score.score, 4),
        confidence_label=score_to_label(score.score, source=score.source),
        method="multi_signal_heuristic",
        signals=score.signals,
        explanation=list(score.explanation),
        canonical_details=score.canonical_details,
    )


def build_selected_mapping(
    source_name: str,
    score: CandidateScore,
    status: str,
    extra_explanation: list[str],
    alternatives: list[str],
    llm_result: LLMValidationResult | None = None,
    considered_targets: list[str] | None = None,
) -> MappingCandidate:
    """Convert an internal chosen candidate into the persisted MappingCandidate model."""

    return MappingCandidate(
        source=source_name,
        target=score.target.name,
        confidence=round(score.score, 4),
        confidence_label=score_to_label(score.score, source=score.source),
        status=status,
        method="llm_validated" if score.llm_selected else "multi_signal_heuristic",
        signals=score.signals,
        explanation=list(score.explanation) + extra_explanation,
        canonical_details=score.canonical_details,
        alternatives=alternatives,
        llm_consulted=llm_result is not None,
        llm_recommendation=llm_result,
        llm_decision_proposition=build_llm_decision_proposition(
            llm_result,
            final_target=score.target.name,
            considered_targets=considered_targets or [score.target.name],
        ),
    )


def build_llm_decision_proposition(
    llm_result: LLMValidationResult | None,
    *,
    final_target: str | None,
    considered_targets: list[str],
) -> LLMDecisionProposition | None:
    """Build a structured summary of how the LLM recommendation related to the final decision."""

    if llm_result is None:
        return None

    proposed_target = None if llm_result.selected_target == "no_match" else llm_result.selected_target
    aligns_with_final = proposed_target == final_target if proposed_target is not None else final_target is None
    if llm_result.selected_target == "no_match":
        proposition_type = "no_match"
        summary = "LLM proposes that no candidate in the closed set should be selected."
    elif aligns_with_final:
        proposition_type = "confirm"
        summary = f"LLM supports the final target '{final_target}'."
    else:
        proposition_type = "challenge"
        summary = (
            f"LLM proposed '{proposed_target}', but the final selected target is '{final_target}'."
            if final_target
            else f"LLM proposed '{proposed_target}', but no final target was selected."
        )

    rejected_targets = [target_name for target_name in considered_targets if target_name != proposed_target]
    return LLMDecisionProposition(
        proposition_type=proposition_type,
        proposed_target=proposed_target,
        final_target=final_target,
        confidence=round(llm_result.confidence, 4),
        reasoning=list(llm_result.reasoning),
        considered_targets=list(considered_targets),
        rejected_targets=rejected_targets,
        aligns_with_final=aligns_with_final,
        applied_to_final_decision=aligns_with_final,
        summary=summary,
    )


def log_decision(
    source_name: str,
    rankings: list[CandidateScore],
    llm_result: LLMValidationResult | None,
    selected: MappingCandidate,
) -> None:
    """Append one decision-log record for an evaluated source field."""

    decision_log_store.append(
        DecisionLogEntry(
            source=source_name,
            candidate_targets=[candidate.target.name for candidate in rankings],
            heuristic_scores={candidate.target.name: candidate.score for candidate in rankings},
            llm_result=llm_result,
            final_target=selected.target,
            final_status=selected.status,
            used_llm=llm_result is not None,
        )
    )


def format_signal_breakdown(signals: ScoringSignals) -> str:
    """Format one scoring-signal bundle into the explanation-line breakdown string."""

    label_overrides = {"statistical": "stat"}
    parts = []
    for signal_name, signal_value in signals.model_dump().items():
        label = label_overrides.get(signal_name, signal_name)
        parts.append(f"{label}={signal_value:.2f}")
    return "Signal breakdown: " + ", ".join(parts) + "."


def refresh_signal_breakdown(explanation: list[str], signals: ScoringSignals) -> None:
    """Refresh or append the signal-breakdown line inside a candidate explanation."""

    breakdown = format_signal_breakdown(signals)
    for index, line in enumerate(explanation):
        if line.startswith("Signal breakdown:"):
            explanation[index] = breakdown
            return
    explanation.append(breakdown)


def build_explanation(
    source: ColumnProfile,
    target: ColumnProfile,
    signals: ScoringSignals,
    *,
    description_priority: bool = False,
) -> list[str]:
    """Build the human-readable explanation lines that accompany a scored candidate."""

    explanation: list[str] = []
    correction_feedback = correction_store.describe_feedback(source.name, target.name)

    if is_strong_canonical_concept_match(target, signals.knowledge, signals.canonical):
        explanation.append(
            "Strong canonical concept lock detected; concept evidence outweighs weak physical field-name similarity in this candidate."
        )
    if signals.pattern >= 0.8 and source.detected_patterns:
        explanation.append(
            f"Strong pattern alignment: source {', '.join(source.detected_patterns)} matches target {', '.join(target.detected_patterns)}."
        )
    if signals.semantic >= 0.6:
        explanation.append("Semantic tokens align after abbreviation expansion and synonym enrichment.")
    if description_priority and (source.description or source.declared_type):
        explanation.append(
            "Description-priority mode injected source description/type metadata into semantic and concept matching for this candidate."
        )
    if signals.knowledge > 0:
        explanation.extend(
            metadata_knowledge_service.explain_alignment(
                source,
                target,
                prefer_metadata_text=description_priority,
            )
        )
    if signals.canonical > 0:
        explanation.extend(
            metadata_knowledge_service.explain_canonical_alignment(
                source,
                target,
                prefer_metadata_text=description_priority,
            )
        )
    if signals.name >= 0.75:
        explanation.append("Field names are lexically very similar.")
    if signals.overlap > 0:
        explanation.append(f"Sample overlap detected across representative values ({signals.overlap:.2f}).")
    if signals.statistical >= 0.7:
        explanation.append("Null ratio, uniqueness, and average length are compatible.")
    if signals.embedding >= 0.65:
        explanation.append("Embedding similarity reinforces the candidate after semantic normalization.")
    elif embedding_enabled():
        explanation.append("Embedding signal was evaluated but remained weaker than the heuristic signals.")
    if correction_feedback["promoted_preferred_rules"] > 0:
        explanation.append(
            "Reusable rule influenced this ranking "
            f"(promoted rules={correction_feedback['promoted_preferred_rules']})."
        )
    elif (
        correction_feedback["promoted_rejected_rules"] > 0
        or correction_feedback["promoted_overridden_away_rules"] > 0
    ):
        explanation.append(
            "Reusable rule penalized this candidate "
            f"(rejected_rules={correction_feedback['promoted_rejected_rules']}, "
            f"alternative_away_rules={correction_feedback['promoted_overridden_away_rules']})."
        )
    if signals.correction > 0:
        explanation.append(
            "Similar past decision influenced this ranking "
            f"(historical confirmation strength {signals.correction:.2f}; "
            f"accepted={correction_feedback['accepted_matches']})."
        )
    elif signals.correction < 0:
        explanation.append(
            "Historical review history penalized this candidate "
            f"(historical confirmation strength {signals.correction:.2f}; "
            f"rejected={correction_feedback['rejected_targets']}, "
            f"alternative_away={correction_feedback['overridden_away']})."
        )
    if not explanation:
        explanation.append("Weak heuristic match; review recommended.")

    explanation.append(format_signal_breakdown(signals))
    explanation.append(f"Candidate target: {target.name}.")
    return explanation


def score_to_label(score: float, *, source: ColumnProfile | None = None) -> str:
    """Map a numeric confidence score into Semantra's confidence label buckets."""

    high_threshold = settings.high_confidence_threshold
    medium_threshold = settings.medium_confidence_threshold
    if source is not None and is_sap_pir_slice_source(source):
        high_threshold = settings.sap_pir_high_confidence_threshold
        medium_threshold = settings.sap_pir_medium_confidence_threshold

    if score >= high_threshold:
        return "high_confidence"
    if score >= medium_threshold:
        return "medium_confidence"
    return "low_confidence"


def label_to_status(score: float, *, source: ColumnProfile | None = None) -> str:
    """Map a numeric score into the default review status for auto-mapping results."""

    auto_accept_threshold = settings.auto_accept_threshold
    if source is not None and is_sap_pir_slice_source(source):
        auto_accept_threshold = settings.sap_pir_auto_accept_threshold

    if score >= auto_accept_threshold:
        return "accepted"
    return "needs_review"