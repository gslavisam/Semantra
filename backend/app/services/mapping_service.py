from __future__ import annotations

from dataclasses import dataclass, field
from collections.abc import Callable

from app.core.config import settings
from app.models.mapping import (
    AutoMappingResponse,
    CanonicalCoverageReport,
    CandidateOption,
    CanonicalMappingDetails,
    DecisionLogEntry,
    LLMValidationResult,
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


WEIGHTS = {
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
}

TOTAL_WEIGHT = sum(WEIGHTS.values())
STRONG_CANONICAL_LLM_MARGIN = 0.05
ProgressCallback = Callable[[str], None]


@dataclass
class CandidateScore:
    source: ColumnProfile
    target: ColumnProfile
    score: float
    signals: ScoringSignals
    explanation: list[str]
    active_signal_names: set[str] = field(default_factory=set)
    canonical_details: CanonicalMappingDetails = field(default_factory=CanonicalMappingDetails)
    llm_result: LLMValidationResult | None = None
    llm_selected: bool = False


def generate_mapping_candidates(
    source_schema: SchemaProfile,
    target_schema: SchemaProfile,
    llm_provider: LLMProvider | None = None,
    write_decision_log: bool = True,
    progress_callback: ProgressCallback | None = None,
) -> AutoMappingResponse:
    source_columns = list(source_schema.columns)
    target_columns = list(target_schema.columns)
    _emit_progress(
        progress_callback,
        f"Loaded {len(source_columns)} source fields and {len(target_columns)} target fields for mapping.",
    )
    per_source_scores: dict[str, list[CandidateScore]] = {}
    for index, source_column in enumerate(source_columns, start=1):
        _emit_progress(progress_callback, f"Ranking {index}/{len(source_columns)}: {source_column.name}.")
        per_source_scores[source_column.name] = rank_targets_for_source(source_column, target_columns)

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
                status=label_to_status(selected_score.score),
                extra_explanation=extra_explanation,
                alternatives=[
                    candidate.target.name
                    for candidate in rankings[: settings.top_k_candidates]
                    if candidate.target.name != selected_score.target.name
                ],
                llm_result=llm_result,
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

    source_canonical_coverage = metadata_knowledge_service.canonical_coverage(source_schema)
    target_canonical_coverage = metadata_knowledge_service.canonical_coverage(target_schema)
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
    )
    _emit_progress(progress_callback, "Mapping response assembled.")
    return response


def rank_targets_for_source(source: ColumnProfile, targets: list[ColumnProfile]) -> list[CandidateScore]:
    scored: list[CandidateScore] = []
    for target in targets:
        signals, active_signal_names = compute_signals(source, target)
        final_score = compute_final_score(signals, active_signal_names)
        explanation = build_explanation(source, target, signals)
        scored.append(
            CandidateScore(
                source=source,
                target=target,
                score=final_score,
                signals=signals,
                active_signal_names=active_signal_names,
                explanation=explanation,
                canonical_details=metadata_knowledge_service.canonical_mapping_details(source, target),
            )
        )
    return sorted(scored, key=lambda item: item.score, reverse=True)


def apply_llm_validation(
    per_source_scores: dict[str, list[CandidateScore]],
    llm_provider: LLMProvider | None,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, LLMValidationResult]:
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
            candidate.score = compute_final_score(candidate.signals, candidate.active_signal_names)
            candidate.llm_result = llm_result
            candidate.llm_selected = True
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
    except Exception:
        return


def should_run_llm_validation(rankings: list[CandidateScore]) -> bool:
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
        if (top_candidate.score - challenger.score) < STRONG_CANONICAL_LLM_MARGIN:
            return True
    return False


def should_run_canonical_semantic_rescue(top_candidate: CandidateScore) -> bool:
    if top_candidate.score >= settings.llm_gate_min_score or top_candidate.score < 0.2:
        return False
    if not is_canonical_target_name(top_candidate.target.name):
        return False
    if top_candidate.signals.semantic < 0.45:
        return False
    if top_candidate.signals.knowledge > 0 or top_candidate.signals.canonical > 0:
        return False
    return True


