"""Benchmark evaluation, scoring-profile comparison, and correction-impact logic."""

from __future__ import annotations

from contextlib import contextmanager

from app.core.config import settings
from app.models.mapping import CorrectionImpactMetrics, EvaluationMetrics, ScoringProfileComparisonResponse, ScoringProfileMetrics
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.correction_service import correction_store
from app.services.mapping_service import DEFAULT_SCORING_PROFILE, SCORING_PROFILES, generate_mapping_candidates, normalize_scoring_profile_name, resolve_scoring_weights


@contextmanager
def scoring_profile_context(profile_name: str, weight_overrides: dict[str, float] | None = None):
    """Temporarily switch the active scoring profile and weight overrides for evaluation runs."""

    normalized_profile = normalize_scoring_profile_name(profile_name)
    resolve_scoring_weights(normalized_profile, weight_overrides or {})
    previous_profile = settings.scoring_profile
    previous_overrides = dict(settings.scoring_weight_overrides)
    try:
        settings.scoring_profile = normalized_profile
        settings.scoring_weight_overrides = dict(weight_overrides or {})
        yield
    finally:
        settings.scoring_profile = previous_profile
        settings.scoring_weight_overrides = previous_overrides


def evaluate_cases(cases: list[dict], llm_provider=None) -> EvaluationMetrics:
    """Evaluate benchmark cases against the current mapping configuration."""

    total_cases = len(cases)
    total_fields = 0
    correct_matches = 0
    top1_correct = 0
    bucket_totals = {"high_confidence": 0, "medium_confidence": 0, "low_confidence": 0}
    bucket_correct = {"high_confidence": 0, "medium_confidence": 0, "low_confidence": 0}

    for case in cases:
        source_schema = SchemaProfile(
            dataset_id="eval-source",
            dataset_name="eval-source.csv",
            row_count=case.get("row_count", 5),
            columns=[build_column_profile(column) for column in case["source_columns"]],
        )
        target_schema = SchemaProfile(
            dataset_id="eval-target",
            dataset_name="eval-target.csv",
            row_count=case.get("row_count", 5),
            columns=[build_column_profile(column) for column in case["target_columns"]],
        )
        ground_truth = case["ground_truth"]
        result = generate_mapping_candidates(source_schema, target_schema, llm_provider=llm_provider)

        for mapping in result.mappings:
            total_fields += 1
            expected_target = ground_truth.get(mapping.source)
            bucket_totals[mapping.confidence_label] += 1
            if mapping.target == expected_target:
                correct_matches += 1
                bucket_correct[mapping.confidence_label] += 1

        for ranked in result.ranked_mappings:
            if not ranked.candidates:
                continue
            expected_target = ground_truth.get(ranked.source)
            if ranked.candidates[0].target == expected_target:
                top1_correct += 1

    confidence_by_bucket = {
        bucket: round(bucket_correct[bucket] / bucket_totals[bucket], 4) if bucket_totals[bucket] else 0.0
        for bucket in bucket_totals
    }

    accuracy = round(correct_matches / total_fields, 4) if total_fields else 0.0
    top1_accuracy = round(top1_correct / total_fields, 4) if total_fields else 0.0
    return EvaluationMetrics(
        total_cases=total_cases,
        total_fields=total_fields,
        correct_matches=correct_matches,
        top1_accuracy=top1_accuracy,
        accuracy=accuracy,
        confidence_by_bucket=confidence_by_bucket,
    )


def evaluate_correction_impact(cases: list[dict], llm_provider=None) -> CorrectionImpactMetrics:
    """Compare baseline and correction-aware benchmark performance on the same cases."""

    with correction_store.feedback_disabled():
        baseline = evaluate_cases(cases, llm_provider=llm_provider)

    correction_aware = evaluate_cases(cases, llm_provider=llm_provider)

    return CorrectionImpactMetrics(
        baseline=baseline,
        correction_aware=correction_aware,
        accuracy_delta=round(correction_aware.accuracy - baseline.accuracy, 4),
        top1_accuracy_delta=round(correction_aware.top1_accuracy - baseline.top1_accuracy, 4),
        correct_matches_delta=correction_aware.correct_matches - baseline.correct_matches,
    )


