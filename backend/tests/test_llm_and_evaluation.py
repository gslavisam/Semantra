from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import settings
from app.models.mapping import ScoringSignals
from app.services.decision_log_service import decision_log_store
from app.services.evaluation_service import compare_scoring_profiles, evaluate_cases, evaluate_cases_for_profile
from app.services.llm_service import (
    StaticLLMProvider,
    build_transformation_generator_prompt,
    build_validator_prompt,
    call_transformation_generator,
    call_validator,
)
from app.services.mapping_service import CandidateScore, generate_mapping_candidates, should_run_canonical_semantic_rescue, should_run_llm_validation
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.spec_upload_service import parse_spec_payload
from app.services.virtual_target_service import build_virtual_target_schema


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


def test_llm_validator_accepts_markdown_fenced_json() -> None:
    provider = StaticLLMProvider(
        '```json\n{"selected_target":"no_match","confidence":0.0,"reasoning":["No good candidate in the closed set."]}\n```'
    )

    result = call_validator(
        source_field={"name": "LAND1", "sample_values": [], "pattern": ["text"], "unique_ratio": 0.0},
        candidate_targets=[
            {"name": "customer.phone", "pattern": ["phone"]},
            {"name": "address.postal_code", "pattern": []},
        ],
        provider=provider,
    )

    assert result is not None
    assert result.selected_target == "no_match"


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


def test_llm_validator_logs_classified_failures(caplog: pytest.LogCaptureFixture) -> None:
    provider = StaticLLMProvider("not-json")

    with caplog.at_level("WARNING"):
        result = call_validator(
            source_field={"name": "cust_ref", "sample_values": ["0641234567"], "pattern": ["phone"], "unique_ratio": 1.0},
            candidate_targets=[
                {"name": "customer_id", "pattern": ["numeric_id"]},
                {"name": "phone_number", "pattern": ["phone"]},
            ],
            provider=provider,
            max_retries=1,
        )

    assert result is None
    assert "invalid_json" in caplog.text


def test_llm_transformation_logs_classified_failures(caplog: pytest.LogCaptureFixture) -> None:
    provider = StaticLLMProvider("not-json")

    with caplog.at_level("WARNING"):
        result = call_transformation_generator(
            source_field={"name": "email", "sample_values": ["ana.markovic@example.com"], "pattern": ["email"]},
            target_field={"name": "customer_name", "sample_values": ["Ana Markovic"], "pattern": ["text"]},
            user_instruction="Extract the person's full name from the email address.",
            provider=provider,
            max_retries=1,
        )

    assert result is None
    assert "invalid_json" in caplog.text


def test_validator_prompt_includes_description_aware_context_with_guardrails() -> None:
    prompt = build_validator_prompt(
        source_field={
            "name": "AKONT",
            "description": "A" * 400,
            "declared_type": "CHAR(10)",
            "sample_values": ["1000", "2000", "3000", "4000", "5000", "6000"],
            "detected_patterns": ["categorical"],
            "unique_ratio": 0.8,
        },
        candidate_targets=[
            {
                "name": "reconciliation_account",
                "description": "General ledger reconciliation account used for vendor postings",
                "declared_type": "VARCHAR",
                "sample_values": ["100000", "200000"],
                "detected_patterns": ["categorical"],
                "confidence": 0.61,
            }
        ],
    )

    assert '"description_truncation": 280' in prompt
    assert '"sample_values_limit": 5' in prompt
    assert '"declared_type": "CHAR(10)"' in prompt
    assert '"name": "reconciliation_account"' in prompt
    assert '"6000"' not in prompt
    assert 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' in prompt
    assert ('A' * 320) not in prompt


def test_transformation_prompt_includes_description_aware_context() -> None:
    prompt = build_transformation_generator_prompt(
        source_field={
            "name": "ERDAT",
            "description": "SAP created-on date",
            "declared_type": "DATS",
            "sample_values": ["20240101"],
            "detected_patterns": ["date"],
        },
        target_field={
            "name": "document.created_date",
            "description": "Canonical document creation date",
            "declared_type": "date",
            "sample_values": ["2024-01-01"],
            "detected_patterns": ["date"],
        },
        user_instruction="Convert SAP DATS to ISO date.",
    )

    assert '"description": "SAP created-on date"' in prompt
    assert '"declared_type": "DATS"' in prompt
    assert '"name": "document.created_date"' in prompt


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
        breakdown = next(line for line in result.mappings[0].explanation if line.startswith("Signal breakdown:"))
        proposition = result.mappings[0].llm_decision_proposition

        assert result.mappings[0].method == "llm_validated"
        assert any("LLM validator" in line for line in result.mappings[0].explanation)
        assert "llm=0.76" in breakdown
        assert proposition is not None
        assert proposition.proposition_type == "confirm"
        assert proposition.proposed_target == "phone_number"
        assert proposition.applied_to_final_decision is True
        assert len(logs) == 1
        assert logs[0].used_llm is True
        assert logs[0].llm_result is not None
    finally:
        settings.llm_gate_min_score, settings.llm_gate_max_score = previous_bounds


