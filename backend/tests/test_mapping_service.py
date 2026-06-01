"""Core regression tests for Semantra mapping, scoring, and assignment logic."""

from pathlib import Path

from app.core.config import settings
from app.models.mapping import ScoringSignals
from app.services.correction_service import correction_store
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.mapping_service import (
    CandidateScore,
    SourceSapContextProfile,
    TOTAL_WEIGHT,
    assignment_weight,
    assign_unique_targets,
    build_explanation,
    compute_final_score,
    generate_mapping_candidates,
    label_to_status,
    resolve_scoring_weights,
    score_to_label,
    should_deemphasize_name_signal,
)
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service
from app.services.profiling_service import build_schema_profile
from app.services.virtual_target_service import build_virtual_target_schema
from app.utils.normalization import semantic_token_set


def setup_function() -> None:
    correction_store.clear()
    correction_store.clear_reusable_rules()
    persistence_service.clear_knowledge_overlays()
    metadata_knowledge_service.refresh()


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


def test_mapping_prefers_phone_pattern_when_name_is_weak() -> None:
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

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "phone_number"
    assert any("Strong pattern alignment" in line for line in result.mappings[0].explanation)
    assert result.ranked_mappings[0].candidates[0].target == "phone_number"


def test_mapping_returns_no_match_when_closed_set_is_only_weak_candidates() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=2,
        columns=[make_column("NAME1", ["text"], ["Acme GmbH", "Contoso AG"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=2,
        columns=[
            make_column("customer_id", ["numeric_id"], ["1000", "2000"]),
            make_column("customer_email", ["email"], ["ana@example.com", "bob@example.com"]),
            make_column("phone_number", ["phone"], ["0641234567", "0659998888"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema, write_decision_log=False)

    assert result.mappings[0].target is None
    assert result.mappings[0].method == "closed_set_no_match"
    assert result.mappings[0].confidence == 0.0
    assert result.ranked_mappings[0].selected is not None
    assert result.ranked_mappings[0].selected.target is None
    assert result.ranked_mappings[0].candidates[0].target == "phone_number"
    assert result.ranked_mappings[0].candidates[0].confidence < settings.medium_confidence_threshold
    assert any("No candidate in the closed target set cleared the minimum confidence gate" in line for line in result.mappings[0].explanation)


def test_mapping_uses_synonym_enrichment_for_email_fields() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("client_mail", ["email"], ["ana@example.com", "marko@example.com"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_email", ["email"], ["ana@example.com", "marko@example.com"]),
            make_column("customer_phone", ["phone"], ["0641234567", "0659998888"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "customer_email"
    assert any("Semantic tokens align" in line for line in result.mappings[0].explanation)
    assert any("Signal breakdown" in line for line in result.mappings[0].explanation)


def test_signal_breakdown_lists_all_defined_signals() -> None:
    source = make_column("kunnr", ["text"], ["C0001", "C0002"])
    target = make_column("customer_id", ["text"], ["C0001", "C0002"])

    explanation = build_explanation(
        source,
        target,
        ScoringSignals(
            name=0.15,
            semantic=0.5,
            knowledge=1.0,
            canonical=0.8,
            pattern=1.0,
            statistical=1.0,
            overlap=1.0,
            embedding=0.0,
            correction=0.0,
            llm=0.73,
        ),
    )

    breakdown = next(line for line in explanation if line.startswith("Signal breakdown:"))

    assert "name=0.15" in breakdown
    assert "semantic=0.50" in breakdown
    assert "knowledge=1.00" in breakdown
    assert "canonical=0.80" in breakdown
    assert "pattern=1.00" in breakdown
    assert "stat=1.00" in breakdown
    assert "overlap=1.00" in breakdown
    assert "embedding=0.00" in breakdown
    assert "correction=0.00" in breakdown
    assert "llm=0.73" in breakdown


def test_mapping_assigns_distinct_targets_when_multiple_good_options_exist() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[
            make_column("primary_phone", ["phone"], ["0641234567", "0659998888"]),
            make_column("contact_email", ["email"], ["ana@example.com", "marko@example.com"]),
        ],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("phone_number", ["phone"], ["0641234567", "0659998888"]),
            make_column("email_address", ["email"], ["ana@example.com", "marko@example.com"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert {mapping.target for mapping in result.mappings} == {"phone_number", "email_address"}
    assert all(mapping.status in {"accepted", "needs_review"} for mapping in result.mappings)


def test_mapping_exposes_top_k_candidates_for_each_source() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("cust_id", ["numeric_id"], ["1", "2", "3"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["1", "2", "3"]),
            make_column("account_id", ["numeric_id"], ["1", "2", "3"]),
            make_column("phone_number", ["phone"], ["0641234567", "0659998888"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert len(result.ranked_mappings) == 1
    assert len(result.ranked_mappings[0].candidates) == settings.top_k_candidates
    assert result.ranked_mappings[0].selected is not None


def test_mapping_optional_embedding_signal_can_be_enabled() -> None:
    previous_provider = settings.embedding_provider
    settings.embedding_provider = "hash"
    try:
        source_schema = SchemaProfile(
            dataset_id="source",
            dataset_name="source.csv",
            row_count=5,
            columns=[make_column("customer_identifier", ["numeric_id"], ["1", "2", "3"])],
        )
        target_schema = SchemaProfile(
            dataset_id="target",
            dataset_name="target.csv",
            row_count=5,
            columns=[make_column("customer_id", ["numeric_id"], ["1", "2", "3"])],
        )

        result = generate_mapping_candidates(source_schema, target_schema)

        assert result.mappings[0].signals.embedding > 0
        assert any("embedding" in line.lower() for line in result.mappings[0].explanation)
    finally:
        settings.embedding_provider = previous_provider


def test_mapping_reuses_target_embeddings_within_single_run(monkeypatch) -> None:
    previous_provider = settings.embedding_provider
    settings.embedding_provider = "hash"

    counts: dict[str, int] = {}

    def fake_get_embedding(text: str) -> list[float]:
        counts[text] = counts.get(text, 0) + 1
        return [float(len(text)), 1.0]

    monkeypatch.setattr("app.services.mapping_service.get_embedding", fake_get_embedding)

    try:
        source_schema = SchemaProfile(
            dataset_id="source",
            dataset_name="source.csv",
            row_count=5,
            columns=[
                make_column("vendor_identifier", ["numeric_id"], ["1", "2", "3"]),
                make_column("vendor_name", ["text"], ["Acme", "Contoso"]),
                make_column("vendor_city", ["text"], ["Berlin", "London"]),
            ],
        )
        target_schema = SchemaProfile(
            dataset_id="target",
            dataset_name="target.csv",
            row_count=5,
            columns=[
                make_column("supplier_id", ["numeric_id"], ["1", "2", "3"]),
                make_column("supplier_name", ["text"], ["Acme", "Contoso"]),
                make_column("city_name", ["text"], ["Berlin", "London"]),
                make_column("country_code", ["categorical"], ["DE", "GB"]),
            ],
        )

        generate_mapping_candidates(source_schema, target_schema)

        assert counts["supplier id"] == 1
        assert counts["supplier name"] == 1
        assert counts["city name"] == 1
        assert counts["country code"] == 1
    finally:
        settings.embedding_provider = previous_provider


def test_mapping_uses_user_correction_history_as_score_boost() -> None:
    correction_store.append(
        {
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "phone_number",
            "status": "accepted",
            "note": "phone pattern was the right answer",
        }
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

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "phone_number"
    assert result.mappings[0].signals.correction > 0
    assert any("Similar past decision influenced this ranking" in line for line in result.mappings[0].explanation)


def test_mapping_penalizes_previously_wrong_suggested_target() -> None:
    correction_store.append(
        {
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "phone_number",
            "status": "accepted",
            "note": "customer_id was wrong",
        }
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

    result = generate_mapping_candidates(source_schema, target_schema)
    customer_id_candidate = next(
        candidate
        for candidate in result.ranked_mappings[0].candidates
        if candidate.target == "customer_id"
    )

    assert customer_id_candidate.signals.correction < 0
    assert any(
        "Historical review history penalized this candidate" in line
        for line in customer_id_candidate.explanation
    )


def test_mapping_penalizes_explicitly_rejected_target() -> None:
    correction_store.append(
        {
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": None,
            "status": "rejected",
            "note": "no reliable customer id mapping",
        }
    )
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("cust_ref", ["numeric_id"], ["1", "2"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["1", "2"]),
            make_column("account_id", ["numeric_id"], ["1", "2"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)
    customer_id_candidate = next(
        candidate
        for candidate in result.ranked_mappings[0].candidates
        if candidate.target == "customer_id"
    )

    assert customer_id_candidate.signals.correction < 0
    assert any(
        "Historical review history penalized this candidate" in line
        for line in customer_id_candidate.explanation
    )


def test_compute_final_score_normalizes_over_active_weights() -> None:
    score = compute_final_score(ScoringSignals(name=1.0))

    assert score == 1.0


def test_compute_final_score_clamps_negative_adjustments() -> None:
    score = compute_final_score(ScoringSignals(correction=-1.0))

    assert score == 0.0


def test_compute_final_score_keeps_evaluated_zero_signals_in_active_denominator() -> None:
    score = compute_final_score(
        ScoringSignals(
            name=1.0,
            semantic=1.0,
            knowledge=0.0,
            canonical=1.0,
            pattern=1.0,
            statistical=1.0,
            overlap=1.0,
            embedding=0.0,
            correction=0.0,
            llm=0.0,
        ),
        {"name", "semantic", "knowledge", "canonical", "pattern", "statistical", "overlap"},
    )

    assert score == round(0.82 / 0.92, 4)


def test_compute_final_score_uses_selected_scoring_profile() -> None:
    previous_profile = settings.scoring_profile
    previous_overrides = dict(settings.scoring_weight_overrides)
    settings.scoring_profile = "canonical_first"
    settings.scoring_weight_overrides = {}
    try:
        score = compute_final_score(
            ScoringSignals(name=1.0, knowledge=0.0),
            {"name", "knowledge"},
        )

        assert score == round(0.10 / 0.32, 4)
    finally:
        settings.scoring_profile = previous_profile
        settings.scoring_weight_overrides = previous_overrides


def test_compute_final_score_preserves_strong_sap_business_anchor() -> None:
    source = make_column("LIFNR", ["numeric_id"], ["V0001", "V0002"])
    target = make_column("supplier_id", ["numeric_id"], ["V0001", "V0002"])

    score = compute_final_score(
        ScoringSignals(
            name=0.12,
            semantic=0.86,
            knowledge=1.0,
            canonical=1.0,
            pattern=0.0,
            statistical=0.0,
            overlap=0.0,
            embedding=0.0,
            correction=0.0,
            llm=0.0,
        ),
        {"name", "semantic", "knowledge", "canonical", "pattern", "statistical"},
        source=source,
        target=target,
    )

    assert score >= 0.95


def test_compute_final_score_promotes_strong_identifier_consensus_to_full_confidence() -> None:
    score = compute_final_score(
        ScoringSignals(
            name=0.15,
            semantic=0.5,
            knowledge=1.0,
            canonical=0.8,
            pattern=1.0,
            statistical=1.0,
            overlap=1.0,
            embedding=0.0,
            correction=0.0,
            llm=0.73,
        ),
        {"name", "semantic", "knowledge", "canonical", "pattern", "statistical", "overlap", "llm"},
    )

    assert score == 1.0


def test_assign_unique_targets_uses_global_optimum_not_greedy_edge_order() -> None:
    source_a = make_column("source_a", ["text"], ["A"])
    source_b = make_column("source_b", ["text"], ["B"])
    target_a = make_column("target_a", ["text"], ["A"])
    target_b = make_column("target_b", ["text"], ["B"])

    score_a1 = CandidateScore(
        source=source_a,
        target=target_a,
        score=0.90,
        signals=ScoringSignals(name=0.90),
        explanation=[],
    )
    score_a2 = CandidateScore(
        source=source_a,
        target=target_b,
        score=0.89,
        signals=ScoringSignals(name=0.89),
        explanation=[],
    )
    score_b1 = CandidateScore(
        source=source_b,
        target=target_a,
        score=0.88,
        signals=ScoringSignals(name=0.88),
        explanation=[],
    )
    score_b2 = CandidateScore(
        source=source_b,
        target=target_b,
        score=0.10,
        signals=ScoringSignals(name=0.10),
        explanation=[],
    )

    assigned = assign_unique_targets(
        {
            "source_a": [score_a1, score_a2],
            "source_b": [score_b1, score_b2],
        }
    )

    assert assigned["source_a"].target.name == "target_b"
    assert assigned["source_b"].target.name == "target_a"
    assert assignment_weight(assigned["source_a"]) + assignment_weight(assigned["source_b"]) > 1.7


def test_supplier_showcase_auto_description_priority_and_global_assignment_fix() -> None:
    from app.services.profiling_service import build_schema_profile
    from app.services.spec_upload_service import parse_spec_payload
    from app.services.tabular_upload_service import read_xml_payload

    fixture_root = Path(__file__).resolve().parents[2] / "ui_fixtures" / "showcase_supplier_master"
    source_rows = read_xml_payload((fixture_root / "showcase_supplier_source.xml").read_bytes())
    source_schema = build_schema_profile(
        source_rows,
        dataset_id="source",
        dataset_name="showcase_supplier_source.xml",
    )
    target_schema = parse_spec_payload(
        (fixture_root / "showcase_supplier_target_spec.csv").read_bytes(),
        "showcase_supplier_target_spec.csv",
    )

    result = generate_mapping_candidates(source_schema, target_schema)
    selected_by_source = {item.source: item for item in result.mappings}

    assert selected_by_source["LIFNR"].target == "supplier_id"
    assert selected_by_source["LIFNR"].confidence >= 0.95
    assert selected_by_source["PSTLZ"].target == "postal_code"
    assert selected_by_source["TELF1"].target == "phone_number"
    assert selected_by_source["ORT01"].target == "city_name"
    assert any("business anchor" in line.lower() for line in selected_by_source["LIFNR"].explanation)


def test_scoring_weight_overrides_replace_profile_weights() -> None:
    previous_profile = settings.scoring_profile
    previous_overrides = dict(settings.scoring_weight_overrides)
    settings.scoring_profile = "balanced"
    settings.scoring_weight_overrides = {"knowledge": 0.40}
    try:
        weights = resolve_scoring_weights()
        score = compute_final_score(
            ScoringSignals(name=1.0, knowledge=0.0),
            {"name", "knowledge"},
        )

        assert weights["knowledge"] == 0.40
        assert score == round(0.20 / 0.60, 4)
    finally:
        settings.scoring_profile = previous_profile
        settings.scoring_weight_overrides = previous_overrides


def test_promoted_reusable_rule_influences_ranking_without_raw_history() -> None:
    for _ in range(3):
        correction_store.append(
            {
                "source": "cust_ref",
                "suggested_target": "customer_id",
                "corrected_target": "account_id",
                "status": "accepted",
                "note": "Prefer account id",
            }
        )

    correction_store.promote_reusable_rule(
        {
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "account_id",
            "status": "accepted",
            "occurrence_count": 3,
        }
    )
    correction_store.clear()

    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("cust_ref", ["numeric_id"], ["1", "2"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["1", "2"]),
            make_column("account_id", ["numeric_id"], ["1", "2"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "account_id"
    assert result.mappings[0].signals.correction > 0
    assert any("Reusable rule influenced this ranking" in line for line in result.mappings[0].explanation)


def test_active_overlay_synonym_enriches_semantic_tokens() -> None:
    overlay = persistence_service.save_knowledge_overlay_version("overlay-v1", status="validated")
    persistence_service.save_knowledge_overlay_entries(
        overlay.overlay_id,
        [
            {
                "entry_type": "synonym",
                "canonical_term": "customer",
                "alias": "purchaser",
                "domain": "sales",
                "source_system": None,
                "note": "Overlay synonym",
                "normalized_canonical_term": "customer",
                "normalized_alias": "purchaser",
            }
        ],
    )
    persistence_service.activate_knowledge_overlay_version(overlay.overlay_id)
    metadata_knowledge_service.refresh()

    tokens = semantic_token_set("purchaser_email")

    assert "purchaser" in tokens
    assert "customer" in tokens


def test_canonical_glossary_influences_mapping_for_generic_customer_alias() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("cust_id", ["numeric_id"], ["C001", "C002"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["C001", "C002"]),
            make_column("vendor_id", ["numeric_id"], ["V001", "V002"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert metadata_knowledge_service.canonical_concept_count > 0
    assert result.mappings[0].target == "customer_id"
    assert result.mappings[0].signals.canonical > 0
    assert result.mappings[0].canonical_details.shared_concepts[0].concept_id == "customer.id"
    assert result.mappings[0].canonical_details.shared_concepts[0].display_name == "Customer ID"
    assert any("Canonical glossary aligns both fields to business concept 'Customer ID'" in line for line in result.mappings[0].explanation)


def test_canonical_virtual_target_prefers_core_customer_id_for_sold_to_party_alias() -> None:
    source_schema = build_schema_profile(
        [{"sold_to_party": "C001"}, {"sold_to_party": "C002"}],
        dataset_id="source",
        dataset_name="source.csv",
    )

    result = generate_mapping_candidates(
        source_schema,
        build_virtual_target_schema("canonical"),
        llm_provider=None,
        write_decision_log=False,
    )

    assert result.mappings[0].target == "customer.id"


def test_canonical_coverage_reports_matched_and_unmatched_columns_for_generic_customer_alias() -> None:
    schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[
            make_column("cust_id", ["numeric_id"], ["C001", "C002"]),
            make_column("mystery_field", ["text"], ["foo", "bar"]),
        ],
    )

    coverage = metadata_knowledge_service.canonical_coverage(schema)

    assert coverage.total_columns == 2
    assert coverage.matched_columns == 1
    assert coverage.coverage_ratio == 0.5
    assert coverage.unmatched_columns == ["mystery_field"]
    assert coverage.matched_columns_detail[0].column == "cust_id"
    assert "customer.id" in coverage.matched_columns_detail[0].concept_ids


def test_canonical_coverage_matches_common_contact_aliases() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[
            make_column("cust_id", ["numeric_id"], ["1", "2"]),
            make_column("client_mail", ["email"], ["ana@example.com", "marko@example.com"]),
            make_column("customer_phone", ["phone"], ["0641234567", "0659998888"]),
        ],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["1", "2"]),
            make_column("customer_email", ["email"], ["ana@example.com", "marko@example.com"]),
            make_column("customer_phone", ["phone"], ["0641234567", "0659998888"]),
        ],
    )

    source_coverage = metadata_knowledge_service.canonical_coverage(source_schema)
    target_coverage = metadata_knowledge_service.canonical_coverage(target_schema)

    assert source_coverage.matched_columns == 3
    assert source_coverage.coverage_ratio == 1.0
    assert source_coverage.unmatched_columns == []
    assert target_coverage.matched_columns == 3
    assert target_coverage.coverage_ratio == 1.0
    assert target_coverage.unmatched_columns == []
    source_matches = {detail.column: detail.concept_ids for detail in source_coverage.matched_columns_detail}
    target_matches = {detail.column: detail.concept_ids for detail in target_coverage.matched_columns_detail}
    assert "customer.email" in source_matches["client_mail"]
    assert "customer.phone" in source_matches["customer_phone"]
    assert "customer.phone" in target_matches["customer_phone"]


def test_canonical_project_coverage_reports_shared_and_dataset_specific_concepts() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[
            make_column("cust_id", ["numeric_id"], ["1", "2"]),
            make_column("client_mail", ["email"], ["ana@example.com", "marko@example.com"]),
        ],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["1", "2"]),
            make_column("customer_email", ["email"], ["ana@example.com", "marko@example.com"]),
            make_column("vendor_id", ["numeric_id"], ["V1", "V2"]),
        ],
    )

    source_coverage = metadata_knowledge_service.canonical_coverage(source_schema)
    target_coverage = metadata_knowledge_service.canonical_coverage(target_schema)
    project_coverage = metadata_knowledge_service.canonical_project_coverage(source_coverage, target_coverage)

    assert project_coverage.total_columns == 5
    assert project_coverage.matched_columns == 5
    assert project_coverage.coverage_ratio == 1.0
    assert project_coverage.shared_concept_count == 2
    assert "customer.id" in project_coverage.shared_concepts
    assert "customer.email" in project_coverage.shared_concepts
    assert "vendor.id" in project_coverage.target_only_concepts


def test_canonical_coverage_matches_curated_erp_aliases() -> None:
    schema = SchemaProfile(
        dataset_id="erp",
        dataset_name="erp_extract.csv",
        row_count=5,
        columns=[
            make_column("EBELN", ["text"], ["4500000010", "4500000011"]),
            make_column("EBELP", ["numeric_id"], ["00010", "00020"]),
            make_column("LGORT", ["text"], ["0001", "0002"]),
            make_column("LABST", ["numeric_id"], ["120", "75"]),
            make_column("CHARG", ["text"], ["BATCH01", "BATCH02"]),
            make_column("HKONT", ["numeric_id"], ["400000", "500000"]),
            make_column("KOSTL", ["text"], ["CC100", "CC200"]),
            make_column("PRCTR", ["text"], ["PC100", "PC200"]),
            make_column("MEINS", ["text"], ["EA", "KG"]),
            make_column("WAERS", ["text"], ["EUR", "USD"]),
            make_column("ZTERM", ["text"], ["N30", "N45"]),
            make_column("INCO1", ["text"], ["EXW", "FOB"]),
            make_column("PRUEFLOS", ["text"], ["1000001", "1000002"]),
            make_column("ANLN1", ["text"], ["ASSET01", "ASSET02"]),
            make_column("EQUNR", ["text"], ["EQ100", "EQ200"]),
            make_column("MATKL", ["text"], ["FG01", "RM01"]),
        ],
    )

    coverage = metadata_knowledge_service.canonical_coverage(schema)

    assert coverage.total_columns == 16
    assert coverage.matched_columns == 16
    assert coverage.coverage_ratio == 1.0
    assert coverage.unmatched_columns == []

    matches = {detail.column: detail.concept_ids for detail in coverage.matched_columns_detail}
    assert "purchase_order.id" in matches["EBELN"]
    assert "purchase_order.line_item_number" in matches["EBELP"]
    assert "storage_location.id" in matches["LGORT"]
    assert "stock.quantity" in matches["LABST"]
    assert "batch.id" in matches["CHARG"]
    assert "gl_account.id" in matches["HKONT"]
    assert "cost_center.id" in matches["KOSTL"]
    assert "profit_center.id" in matches["PRCTR"]
    assert "material.base_uom_code" in matches["MEINS"]
    assert "currency.code" in matches["WAERS"]
    assert "payment_term.id" in matches["ZTERM"]
    assert "incoterm.code" in matches["INCO1"]
    assert "quality_inspection.id" in matches["PRUEFLOS"]
    assert "asset.id" in matches["ANLN1"]
    assert "equipment.id" in matches["EQUNR"]
    assert "material_group.id" in matches["MATKL"]


def test_canonical_coverage_matches_sd_mm_document_aliases() -> None:
    schema = SchemaProfile(
        dataset_id="sdmm",
        dataset_name="sdmm_extract.csv",
        row_count=5,
        columns=[
            make_column("VBELN", ["text"], ["500001", "500002"]),
            make_column("AUDAT", ["date"], ["2025-01-01", "2025-01-02"]),
            make_column("EBELN", ["text"], ["450001", "450002"]),
            make_column("BEDAT", ["date"], ["2025-01-03", "2025-01-04"]),
            make_column("VSTEL", ["text"], ["SP01", "SP02"]),
            make_column("VBELN_VL", ["text"], ["800001", "800002"]),
        ],
    )

    coverage = metadata_knowledge_service.canonical_coverage(schema)

    assert coverage.total_columns == 6
    assert coverage.matched_columns == 6
    assert coverage.coverage_ratio == 1.0
    assert coverage.unmatched_columns == []

    matches = {detail.column: detail.concept_ids for detail in coverage.matched_columns_detail}
    assert "sales_order.id" in matches["VBELN"]
    assert "sales_order.document_date" in matches["AUDAT"]
    assert "purchase_order.id" in matches["EBELN"]
    assert "purchase_order.document_date" in matches["BEDAT"]
    assert "shipping_point.id" in matches["VSTEL"]
    assert "delivery.id" in matches["VBELN_VL"]


def test_canonical_virtual_target_keeps_strong_concept_lock_high_confidence() -> None:
    source_schema = SchemaProfile(
        dataset_id="source-spec",
        dataset_name="source_schema_spec.csv",
        row_count=0,
        columns=[
            ColumnProfile(
                name="KUNNR",
                normalized_name="Customer number",
                dtype="integer",
                null_ratio=0.0,
                unique_ratio=0.0,
                avg_length=0.0,
                non_null_count=0,
                sample_values=[],
                distinct_sample_values=[],
                detected_patterns=["integer"],
                tokenized_name=["kunnr"],
            )
        ],
    )

    result = generate_mapping_candidates(source_schema, build_virtual_target_schema("canonical"))

    selected = result.mappings[0]
    assert selected.target == "customer.id"
    assert selected.confidence >= settings.high_confidence_threshold
    assert selected.confidence_label == "high_confidence"
    assert any("Internal metadata dictionary aligns both fields to concept 'Customer ID'" in line for line in selected.explanation)
    assert any("Canonical glossary aligns both fields to business concept 'Customer ID'" in line for line in selected.explanation)


def test_sap_concept_lock_deemphasizes_weak_name_signal() -> None:
    source = make_column("ZTERM", ["text"], ["0001", "0002", "0003"])
    target = make_column("payment_terms_id", ["text"], ["0001", "0002", "0003"])
    signals = ScoringSignals(
        name=0.23,
        semantic=0.80,
        knowledge=0.75,
        canonical=0.75,
        statistical=0.71,
        llm=0.70,
    )
    active_signal_names = {"name", "semantic", "knowledge", "canonical", "statistical", "llm"}

    assert should_deemphasize_name_signal(signals, active_signal_names, source) is True

    score = compute_final_score(
        signals,
        active_signal_names,
        profile_name="description_priority",
        source=source,
        target=target,
        source_sap_profile=SourceSapContextProfile(),
    )

    assert 0.75 <= score <= 0.77


def test_sap_payment_terms_mapping_explains_name_signal_deemphasis() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=3,
        columns=[make_column("ZTERM", ["text"], ["0001", "0002", "0003"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=3,
        columns=[
            make_column("payment_terms_id", ["text"], ["0001", "0002", "0003"]),
            make_column("tax_id_number", ["text"], ["1001", "1002", "1003"]),
            make_column("postal_code", ["text"], ["11000", "21000", "31000"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema, description_priority=True)

    selected = result.mappings[0]
    assert selected.target == "payment_terms_id"
    assert selected.confidence >= 0.75
    assert any("Weak physical evidence was de-emphasized" in line for line in selected.explanation)


def test_label_to_status_auto_accepts_scores_above_auto_accept_threshold() -> None:
    score = 0.8193

    assert score_to_label(score) == "medium_confidence"
    assert label_to_status(score) == "accepted"


def test_description_priority_mode_uses_source_description_for_canonical_matching() -> None:
    source_column = ColumnProfile(
        name="SENIOR_FIELD",
        normalized_name="senior field",
        description="Employee phone",
        declared_type="VARCHAR",
        dtype="object",
        null_ratio=0.0,
        unique_ratio=0.0,
        avg_length=0.0,
        non_null_count=0,
        sample_values=[],
        distinct_sample_values=[],
        detected_patterns=["text"],
        tokenized_name=["senior", "field"],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="canonical_subset.csv",
        row_count=0,
        columns=[
            make_column("employee.phone", ["phone"], []),
            make_column("employee.id", ["numeric_id"], []),
        ],
    )

    baseline_matches = metadata_knowledge_service.match_canonical_concepts(source_column)
    priority_matches = metadata_knowledge_service.match_canonical_concepts(
        source_column,
        prefer_metadata_text=True,
    )

    baseline_match = next(match for match in baseline_matches if match.concept_id == "employee.phone")
    priority_match = next(match for match in priority_matches if match.concept_id == "employee.phone")

    assert baseline_match.strength > 0
    assert priority_match.strength > baseline_match.strength

    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source_senior.xlsx",
        row_count=0,
        columns=[source_column],
    )
    result = generate_mapping_candidates(
        source_schema,
        target_schema,
        description_priority=True,
    )

    assert result.mappings[0].target == "employee.phone"
    assert any("Description-priority mode injected source description/type metadata" in line for line in result.mappings[0].explanation)


def test_canonical_matching_uses_target_metadata_without_description_priority() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=3,
        columns=[make_column("REGIO", ["text"], ["CA", "TX", "AZ"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=3,
        columns=[
            ColumnProfile(
                name="region_code",
                normalized_name="region code",
                description="Supplier Region Code",
                declared_type="VARCHAR",
                dtype="object",
                null_ratio=0.0,
                unique_ratio=1.0,
                avg_length=5.0,
                non_null_count=3,
                sample_values=["CA", "TX", "AZ"],
                distinct_sample_values=["CA", "TX", "AZ"],
                detected_patterns=["text"],
                tokenized_name=["region", "code"],
            )
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    selected = result.mappings[0]
    assert selected.target == "region_code"
    assert selected.signals.knowledge > 0
    assert selected.signals.canonical > 0
    assert any(
        "Internal metadata dictionary aligns" in line or "Canonical glossary aligns" in line
        for line in selected.explanation
    )


def test_generic_target_attribute_bridge_lifts_regio_without_target_metadata() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=3,
        columns=[make_column("REGIO", ["text"], ["CA", "TX", "AZ"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=3,
        columns=[make_column("region_code", ["text"], ["CA", "TX", "AZ"])],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    selected = result.mappings[0]
    assert selected.target == "region_code"
    assert selected.signals.knowledge > 0
    assert selected.signals.canonical > 0
    assert selected.confidence >= 0.55
    assert any("attribute bridge" in line.lower() for line in selected.explanation)


def test_strong_concept_lock_deemphasizes_name_without_sap_anchor() -> None:
    source = make_column("legacy_pay_code", ["text"], ["0001", "0002", "0003"])
    target = make_column("payment_terms_id", ["text"], ["0001", "0002", "0003"])
    signals = ScoringSignals(
        name=0.23,
        semantic=0.80,
        knowledge=0.75,
        canonical=0.75,
        statistical=0.71,
        llm=0.70,
    )
    active_signal_names = {"name", "semantic", "knowledge", "canonical", "statistical", "llm"}

    assert should_deemphasize_name_signal(signals, active_signal_names, source) is True

    score = compute_final_score(
        signals,
        active_signal_names,
        profile_name="description_priority",
        source=source,
        target=target,
    )

    assert 0.75 <= score <= 0.77


def test_strong_concept_lock_deemphasizes_weak_pattern_and_overlap() -> None:
    source = make_column("legacy_pay_code", ["text"], ["0001", "0002", "0003"])
    target = make_column("payment_terms_id", ["numeric_id"], ["A1", "B2", "C3"])
    signals = ScoringSignals(
        name=0.23,
        semantic=0.80,
        knowledge=0.75,
        canonical=0.75,
        pattern=0.0,
        statistical=0.71,
        overlap=0.0,
    )
    active_signal_names = {"name", "semantic", "knowledge", "canonical", "pattern", "statistical", "overlap"}

    score = compute_final_score(
        signals,
        active_signal_names,
        profile_name="description_priority",
        source=source,
        target=target,
    )

    assert 0.75 <= score <= 0.77


def test_business_first_concept_lock_deemphasizes_weak_physical_signals() -> None:
    source = make_column("AKONT", ["numeric_id"], ["140000", "150000"])
    target = make_column("reconciliation_account", ["text"], ["A", "B"])
    signals = ScoringSignals(
        name=0.13,
        semantic=0.60,
        knowledge=1.00,
        canonical=0.80,
        pattern=0.0,
        statistical=0.63,
        overlap=0.0,
    )
    active_signal_names = {"name", "semantic", "knowledge", "canonical", "pattern", "statistical", "overlap"}

    score = compute_final_score(
        signals,
        active_signal_names,
        profile_name="description_priority",
        source=source,
        target=target,
    )

    assert 0.76 <= score <= 0.78


def test_mapping_response_includes_runtime_fingerprint() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=2,
        columns=[make_column("AKONT", ["numeric_id"], ["140000", "150000"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=2,
        columns=[make_column("reconciliation_account", ["numeric_id"], ["140000", "150000"])],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mapping_runtime.code_fingerprint
    assert result.mapping_runtime.generated_at
    assert result.mapping_runtime.scoring_profile == settings.scoring_profile
    assert result.mapping_runtime.description_priority is False


def test_canonical_candidate_pool_limits_full_scoring_to_shortlist(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import mapping_service

    seen_targets: list[str] = []
    original_compute_signals = mapping_service.compute_signals

    def recording_compute_signals(source, target, **kwargs):
        seen_targets.append(target.name)
        return original_compute_signals(source, target, **kwargs)

    monkeypatch.setattr(mapping_service, "compute_signals", recording_compute_signals)

    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source_senior.xlsx",
        row_count=0,
        columns=[
            ColumnProfile(
                name="SENIOR_FIELD",
                normalized_name="senior field",
                description="Employee phone",
                declared_type="VARCHAR",
                dtype="object",
                null_ratio=0.0,
                unique_ratio=0.0,
                avg_length=0.0,
                non_null_count=0,
                sample_values=[],
                distinct_sample_values=[],
                detected_patterns=["text"],
                tokenized_name=["senior", "field"],
            )
        ],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="canonical_subset.csv",
        row_count=0,
        columns=[
            make_column("employee.phone", ["phone"], []),
            make_column("employee.id", ["numeric_id"], []),
            make_column("employee.email", ["email"], []),
            make_column("employee.manager.id", ["numeric_id"], []),
            make_column("employee.department.name", ["text"], []),
            make_column("employee.birth_date", ["date"], []),
            make_column("employee.status", ["text"], []),
            make_column("employee.country.code", ["text"], []),
        ],
    )

    result = generate_mapping_candidates(
        source_schema,
        target_schema,
        description_priority=True,
        candidate_pool_size=5,
    )

    assert result.mappings[0].target == "employee.phone"
    assert len(seen_targets) == 5
    assert "employee.phone" in seen_targets