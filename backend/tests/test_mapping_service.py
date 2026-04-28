from app.core.config import settings
from app.services.correction_service import correction_store
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.mapping_service import generate_mapping_candidates


def setup_function() -> None:
    correction_store.clear()


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
    assert any("Historical user corrections boost" in line for line in result.mappings[0].explanation)


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
        "penalize this candidate" in line
        for line in customer_id_candidate.explanation
    )