def evaluate_cases_for_profile(
    cases: list[dict],
    profile_name: str,
    *,
    llm_provider=None,
    weight_overrides: dict[str, float] | None = None,
) -> EvaluationMetrics:
    """Evaluate benchmark cases under one named scoring profile and optional weight overrides."""

    with scoring_profile_context(profile_name, weight_overrides):
        return evaluate_cases(cases, llm_provider=llm_provider)


def compare_scoring_profiles(
    cases: list[dict],
    *,
    profile_names: list[str] | None = None,
    llm_provider=None,
) -> dict[str, EvaluationMetrics]:
    """Evaluate the same benchmark cases across multiple scoring profiles."""

    resolved_profile_names = [normalize_scoring_profile_name(name) for name in (profile_names or list(SCORING_PROFILES.keys()))]
    comparison: dict[str, EvaluationMetrics] = {}
    for profile_name in resolved_profile_names:
        comparison[profile_name] = evaluate_cases_for_profile(cases, profile_name, llm_provider=llm_provider)
    return comparison


def recommend_scoring_profile(comparison: dict[str, EvaluationMetrics]) -> tuple[str | None, str]:
    """Choose the best default scoring profile from a comparison result and explain why."""

    if not comparison:
        return None, "No scoring profiles were compared."

    ranked_profiles = sorted(
        comparison.items(),
        key=lambda item: (
            item[1].accuracy,
            item[1].top1_accuracy,
            item[1].correct_matches,
            item[0] == DEFAULT_SCORING_PROFILE,
        ),
        reverse=True,
    )
    top_name, top_metrics = ranked_profiles[0]
    ties = [
        name
        for name, metrics in ranked_profiles
        if metrics.accuracy == top_metrics.accuracy
        and metrics.top1_accuracy == top_metrics.top1_accuracy
        and metrics.correct_matches == top_metrics.correct_matches
    ]
    if len(ties) == 1:
        return top_name, f"Unique best profile on this benchmark: {top_name}."
    if DEFAULT_SCORING_PROFILE in ties:
        return DEFAULT_SCORING_PROFILE, (
            "No decisive benchmark winner across compared profiles; keep balanced as the default because it ties "
            "for best metrics and preserves existing behavior."
        )
    return None, "No decisive benchmark winner across compared profiles; choose based on scenario rather than fixture-only metrics."


def build_scoring_profile_comparison_response(
    cases: list[dict],
    *,
    profile_names: list[str] | None = None,
    llm_provider=None,
) -> ScoringProfileComparisonResponse:
    """Build the API response used to compare and recommend scoring profiles."""

    comparison = compare_scoring_profiles(cases, profile_names=profile_names, llm_provider=llm_provider)
    recommended_profile, recommendation_reason = recommend_scoring_profile(comparison)
    return ScoringProfileComparisonResponse(
        profiles=[
            ScoringProfileMetrics(
                profile=profile_name,
                total_cases=metrics.total_cases,
                total_fields=metrics.total_fields,
                correct_matches=metrics.correct_matches,
                top1_accuracy=metrics.top1_accuracy,
                accuracy=metrics.accuracy,
                confidence_by_bucket=dict(metrics.confidence_by_bucket),
            )
            for profile_name, metrics in comparison.items()
        ],
        recommended_profile=recommended_profile,
        recommendation_reason=recommendation_reason,
    )


def build_column_profile(column: dict) -> ColumnProfile:
    """Build a synthetic ColumnProfile from serialized benchmark fixture data."""

    return ColumnProfile(
        name=column["name"],
        normalized_name=column.get("normalized_name", column["name"].replace("_", " ")),
        description=column.get("description", ""),
        declared_type=column.get("declared_type", ""),
        dtype=column.get("dtype", "object"),
        null_ratio=column.get("null_ratio", 0.0),
        unique_ratio=column.get("unique_ratio", 1.0),
        avg_length=column.get("avg_length", 10.0),
        non_null_count=column.get("non_null_count", 5),
        sample_values=column.get("sample_values", []),
        distinct_sample_values=column.get("distinct_sample_values", column.get("sample_values", [])),
        detected_patterns=column.get("detected_patterns", []),
        tokenized_name=column.get("tokenized_name", column["name"].replace("_", " ").split()),
    )