from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings
from app.services.decision_log_service import decision_log_store
from app.services.evaluation_service import evaluate_cases
from app.services.llm_service import StaticLLMProvider, call_validator
from app.services.mapping_service import generate_mapping_candidates
from app.models.schema import ColumnProfile, SchemaProfile


def make_column(name: str, patterns: list[str], sample_values: list[str], unique_ratio: float = 1.0) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        normalized_name=name.replace("_", " "),
        dtype="object",
        null_ratio=0.0,
        unique_ratio=unique_ratio,
        avg_length=10.0,
        non_null_count=5,
        sample_values=sample_values,
        distinct_sample_values=sample_values,
        detected_patterns=patterns,
        tokenized_name=name.replace("_", " ").split(),
    )


def setup_function() -> None:
    decision_log_store.clear()


def test_llm_validator_accepts_only_closed_candidate_set_json() -> None:
    provider = StaticLLMProvider(
        '{"selected_target":"phone_number","confidence":0.81,"reasoning":["pattern fits phone data"]}'
    )

    result = call_validator(
        source_field={"name": "cust_ref", "sample_values": ["0641234567"], "pattern": ["phone"], "unique_ratio": 1.0},
        candidate_targets=[
            {"name": "customer_id", "pattern": ["numeric_id"]},
            {"name": "phone_number", "pattern": ["phone"]},
        ],
        provider=provider,
    )

    assert result is not None
    assert result.selected_target == "phone_number"


def test_llm_validator_rejects_hallucinated_target() -> None:
    provider = StaticLLMProvider(
        '{"selected_target":"invented_field","confidence":0.91,"reasoning":["wrong target"]}'
    )

    result = call_validator(
        source_field={"name": "cust_ref", "sample_values": ["0641234567"], "pattern": ["phone"], "unique_ratio": 1.0},
        candidate_targets=[
            {"name": "customer_id", "pattern": ["numeric_id"]},
            {"name": "phone_number", "pattern": ["phone"]},
        ],
        provider=provider,
    )

    assert result is None


def test_mapping_uses_llm_validator_only_in_ambiguity_band_and_logs_decision() -> None:
    previous_bounds = (settings.llm_gate_min_score, settings.llm_gate_max_score)
    settings.llm_gate_min_score = 0.0
    settings.llm_gate_max_score = 1.0
    try:
        provider = StaticLLMProvider(
            '{"selected_target":"phone_number","confidence":0.76,"reasoning":["sample values look like phones"]}'
        )
        source_schema = SchemaProfile(
            dataset_id="source",
            dataset_name="source.csv",
            row_count=5,
            columns=[make_column("cust_ref", ["phone"], ["0641234567", "0659998888"])],
        )
        target_schema = SchemaProfile(
            dataset_id="target",
            dataset_name="target.csv",
            row_count=5,
            columns=[
                make_column("customer_id", ["numeric_id"], ["1", "2"]),
                make_column("phone_number", ["phone"], ["0641234567", "0659998888"]),
            ],
        )

        result = generate_mapping_candidates(source_schema, target_schema, llm_provider=provider)
        logs = decision_log_store.list_entries()

        assert result.mappings[0].method == "llm_validated"
        assert any("LLM validator" in line for line in result.mappings[0].explanation)
        assert len(logs) == 1
        assert logs[0].used_llm is True
        assert logs[0].llm_result is not None
    finally:
        settings.llm_gate_min_score, settings.llm_gate_max_score = previous_bounds


def test_evaluation_harness_reports_accuracy_and_bucket_metrics() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "mapping_gold.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    metrics = evaluate_cases(cases)

    assert metrics.total_cases == 3
    assert metrics.total_fields == 4
    assert metrics.accuracy >= 0.75
    assert set(metrics.confidence_by_bucket.keys()) == {"high_confidence", "medium_confidence", "low_confidence"}