def test_erdat_now_resolves_to_generic_created_date_without_llm() -> None:
    # Under the ERP glossary, ERDAT is modeled as a generic technical created date,
    # so it now resolves directly to document.created_date and bypasses LLM rescue.
    provider = StaticLLMProvider(
        '{"selected_target":"no_match","confidence":0.92,"reasoning":["ERDAT is a creation date field and no reliable date concept exists in the closed candidate set."]}'
    )
    fixture_path = Path(__file__).parents[2] / "ui_fixtures" / "source_schema_spec.csv"
    source_schema = parse_spec_payload(fixture_path.read_bytes(), fixture_path.name)

    result = generate_mapping_candidates(source_schema, build_virtual_target_schema("canonical"), llm_provider=provider)
    erdat = next(mapping for mapping in result.mappings if mapping.source == "ERDAT")
    logs = decision_log_store.list_entries()

    assert erdat.method == "multi_signal_heuristic"
    assert erdat.target == "document.created_date"
    assert erdat.signals.canonical == 1.0
    assert any(entry.source == "ERDAT" and entry.used_llm is False for entry in logs)


def test_strong_canonical_near_tie_still_uses_llm_arbitration() -> None:
    provider = StaticLLMProvider(
        '{"selected_target":"vendor.name","confidence":0.81,"reasoning":["NAME1 is ambiguous between customer and vendor naming concepts in the closed set."]}'
    )
    fixture_path = Path(__file__).parents[2] / "ui_fixtures" / "source_schema_spec.csv"
    source_schema = parse_spec_payload(fixture_path.read_bytes(), fixture_path.name)
    name1_column = next(column for column in source_schema.columns if column.name == "NAME1")
    single_column_schema = SchemaProfile(
        dataset_id="name1-only",
        dataset_name="name1_only.csv",
        row_count=source_schema.row_count,
        columns=[name1_column],
    )

    result = generate_mapping_candidates(single_column_schema, build_virtual_target_schema("canonical"), llm_provider=provider)
    name1 = result.mappings[0]
    logs = decision_log_store.list_entries()

    assert name1.source == "NAME1"
    assert name1.method == "llm_validated"
    assert name1.target == "vendor.name"
    assert any("LLM validator" in line for line in name1.explanation)
    assert any(entry.source == "NAME1" and entry.used_llm for entry in logs)


def test_canonical_rescue_gate_triggers_for_semantic_only_low_confidence_candidate() -> None:
    candidate = CandidateScore(
        source=make_column("supplier_label", ["text"], ["Supplier A", "Supplier B"]),
        target=make_column("vendor.name", ["text"], ["Vendor A", "Vendor B"]),
        score=0.34,
        signals=ScoringSignals(
            semantic=0.58,
            knowledge=0.0,
            canonical=0.0,
            statistical=0.32,
        ),
        explanation=[],
        active_signal_names={"semantic", "statistical"},
    )

    assert should_run_canonical_semantic_rescue(candidate) is True
    assert should_run_llm_validation([candidate]) is True


def test_llm_can_generate_transformation_code_from_user_instruction() -> None:
    provider = StaticLLMProvider(
        json.dumps(
            {
                "transformation_code": 'df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
                "reasoning": ["Extract local part", "Replace dots with spaces", "Title-case the result"],
            }
        )
    )

    result = call_transformation_generator(
        source_field={"name": "email", "sample_values": ["ana.markovic@example.com"], "pattern": ["email"]},
        target_field={"name": "customer_name", "sample_values": ["Ana Markovic"], "pattern": ["text"]},
        user_instruction="Extract the person's full name from the email address.",
        provider=provider,
    )

    assert result is not None
    assert 'df_source["email"]' in result.transformation_code
    assert result.reasoning == ["Extract local part", "Replace dots with spaces", "Title-case the result"]


