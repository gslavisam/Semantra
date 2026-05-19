"""Tests interactions between mapping behavior and metadata or canonical knowledge runtime."""

import pytest
from unittest.mock import patch

from app.models.schema import ColumnProfile, SchemaProfile
from app.services.mapping_service import generate_mapping_candidates
from app.services.metadata_knowledge_service import MetadataKnowledgeService, metadata_knowledge_service
from app.services.persistence_service import persistence_service
from app.services.source_field_hint_service import apply_source_field_hints


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
    persistence_service.clear_knowledge_overlays()
    persistence_service.clear_source_field_hints()
    metadata_knowledge_service.refresh()


def test_apply_source_field_hints_enriches_matching_column_from_sqlite_store() -> None:
    persistence_service.save_source_field_hint(
        {
            "source_system": "Senior HR",
            "business_domain": "HR",
            "source_field": "tipOpe",
            "meaning_hint": "Operation type / transaction type",
            "negative_hint": "Not contact name",
            "sample_values": ["SALE", "RETURN", "STORNO"],
        }
    )
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=2,
        columns=[make_column("tipOpe", ["categorical"], ["SALE", "RETURN"])],
    )

    enriched_schema, applied_hints = apply_source_field_hints(
        source_schema,
        source_system="Senior HR",
        business_domain="HR",
    )

    assert len(applied_hints) == 1
    assert "Persistent field hint: Operation type / transaction type" in enriched_schema.columns[0].description
    assert "STORNO" in enriched_schema.columns[0].sample_values


def test_metadata_dictionary_is_loaded() -> None:
    assert metadata_knowledge_service.is_available


