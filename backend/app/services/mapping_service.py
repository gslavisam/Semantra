from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings
from app.models.mapping import (
    AutoMappingResponse,
    CandidateOption,
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
from app.utils.normalization import semantic_token_set
from app.utils.similarity import clamp_score, fuzzy_similarity, jaccard_similarity, score_distance


WEIGHTS = {
    "name": 0.20,
    "semantic": 0.18,
    "pattern": 0.20,
    "statistical": 0.15,
    "overlap": 0.10,
    "embedding": 0.12,
    "correction": 0.10,
    "llm": 0.05,
}


@dataclass
class CandidateScore:
    source: ColumnProfile
    target: ColumnProfile
    score: float
    signals: ScoringSignals
    explanation: list[str]
    llm_result: LLMValidationResult | None = None
    llm_selected: bool = False


def generate_mapping_candidates(
    source_schema: SchemaProfile,
    target_schema: SchemaProfile,
    llm_provider: LLMProvider | None = None,
    write_decision_log: bool = True,
) -> AutoMappingResponse:
    per_source_scores = {
        source_column.name: rank_targets_for_source(source_column, target_schema.columns)
        for source_column in source_schema.columns
    }

    llm_decisions = apply_llm_validation(per_source_scores, llm_provider)

    assigned_scores = assign_unique_targets(per_source_scores)
    selected_mappings: list[MappingCandidate] = []
    ranked_results: list[SourceMappingResult] = []

    for source_column in source_schema.columns:
        rankings = per_source_scores[source_column.name]
        selected_score = assigned_scores.get(source_column.name)
        candidate_options = [build_candidate_option(score) for score in rankings[: settings.top_k_candidates]]

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
                )
            )
            continue

        llm_result = llm_decisions.get(source_column.name)
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
            )
            ranked_results.append(
                SourceMappingResult(
                    source=source_column.name,
                    selected=selected,
                    candidates=candidate_options,
                )
            )
            selected_mappings.append(selected)
            if write_decision_log:
                log_decision(source_column.name, rankings[: settings.top_k_candidates], llm_result, selected)
            continue

        if selected_score is None:
            selected = build_selected_mapping(
                source_column.name,
                rankings[0],
                status="needs_review",
                extra_explanation=["No unique target was assigned by the global matching step; manual review required."],
                alternatives=[candidate.target.name for candidate in rankings[1:settings.top_k_candidates]],
            )
        else:
            extra_explanation: list[str] = []
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
            )

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

    return AutoMappingResponse(mappings=selected_mappings, ranked_mappings=ranked_results)


def rank_targets_for_source(source: ColumnProfile, targets: list[ColumnProfile]) -> list[CandidateScore]:
    scored: list[CandidateScore] = []
    for target in targets:
        signals = compute_signals(source, target)
        final_score = compute_final_score(signals)
        explanation = build_explanation(source, target, signals)
        scored.append(CandidateScore(source=source, target=target, score=final_score, signals=signals, explanation=explanation))
    return sorted(scored, key=lambda item: item.score, reverse=True)


def apply_llm_validation(
    per_source_scores: dict[str, list[CandidateScore]],
    llm_provider: LLMProvider | None,
) -> dict[str, LLMValidationResult]:
    llm_decisions: dict[str, LLMValidationResult] = {}

    if llm_provider is None:
        return llm_decisions

    for source_name, rankings in per_source_scores.items():
        if not rankings:
            continue
        top_score = rankings[0].score
        if top_score <= settings.llm_gate_min_score or top_score >= settings.llm_gate_max_score:
            continue

        candidate_scores = rankings[: settings.top_k_candidates]
        source_column = candidate_scores[0].source
        llm_result = call_validator(
            source_field={
                "name": source_column.name,
                "sample_values": source_column.sample_values,
                "pattern": source_column.detected_patterns,
                "unique_ratio": source_column.unique_ratio,
            },
            candidate_targets=[
                {
                    "name": candidate.target.name,
                    "pattern": candidate.target.detected_patterns,
                    "confidence": candidate.score,
                }
                for candidate in candidate_scores
            ],
            provider=llm_provider,
        )
        if llm_result is None:
            continue
        llm_decisions[source_name] = llm_result

        if llm_result.selected_target == "no_match":
            continue

        for candidate in candidate_scores:
            if candidate.target.name != llm_result.selected_target:
                continue
            candidate.signals.llm = round(llm_result.confidence, 4)
            candidate.score = compute_final_score(candidate.signals)
            candidate.llm_result = llm_result
            candidate.llm_selected = True
            candidate.explanation.extend(
                ["LLM validator re-ranked this candidate within the closed candidate set."]
                + [f"LLM: {reason}" for reason in llm_result.reasoning]
            )
            break

        rankings.sort(key=lambda item: (item.llm_selected, item.score), reverse=True)

    return llm_decisions