def is_canonical_target_name(target_name: str) -> bool:
    return metadata_knowledge_service.resolve_canonical_concept_id(target_name) == target_name


def compute_signals(source: ColumnProfile, target: ColumnProfile) -> tuple[ScoringSignals, set[str]]:
    source_tokens = set(source.tokenized_name)
    target_tokens = set(target.tokenized_name)
    source_semantic = semantic_token_set(source.name) | metadata_knowledge_service.expand_semantic_tokens(source)
    target_semantic = semantic_token_set(target.name) | metadata_knowledge_service.expand_semantic_tokens(target)
    source_patterns = set(source.detected_patterns)
    target_patterns = set(target.detected_patterns)
    source_values = set(source.distinct_sample_values)
    target_values = set(target.distinct_sample_values)

    name_signal = (0.6 * fuzzy_similarity(source.normalized_name, target.normalized_name)) + (
        0.4 * jaccard_similarity(source_tokens, target_tokens)
    )
    semantic_signal = jaccard_similarity(source_semantic, target_semantic)
    knowledge_signal = metadata_knowledge_service.knowledge_alignment(source, target)
    canonical_signal = metadata_knowledge_service.canonical_alignment(source, target)
    pattern_signal = jaccard_similarity(source_patterns, target_patterns)
    stat_signal = (
        score_distance(source.unique_ratio, target.unique_ratio)
        + score_distance(source.null_ratio, target.null_ratio)
        + score_distance(min(source.avg_length, 50) / 50, min(target.avg_length, 50) / 50)
    ) / 3
    overlap_signal = sample_overlap_score(source_values, target_values)
    embedding_signal = embedding_similarity(source, target)
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
            "overridden_matches",
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
    resolved_concept_id = metadata_knowledge_service.resolve_canonical_concept_id(target.name)
    if resolved_concept_id != target.name:
        return False
    return knowledge_signal >= 0.85 and canonical_signal >= 0.6


def compute_final_score(signals: ScoringSignals, active_signal_names: set[str] | None = None) -> float:
    if active_signal_names is None:
        active_signal_names = {
            signal_name
            for signal_name in WEIGHTS
            if float(getattr(signals, signal_name, 0.0) or 0.0) != 0.0
        }

    raw_score = (
        (signals.name * WEIGHTS["name"] if "name" in active_signal_names else 0.0)
        + (signals.semantic * WEIGHTS["semantic"] if "semantic" in active_signal_names else 0.0)
        + (signals.knowledge * WEIGHTS["knowledge"] if "knowledge" in active_signal_names else 0.0)
        + (signals.canonical * WEIGHTS["canonical"] if "canonical" in active_signal_names else 0.0)
        + (signals.pattern * WEIGHTS["pattern"] if "pattern" in active_signal_names else 0.0)
        + (signals.statistical * WEIGHTS["statistical"] if "statistical" in active_signal_names else 0.0)
        + (signals.overlap * WEIGHTS["overlap"] if "overlap" in active_signal_names else 0.0)
        + (signals.embedding * WEIGHTS["embedding"] if "embedding" in active_signal_names else 0.0)
        + (signals.correction * WEIGHTS["correction"] if "correction" in active_signal_names else 0.0)
        + (signals.llm * WEIGHTS["llm"] if "llm" in active_signal_names else 0.0)
    )
    active_total_weight = sum(WEIGHTS[signal_name] for signal_name in active_signal_names)
    normalized_score = raw_score / active_total_weight if active_total_weight else 0.0
    return round(clamp_score(normalized_score), 4)


def sample_overlap_score(source_values: set[str], target_values: set[str]) -> float:
    if not source_values or not target_values:
        return 0.0
    return len(source_values & target_values) / max(len(source_values), len(target_values), 1)