def test_metadata_dictionary_prefers_sap_customer_alias_to_customer_id() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("KUNNR", ["numeric_id"], ["C0001", "C0002"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["C0001", "C0002"]),
            make_column("vendor_id", ["numeric_id"], ["V0001", "V0002"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "customer_id"
    assert result.mappings[0].signals.knowledge > 0
    assert any("Internal metadata dictionary aligns" in line for line in result.mappings[0].explanation)


def test_canonical_glossary_import_avoids_full_metadata_reseed(tmp_path) -> None:
    service = MetadataKnowledgeService()
    service.canonical_glossary_path = tmp_path / "canonical_glossary.csv"

    import_payload = (
        "concept_id,entity,attribute,display_name,description,data_type,aliases\n"
        'loyalty.id,loyalty,id,Loyalty ID,Identifier for a loyalty profile,string,"loyalty id, loyalty identifier"\n'
    ).encode("utf-8")

    with patch.object(service, "_load", side_effect=AssertionError("full metadata reseed should not run")):
        response = service.import_canonical_glossary_csv(import_payload, filename="canonical_glossary.csv")

    assert response.imported_row_count == 1
    assert service.runtime_source == "canonical_authoring_sync"
    assert any(entry.concept_id == "loyalty.id" for entry in service.list_canonical_glossary_entries())


def test_canonical_glossary_promotion_avoids_full_metadata_reseed(tmp_path) -> None:
    service = MetadataKnowledgeService()
    service.canonical_glossary_path = tmp_path / "canonical_glossary.csv"
    service.canonical_glossary_path.write_text(
        "concept_id,entity,attribute,display_name,description,data_type,aliases\n"
        "customer.id,customer,id,Customer ID,Primary customer identifier,string,customer id\n",
        encoding="utf-8",
    )
    service.refresh()

    with patch.object(service, "_load", side_effect=AssertionError("full metadata reseed should not run")):
        entry, alias_added, concept_created = service.promote_overlay_alias_to_canonical_glossary(
            "customer.id",
            "legacy_customer_identifier",
        )

    assert alias_added is True
    assert concept_created is False
    assert service.runtime_source == "canonical_authoring_sync"
    assert "legacy customer identifier" in entry.aliases


def test_metadata_dictionary_bridges_serbian_term_to_english_target() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("Maticni broj JMBG", ["numeric_id"], ["101985710001", "201985710002"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("national_id", ["numeric_id"], ["101985710001", "201985710002"]),
            make_column("tax_id", ["numeric_id"], ["103456789", "203456789"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "national_id"
    assert result.mappings[0].signals.knowledge > 0


def test_metadata_workbook_adds_cross_system_material_context() -> None:
    material_matches = metadata_knowledge_service.match_concepts(make_column("MATNR", ["text"], ["MAT-001", "MAT-002"]))

    material_number_match = next(match for match in material_matches if match.concept_id == "material number")

    assert any(context.system == "SAP" and context.object_name == "MARA" and context.field_name == "MATNR" for context in material_number_match.contexts)


def test_metadata_workbook_links_sap_material_to_workday_item_id() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("MATNR", ["text"], ["MAT-001", "MAT-002"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("Item_ID", ["text"], ["ITEM-001", "ITEM-002"]),
            make_column("Gross_Weight", ["float"], ["10.2", "13.4"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "Item_ID"
    assert result.mappings[0].signals.knowledge > 0
    assert any("Context prior:" in line for line in result.mappings[0].explanation)
    assert any("SAP MARA.MATNR" in line for line in result.mappings[0].explanation)
    assert any("Workday Item.Item_ID" in line for line in result.mappings[0].explanation)


def test_material_master_matnr_prefers_material_id_over_engineering_part_number() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("MATNR", ["text"], ["MAT-001", "MAT-002"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("material_id", ["text"], ["MAT-001", "MAT-002"]),
            make_column("engineering_part_number", ["text"], ["LEG-001", "LEG-002"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)
    ranked = result.ranked_mappings[0]
    engineering_candidate = next(candidate for candidate in ranked.candidates if candidate.target == "engineering_part_number")

    assert result.mappings[0].target == "material_id"
    assert result.mappings[0].signals.knowledge > 0
    assert ranked.candidates[0].target == "material_id"
    assert ranked.candidates[0].confidence > engineering_candidate.confidence


@pytest.mark.parametrize(
    ("source_name", "source_patterns", "sample_values", "expected_target", "other_target"),
    [
        ("BISMT", ["text"], ["LEG-PUMP-A100", "LEG-VALVE-V20"], "engineering_part_number", "material_id"),
        ("ERSDA", ["date"], ["2023-01-10", "2022-09-18"], "created_date", "material_id"),
        ("XCHPF", ["text"], ["X", ""], "batch_managed_flag", "deletion_mark"),
        ("LVORM", ["text"], ["X", ""], "deletion_mark", "batch_managed_flag"),
    ],
)
def test_material_master_sap_field_aliases_gain_knowledge_or_canonical_support(
    source_name: str,
    source_patterns: list[str],
    sample_values: list[str],
    expected_target: str,
    other_target: str,
) -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column(source_name, source_patterns, sample_values)],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column(expected_target, source_patterns, sample_values),
            make_column(other_target, ["text"], ["ALT-001", "ALT-002"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)
    selected = result.mappings[0]

    assert selected.target == expected_target
    assert selected.signals.knowledge > 0 or selected.signals.canonical > 0
    assert any(
        marker in line
        for marker in ("Internal metadata dictionary aligns", "Canonical glossary aligns both fields")
        for line in selected.explanation
    )


def test_supplier_master_sperr_gains_supplier_posting_block_support() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("SPERR", ["text"], ["X", ""])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("posting_block_flag", ["text"], ["X", ""]),
            make_column("deletion_mark", ["text"], ["X", ""]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)
    selected = result.mappings[0]

    assert selected.target == "posting_block_flag"
    assert selected.signals.knowledge > 0 or selected.signals.canonical > 0
    assert any(
        marker in line
        for marker in ("Internal metadata dictionary aligns", "Canonical glossary aligns both fields")
        for line in selected.explanation
    )


def test_canonical_only_sap_field_context_survives_cold_start_db_reload() -> None:
    metadata_knowledge_service.reseed_from_files()
    file_seed_matches = metadata_knowledge_service.match_concepts(make_column("LSTEL", ["text"], ["A01", "A02"]))

    cold_start_service = MetadataKnowledgeService()
    cold_start_matches = cold_start_service.match_concepts(make_column("LSTEL", ["text"], ["A01", "A02"]))

    file_seed_match = next(match for match in file_seed_matches if match.concept_id == "shipping_point.id")
    cold_start_match = next(match for match in cold_start_matches if match.concept_id == "shipping_point.id")

    assert tuple((context.system, context.object_name, context.field_name) for context in cold_start_match.contexts) == tuple(
        (context.system, context.object_name, context.field_name) for context in file_seed_match.contexts
    )


def test_generated_workday_overlay_is_not_auto_loaded_into_base_knowledge() -> None:
    middle_name_matches = metadata_knowledge_service.match_canonical_concepts(make_column("Middle_Name", ["text"], ["Ana", "Mila"]))

    assert "address.country" not in {match.concept_id for match in middle_name_matches}


def test_active_overlay_field_alias_changes_mapping_result() -> None:
    overlay = persistence_service.save_knowledge_overlay_version("overlay-v1", status="validated")
    persistence_service.save_knowledge_overlay_entries(
        overlay.overlay_id,
        [
            {
                "entry_type": "field_alias",
                "canonical_term": "customer id",
                "alias": "LEGACY_CUST",
                "domain": "master_data",
                "source_system": "LegacyERP",
                "note": "Legacy customer identifier",
                "normalized_canonical_term": "customer id",
                "normalized_alias": "legacy cust",
            }
        ],
    )
    persistence_service.activate_knowledge_overlay_version(overlay.overlay_id)
    metadata_knowledge_service.refresh()

    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("LEGACY_CUST", ["numeric_id"], ["C0001", "C0002"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["C0001", "C0002"]),
            make_column("vendor_id", ["numeric_id"], ["V0001", "V0002"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "customer_id"
    assert result.mappings[0].signals.knowledge > 0
    assert any("Custom knowledge overlay 'overlay-v1' matched alias(es): legacy cust." in line for line in result.mappings[0].explanation)


def test_active_overlay_concept_alias_extends_canonical_matching() -> None:
    overlay = persistence_service.save_knowledge_overlay_version("overlay-v1", status="validated")
    persistence_service.save_knowledge_overlay_entries(
        overlay.overlay_id,
        [
            {
                "entry_type": "concept_alias",
                "canonical_term": "Customer ID",
                "canonical_concept_id": "customer.id",
                "alias": "legacy_customer_identifier",
                "domain": "master_data",
                "source_system": "LegacyERP",
                "note": "Legacy canonical alias",
                "normalized_canonical_term": "customer id",
                "normalized_alias": "legacy customer identifier",
            }
        ],
    )
    persistence_service.activate_knowledge_overlay_version(overlay.overlay_id)
    metadata_knowledge_service.refresh()

    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=5,
        columns=[make_column("legacy_customer_identifier", ["numeric_id"], ["C0001", "C0002"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=5,
        columns=[
            make_column("customer_id", ["numeric_id"], ["C0001", "C0002"]),
            make_column("vendor_id", ["numeric_id"], ["V0001", "V0002"]),
        ],
    )

    result = generate_mapping_candidates(source_schema, target_schema)

    assert result.mappings[0].target == "customer_id"
    assert result.mappings[0].signals.canonical > 0
    assert result.mappings[0].canonical_details.shared_concepts[0].concept_id == "customer.id"
    assert any("extended canonical concept 'Customer ID'" in line for line in result.mappings[0].explanation)
