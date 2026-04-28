from __future__ import annotations

from app.models.mapping import EvaluationMetrics
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.mapping_service import generate_mapping_candidates


def evaluate_cases(cases: list[dict], llm_provider=None) -> EvaluationMetrics:
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


def build_column_profile(column: dict) -> ColumnProfile:
    return ColumnProfile(
        name=column["name"],
        normalized_name=column.get("normalized_name", column["name"].replace("_", " ")),
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