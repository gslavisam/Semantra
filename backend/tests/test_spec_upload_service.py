from __future__ import annotations

from app.services.spec_upload_service import detect_spec_layout, map_spec_type, parse_spec_rows


def test_detect_spec_layout_returns_hint_for_field_spec_headers() -> None:
    hint = detect_spec_layout(["Column", "Description", "Type", "Length"])

    assert hint is not None
    assert hint.name_col == "Column"
    assert hint.description_col == "Description"
    assert hint.type_col == "Type"
    assert hint.confidence == 1.0


def test_detect_spec_layout_rejects_plain_data_headers() -> None:
    assert detect_spec_layout(["KUNNR", "NAME1", "LAND1"]) is None


def test_parse_spec_rows_builds_schema_columns_from_field_rows() -> None:
    profile = parse_spec_rows(
        [
            {"Column": "KUNNR", "Description": "Customer number", "Type": "CHAR"},
            {"Column": "NAME1", "Description": "Customer name", "Type": "VARCHAR"},
            {"Column": "ERDAT", "Description": "Created on", "Type": "DATE"},
        ],
        dataset_id="dataset-1",
        dataset_name="customer_spec.csv",
    )

    assert profile.row_count == 0
    assert [column.name for column in profile.columns] == ["KUNNR", "NAME1", "ERDAT"]
    assert profile.columns[0].normalized_name == "Customer number"
    assert profile.columns[0].dtype == "string"
    assert profile.columns[2].dtype == "date"


def test_parse_spec_rows_skips_empty_and_section_rows() -> None:
    profile = parse_spec_rows(
        [
            {"Column": "", "Description": "Blank row", "Type": "CHAR"},
            {"Column": "Table: KNA1", "Description": "Section", "Type": ""},
            {"Column": "KUNNR", "Description": "Customer number", "Type": "NUMC"},
        ],
        dataset_id="dataset-1",
        dataset_name="customer_spec.csv",
    )

    assert [column.name for column in profile.columns] == ["KUNNR"]
    assert profile.columns[0].dtype == "integer"


def test_map_spec_type_maps_unknown_type_to_string() -> None:
    assert map_spec_type("CUSTOM_BLOB") == "string"