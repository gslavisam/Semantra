"""Unit tests for schema-spec parsing and normalization service logic."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.services.spec_upload_service import detect_spec_layout, map_spec_type, parse_spec_payload, parse_spec_rows


def test_detect_spec_layout_returns_hint_for_field_spec_headers() -> None:
    hint = detect_spec_layout(["Column", "Description", "Type", "Sample Values", "Length"])

    assert hint is not None
    assert hint.name_col == "Column"
    assert hint.description_col == "Description"
    assert hint.type_col == "Type"
    assert hint.sample_values_col == "Sample Values"
    assert hint.confidence == 1.0


def test_detect_spec_layout_rejects_plain_data_headers() -> None:
    assert detect_spec_layout(["KUNNR", "NAME1", "LAND1"]) is None


def test_parse_spec_rows_builds_schema_columns_from_field_rows() -> None:
    profile = parse_spec_rows(
        [
            {"Column": "KUNNR", "Description": "Customer number", "Type": "CHAR", "Sample Values": "1000 | 2000 | 3000"},
            {"Column": "NAME1", "Description": "Customer name", "Type": "VARCHAR", "Sample Values": "Acme; Contoso"},
            {"Column": "ERDAT", "Description": "Created on", "Type": "DATE", "Sample Values": "20240101"},
        ],
        dataset_id="dataset-1",
        dataset_name="customer_spec.csv",
    )

    assert profile.row_count == 0
    assert [column.name for column in profile.columns] == ["KUNNR", "NAME1", "ERDAT"]
    assert profile.columns[0].normalized_name == "kunnr"
    assert profile.columns[0].description == "Customer number"
    assert profile.columns[0].declared_type == "CHAR"
    assert profile.columns[0].sample_values == ["1000", "2000", "3000"]
    assert profile.columns[0].dtype == "string"
    assert profile.columns[2].dtype == "date"


def test_parse_spec_rows_parses_and_deduplicates_sample_values() -> None:
    profile = parse_spec_rows(
        [
            {
                "Column": "AKONT",
                "Description": "Reconciliation account",
                "Type": "CHAR",
                "Sample Values": "100000; 100000 ; 200000\n300000|400000|500000|600000",
            }
        ],
        dataset_id="dataset-2",
        dataset_name="vendor_spec.csv",
    )

    assert profile.columns[0].sample_values == ["100000", "200000", "300000", "400000", "500000"]
    assert profile.columns[0].distinct_sample_values == ["100000", "200000", "300000", "400000", "500000"]


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


def test_parse_spec_payload_extracts_embedded_csv_table_from_mixed_text() -> None:
    profile = parse_spec_payload(
        (
            "Introductory note for analysts\n"
            "The following section lists field definitions\n"
            "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
            "AKONT,Reconciliation account,CHAR,160000|170000\n"
            "ERDAT,Created on,DATS,20240101\n"
            "Closing comment after the table\n"
        ).encode("utf-8"),
        "mixed_spec.csv",
        name_col="SENIOR_FIELD",
        description_col="Senior Description",
        type_col="DataType",
        sample_values_col="Example Values",
    )

    assert [column.name for column in profile.columns] == ["AKONT", "ERDAT"]
    assert profile.columns[0].description == "Reconciliation account"
    assert profile.columns[0].sample_values == ["160000", "170000"]


def test_parse_spec_payload_extracts_embedded_xlsx_table_from_mixed_rows() -> None:
    profile = parse_spec_payload(
        xlsx_bytes(
            [
                ["Introductory note for analysts"],
                ["The following section lists field definitions"],
                ["SENIOR_FIELD", "Senior Description", "DataType", "Example Values"],
                ["AKONT", "Reconciliation account", "CHAR", "160000|170000"],
                ["ERDAT", "Created on", "DATS", "20240101"],
                ["Closing comment after the table"],
            ]
        ),
        "mixed_spec.xlsx",
        name_col="SENIOR_FIELD",
        description_col="Senior Description",
        type_col="DataType",
        sample_values_col="Example Values",
    )

    assert [column.name for column in profile.columns] == ["AKONT", "ERDAT"]
    assert profile.columns[0].description == "Reconciliation account"
    assert profile.columns[0].sample_values == ["160000", "170000"]


def xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()