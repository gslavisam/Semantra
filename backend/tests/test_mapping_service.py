from app.core.config import settings
from app.services.correction_service import correction_store
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.mapping_service import generate_mapping_candidates
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service
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


def test_mapping_uses_user_correction_history_as_score_boost() -> None:
    correction_store.append(
        {
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "phone_number",
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


def test_promoted_reusable_rule_influences_ranking_without_raw_history() -> None:
    for _ in range(3):
        correction_store.append(
            {
                "source": "cust_ref",
                "suggested_target": "customer_id",
                "corrected_target": "account_id",
                "status": "overridden",
                "note": "Prefer account id",
            }
        )

    correction_store.promote_reusable_rule(
        {
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "account_id",
            "status": "overridden",
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