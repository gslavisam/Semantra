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


def test_canonical_glossary_influences_mapping_for_business_concepts() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("sold_to_party", ["numeric_id"], ["C001", "C002"])],
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


def test_canonical_coverage_reports_matched_and_unmatched_columns() -> None:
    schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[
            make_column("sold_to_party", ["numeric_id"], ["C001", "C002"]),
            make_column("mystery_field", ["text"], ["foo", "bar"]),
        ],
    )

    coverage = metadata_knowledge_service.canonical_coverage(schema)

    assert coverage.total_columns == 2
    assert coverage.matched_columns == 1
    assert coverage.coverage_ratio == 0.5
    assert coverage.unmatched_columns == ["mystery_field"]
    assert coverage.matched_columns_detail[0].column == "sold_to_party"
    assert "customer.id" in coverage.matched_columns_detail[0].concept_ids


def test_canonical_coverage_matches_common_contact_aliases() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[
            make_column("cust_id", ["numeric_id"], ["1", "2"]),
            make_column("client_mail", ["email"], ["ana@example.com", "marko@example.com"]),
            make_column("primary_phone", ["phone"], ["0641234567", "0659998888"]),
        ],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["1", "2"]),
            make_column("customer_email", ["email"], ["ana@example.com", "marko@example.com"]),
            make_column("phone_number", ["phone"], ["0641234567", "0659998888"]),
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
    assert "customer.phone" in source_matches["primary_phone"]
    assert "customer.phone" in target_matches["phone_number"]


def test_canonical_project_coverage_reports_shared_and_dataset_specific_concepts() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[
            make_column("sold_to_party", ["numeric_id"], ["1", "2"]),
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
    assert "purchase_order.line_item" in matches["EBELP"]
    assert "stock.location" in matches["LGORT"]
    assert "stock.quantity" in matches["LABST"]
    assert "batch.id" in matches["CHARG"]
    assert "gl_account.id" in matches["HKONT"]
    assert "cost_center.id" in matches["KOSTL"]
    assert "profit_center.id" in matches["PRCTR"]
    assert "uom.code" in matches["MEINS"]
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
    assert "sales_order.date" in matches["AUDAT"]
    assert "purchase_order.id" in matches["EBELN"]
    assert "purchase_order.date" in matches["BEDAT"]
    assert "shipping_point.id" in matches["VSTEL"]
    assert "delivery.id" in matches["VBELN_VL"]