def embedding_similarity(source: ColumnProfile, target: ColumnProfile) -> float:
    if not embedding_enabled():
        return 0.0
    source_embedding = get_embedding(source.normalized_name)
    target_embedding = get_embedding(target.normalized_name)
    return cosine_similarity(source_embedding, target_embedding)


def assign_unique_targets(per_source_scores: dict[str, list[CandidateScore]]) -> dict[str, CandidateScore]:
    assigned_by_source: dict[str, CandidateScore] = {}
    assigned_targets: set[str] = set()

    all_edges = []
    for source_name, rankings in per_source_scores.items():
        for score in rankings:
            all_edges.append((source_name, score))

    all_edges.sort(
        key=lambda item: (
            item[1].llm_selected,
            item[1].score,
            item[1].signals.pattern,
            item[1].signals.canonical,
            item[1].signals.semantic,
            item[1].signals.embedding,
        ),
        reverse=True,
    )

    for source_name, score in all_edges:
        if source_name in assigned_by_source:
            continue
        if score.target.name in assigned_targets:
            continue
        assigned_by_source[source_name] = score
        assigned_targets.add(score.target.name)

    return assigned_by_source


def build_candidate_option(score: CandidateScore) -> CandidateOption:
    return CandidateOption(
        target=score.target.name,
        confidence=round(score.score, 4),
        confidence_label=score_to_label(score.score),
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
) -> MappingCandidate:
    return MappingCandidate(
        source=source_name,
        target=score.target.name,
        confidence=round(score.score, 4),
        confidence_label=score_to_label(score.score),
        status=status,
        method="llm_validated" if score.llm_selected else "multi_signal_heuristic",
        signals=score.signals,
        explanation=list(score.explanation) + extra_explanation,
        canonical_details=score.canonical_details,
        alternatives=alternatives,
        llm_consulted=llm_result is not None,
        llm_recommendation=llm_result,
    )


def log_decision(
    source_name: str,
    rankings: list[CandidateScore],
    llm_result: LLMValidationResult | None,
    selected: MappingCandidate,
) -> None:
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


def build_explanation(source: ColumnProfile, target: ColumnProfile, signals: ScoringSignals) -> list[str]:
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
    if signals.knowledge > 0:
        explanation.extend(metadata_knowledge_service.explain_alignment(source, target))
    if signals.canonical > 0:
        explanation.extend(metadata_knowledge_service.explain_canonical_alignment(source, target))
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
            f"overridden_away_rules={correction_feedback['promoted_overridden_away_rules']})."
        )
    if signals.correction > 0:
        explanation.append(
            "Similar past decision influenced this ranking "
            f"(historical confirmation strength {signals.correction:.2f}; "
            f"accepted={correction_feedback['accepted_matches']}, overridden={correction_feedback['overridden_matches']})."
        )
    elif signals.correction < 0:
        explanation.append(
            "Historical review history penalized this candidate "
            f"(historical confirmation strength {signals.correction:.2f}; "
            f"rejected={correction_feedback['rejected_targets']}, overridden_away={correction_feedback['overridden_away']})."
        )
    if not explanation:
        explanation.append("Weak heuristic match; review recommended.")

    explanation.append(
        "Signal breakdown: "
        f"name={signals.name:.2f}, semantic={signals.semantic:.2f}, knowledge={signals.knowledge:.2f}, canonical={signals.canonical:.2f}, pattern={signals.pattern:.2f}, "
        f"stat={signals.statistical:.2f}, overlap={signals.overlap:.2f}, embedding={signals.embedding:.2f}, correction={signals.correction:.2f}."
    )
    explanation.append(f"Candidate target: {target.name}.")
    return explanation


def score_to_label(score: float) -> str:
    if score >= settings.high_confidence_threshold:
        return "high_confidence"
    if score >= settings.medium_confidence_threshold:
        return "medium_confidence"
    return "low_confidence"


def label_to_status(score: float) -> str:
    label = score_to_label(score)
    if label == "high_confidence":
        return "accepted"
    return "needs_review"