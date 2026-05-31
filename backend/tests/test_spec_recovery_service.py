"""Focused unit tests for bounded schema-spec recovery behavior."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from app.services.llm_service import StaticLLMProvider
from app.services.spec_recovery_service import recover_spec_layout


def test_recover_spec_layout_returns_deterministic_hint_without_llm() -> None:
    result = recover_spec_layout(
        csv_bytes(
            "Column,Description,Type\n"
            "KUNNR,Customer number,CHAR\n"
        ),
        "source_spec.csv",
        provider=None,
    )

    assert result.status == "recovered"
    assert result.hint is not None
    assert result.hint.name_col == "Column"
    assert result.hint.description_col == "Description"
    assert result.hint.type_col == "Type"


def test_recover_spec_layout_returns_no_suggestion_for_row_data_classification() -> None:
    provider = StaticLLMProvider(
        """
        {
            "detected_mode": "row_data",
            "sheet_name": null,
            "header_row_index": 1,
            "record_path": null,
            "name_col": null,
            "description_col": null,
            "type_col": null,
            "sample_values_col": null,
            "selected_table": null,
            "confidence": 0.66,
            "warnings": ["Rows look like business records, not field metadata."]
        }
        """
    )

    result = recover_spec_layout(
        csv_bytes(
            "customer_id,customer_email,phone_number\n"
            "1001,ana@example.com,0641234567\n"
        ),
        "source_spec.csv",
        provider=provider,
    )

    assert result.status == "no_suggestion"
    assert result.hint is None
    assert result.suggestion is not None
    assert result.suggestion.detected_mode == "row_data"


def test_recover_spec_layout_extracts_embedded_csv_block_before_llm_recovery() -> None:
    provider = StaticLLMProvider(
        """
        {
            "detected_mode": "spec",
            "sheet_name": null,
            "header_row_index": 3,
            "record_path": null,
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
            "selected_table": null,
            "confidence": 0.88,
            "warnings": ["Detected the field-definition table after introductory text."]
        }
        """
    )

    result = recover_spec_layout(
        csv_bytes(
            "Introductory note for analysts\n"
            "The following section lists field definitions\n"
            "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
            "AKONT,Reconciliation account,CHAR,160000|170000\n"
            "ERDAT,Created on,DATS,20240101\n"
            "Closing comment after the table\n"
        ),
        "mixed_spec.csv",
        provider=provider,
    )

    assert result.status == "recovered"
    assert result.hint is not None
    assert result.hint.name_col == "SENIOR_FIELD"
    assert result.suggestion is not None
    assert result.suggestion.header_row_index == 3
    assert any("embedded tabular block starting at row 3" in warning for warning in result.warnings)


def test_recover_spec_layout_lets_llm_choose_between_multiple_candidate_blocks() -> None:
    provider = StaticLLMProvider(
        """
        {
            "detected_mode": "spec",
            "sheet_name": null,
            "header_row_index": 6,
            "record_path": null,
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
            "selected_table": null,
            "confidence": 0.84,
            "warnings": ["Chose the field-definition block instead of the business-record block."]
        }
        """
    )

    result = recover_spec_layout(
        csv_bytes(
            "Introductory note for analysts\n"
            "Customer ID,Customer Email,Phone Number\n"
            "1001,ana@example.com,0641234567\n"
            "1002,marko@example.com,0659998888\n"
            "Field definition section\n"
            "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
            "AKONT,Reconciliation account,CHAR,160000|170000\n"
            "ERDAT,Created on,DATS,20240101\n"
            "Closing comment after the table\n"
        ),
        "multi_block_spec.csv",
        provider=provider,
    )

    assert result.status == "recovered"
    assert result.suggestion is not None
    assert result.suggestion.header_row_index == 6
    assert result.hint is not None
    assert result.hint.name_col == "SENIOR_FIELD"
    assert any("considered 2 candidate tabular blocks" in warning for warning in result.warnings)


def test_recover_spec_layout_lets_llm_choose_between_multiple_xlsx_candidate_blocks() -> None:
    provider = StaticLLMProvider(
        """
        {
            "detected_mode": "spec",
            "sheet_name": null,
            "header_row_index": 6,
            "record_path": null,
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
            "selected_table": null,
            "confidence": 0.87,
            "warnings": ["Selected the field-definition block after comparing two candidate ranges."]
        }
        """
    )

    result = recover_spec_layout(
        xlsx_bytes(
            [
                ["Introductory note for analysts"],
                ["Customer ID", "Customer Email", "Phone Number"],
                [1001, "ana@example.com", "0641234567"],
                [1002, "marko@example.com", "0659998888"],
                ["Field definition section"],
                ["SENIOR_FIELD", "Senior Description", "DataType", "Example Values"],
                ["AKONT", "Reconciliation account", "CHAR", "160000|170000"],
                ["ERDAT", "Created on", "DATS", "20240101"],
                ["Closing comment after the table"],
            ]
        ),
        "multi_block_spec.xlsx",
        provider=provider,
    )

    assert result.status == "recovered"
    assert result.suggestion is not None
    assert result.suggestion.header_row_index == 6
    assert result.hint is not None
    assert result.hint.name_col == "SENIOR_FIELD"
    assert any("considered 2 candidate tabular blocks" in warning for warning in result.warnings)


def test_recover_spec_layout_uses_multi_block_alias_fallback_without_llm() -> None:
    result = recover_spec_layout(
        csv_bytes(
            "Introductory note for analysts\n"
            "Customer ID,Customer Email,Phone Number\n"
            "1001,ana@example.com,0641234567\n"
            "1002,marko@example.com,0659998888\n"
            "Field definition section\n"
            "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
            "AKONT,Reconciliation account,CHAR,160000|170000\n"
            "ERDAT,Created on,DATS,20240101\n"
            "Closing comment after the table\n"
        ),
        "multi_block_spec.csv",
        provider=None,
    )

    assert result.status == "recovered"
    assert result.suggestion is not None
    assert result.suggestion.header_row_index == 6
    assert result.hint is not None
    assert result.hint.name_col == "SENIOR_FIELD"
    assert any("selected candidate block at row 6 via close header aliases" in warning for warning in result.warnings)


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()