def compute_signals(source: ColumnProfile, target: ColumnProfile) -> ScoringSignals:
    source_tokens = set(source.tokenized_name)
    target_tokens = set(target.tokenized_name)
    source_semantic = semantic_token_set(source.name)
    target_semantic = semantic_token_set(target.name)
    source_patterns = set(source.detected_patterns)
    target_patterns = set(target.detected_patterns)
    source_values = set(source.distinct_sample_values)
    target_values = set(target.distinct_sample_values)

    name_signal = (0.6 * fuzzy_similarity(source.normalized_name, target.normalized_name)) + (
        0.4 * jaccard_similarity(source_tokens, target_tokens)
    )
    semantic_signal = jaccard_similarity(source_semantic, target_semantic)
    pattern_signal = jaccard_similarity(source_patterns, target_patterns)
    stat_signal = (
        score_distance(source.unique_ratio, target.unique_ratio)
        + score_distance(source.null_ratio, target.null_ratio)
        + score_distance(min(source.avg_length, 50) / 50, min(target.avg_length, 50) / 50)
    ) / 3
    overlap_signal = sample_overlap_score(source_values, target_values)
    embedding_signal = embedding_similarity(source, target)
    correction_signal = correction_store.get_feedback_adjustment(source.name, target.name)

    return ScoringSignals(
        name=round(clamp_score(name_signal), 4),
        semantic=round(clamp_score(semantic_signal), 4),
        pattern=round(clamp_score(pattern_signal), 4),
        statistical=round(clamp_score(stat_signal), 4),
        overlap=round(clamp_score(overlap_signal), 4),
        embedding=round(clamp_score(embedding_signal), 4),
        correction=round(correction_signal, 4),
        llm=0.0,
    )


def compute_final_score(signals: ScoringSignals) -> float:
    return round(
        (signals.name * WEIGHTS["name"])
        + (signals.semantic * WEIGHTS["semantic"])
        + (signals.pattern * WEIGHTS["pattern"])
        + (signals.statistical * WEIGHTS["statistical"])
        + (signals.overlap * WEIGHTS["overlap"])
        + (signals.embedding * WEIGHTS["embedding"])
        + (signals.correction * WEIGHTS["correction"])
        + (signals.llm * WEIGHTS["llm"]),
        4,
    )


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
            item[1].score,
            item[1].signals.pattern,
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
    )


def build_selected_mapping(
    source_name: str,
    score: CandidateScore,
    status: str,
    extra_explanation: list[str],
    alternatives: list[str],
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
        alternatives=alternatives,
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

    if signals.pattern >= 0.8 and source.detected_patterns:
        explanation.append(
            f"Strong pattern alignment: source {', '.join(source.detected_patterns)} matches target {', '.join(target.detected_patterns)}."
        )
    if signals.semantic >= 0.6:
        explanation.append("Semantic tokens align after abbreviation expansion and synonym enrichment.")
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
    if signals.correction > 0:
        explanation.append("Historical user corrections boost this candidate for the same source field.")
    elif signals.correction < 0:
        explanation.append("Historical user corrections penalize this candidate because it was corrected away before.")
    if not explanation:
        explanation.append("Weak heuristic match; review recommended.")

    explanation.append(
        "Signal breakdown: "
        f"name={signals.name:.2f}, semantic={signals.semantic:.2f}, pattern={signals.pattern:.2f}, "
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