def test_llm_override_is_explained_when_global_assignment_picks_a_different_target() -> None:
    customer = make_column("customer", ["text"], ["Acme North", "Contoso Trade"])
    customer_id = make_column("customer_id", ["text"], ["C0001", "C0002"])
    customer_segment = make_column("customer_segment", ["text"], ["A", "B"])

    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=2,
        columns=[
            make_column("LEGACY_CUST", ["text"], ["C0001", "C0002"]),
            make_column("purchaser", ["text"], ["Acme North", "Contoso Trade"]),
        ],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=2,
        columns=[customer, customer_id, customer_segment],
    )

    def fake_rankings(source_column, _targets, target_embedding_cache=None):
        if source_column.name == "LEGACY_CUST":
            return [
                CandidateScore(customer, customer, 0.6119, ScoringSignals(), [], set()),
                CandidateScore(customer, customer_id, 0.6102, ScoringSignals(), [], set()),
                CandidateScore(customer, customer_segment, 0.5615, ScoringSignals(), [], set()),
            ]
        return [
            CandidateScore(source_column, customer, 0.5723, ScoringSignals(), [], set()),
            CandidateScore(source_column, customer_id, 0.4334, ScoringSignals(), [], set()),
            CandidateScore(source_column, customer_segment, 0.4330, ScoringSignals(), [], set()),
        ]

    provider = StaticLLMProvider(
        lambda prompt: json.dumps(
            {
                "selected_target": "customer",
                "confidence": 0.6119 if "LEGACY_CUST" in prompt else 0.5723,
                "reasoning": ["LLM prefers the generic customer field."],
            }
        )
    )

    with patch("app.services.mapping_service.rank_targets_for_source", side_effect=fake_rankings):
        result = generate_mapping_candidates(source_schema, target_schema, llm_provider=provider)

    purchaser = next(mapping for mapping in result.mappings if mapping.source == "purchaser")

    assert purchaser.target == "customer_id"
    assert purchaser.llm_consulted is True
    assert purchaser.llm_recommendation is not None
    assert purchaser.llm_recommendation.selected_target == "customer"
    assert purchaser.llm_decision_proposition is not None
    assert purchaser.llm_decision_proposition.proposition_type == "challenge"
    assert purchaser.llm_decision_proposition.proposed_target == "customer"
    assert purchaser.llm_decision_proposition.final_target == "customer_id"
    assert purchaser.llm_decision_proposition.applied_to_final_decision is False
    assert any(
        "LLM validator preferred 'customer', but global one-to-one assignment selected this target instead." == line
        for line in purchaser.explanation
    )


def test_evaluation_harness_reports_accuracy_and_bucket_metrics() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "mapping_gold.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    metrics = evaluate_cases(cases)

    assert metrics.total_cases == 3
    assert metrics.total_fields == 4
    assert metrics.accuracy >= 0.75
    assert set(metrics.confidence_by_bucket.keys()) == {"high_confidence", "medium_confidence", "low_confidence"}


def test_evaluation_harness_keeps_deterministic_metrics_same_with_or_without_description_context() -> None:
    base_case = {
        "source_columns": [
            {
                "name": "LIFNR",
                "description": "Supplier account number",
                "declared_type": "CHAR(10)",
                "dtype": "object",
                "sample_values": ["0000100001", "0000100002"],
                "distinct_sample_values": ["0000100001", "0000100002"],
                    "detected_patterns": ["numeric_id"],
                "tokenized_name": ["vendor", "id"],
            }
        ],
        "target_columns": [
            {
                "name": "supplier_id",
                "description": "Unique supplier identifier",
                "declared_type": "VARCHAR(10)",
                "dtype": "object",
                "sample_values": ["0000100001", "0000100002"],
                "distinct_sample_values": ["0000100001", "0000100002"],
                    "detected_patterns": ["numeric_id"],
                "tokenized_name": ["supplier", "id"],
            },
            {
                "name": "supplier_name",
                "description": "Supplier display name",
                "declared_type": "VARCHAR(80)",
                "dtype": "object",
                "sample_values": ["Acme GmbH", "Contoso LLC"],
                "distinct_sample_values": ["Acme GmbH", "Contoso LLC"],
                "detected_patterns": ["text"],
                "tokenized_name": ["supplier", "name"],
            },
        ],
        "ground_truth": {"LIFNR": "supplier_id"},
    }
    description_blind_case = copy.deepcopy(base_case)
    for column in description_blind_case["source_columns"] + description_blind_case["target_columns"]:
        column["description"] = ""
        column["declared_type"] = ""

    metrics_with_context = evaluate_cases([base_case])
    metrics_without_context = evaluate_cases([description_blind_case])

    assert metrics_with_context.accuracy == metrics_without_context.accuracy
    assert metrics_with_context.top1_accuracy == metrics_without_context.top1_accuracy
    assert metrics_with_context.correct_matches == metrics_without_context.correct_matches


def test_evaluate_cases_for_profile_restores_global_scoring_settings() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "mapping_gold.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))
    previous_profile = settings.scoring_profile
    previous_overrides = dict(settings.scoring_weight_overrides)
    settings.scoring_profile = "balanced"
    settings.scoring_weight_overrides = {"knowledge": 0.33}
    try:
        metrics = evaluate_cases_for_profile(cases, "canonical_first")

        assert metrics.total_cases == 3
        assert settings.scoring_profile == "balanced"
        assert settings.scoring_weight_overrides == {"knowledge": 0.33}
    finally:
        settings.scoring_profile = previous_profile
        settings.scoring_weight_overrides = previous_overrides


def test_compare_scoring_profiles_returns_requested_profiles() -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "mapping_gold.json"
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))

    comparison = compare_scoring_profiles(cases, profile_names=["balanced", "canonical_first"])

    assert set(comparison) == {"balanced", "canonical_first"}
    assert all(metrics.total_cases == 3 for metrics in comparison.values())