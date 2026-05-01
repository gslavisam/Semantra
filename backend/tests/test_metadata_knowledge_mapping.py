from app.models.schema import ColumnProfile, SchemaProfile
from app.services.mapping_service import generate_mapping_candidates
from app.services.metadata_knowledge_service import metadata_knowledge_service


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
