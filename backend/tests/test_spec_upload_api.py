"""API tests for schema-spec upload parsing and validation flows."""

from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
from unittest.mock import patch

from app.main import app
from app.services.llm_service import StaticLLMProvider
from app.services.upload_store import dataset_store


client = TestClient(app)


def setup_function() -> None:
    dataset_store.clear()


def test_spec_detect_endpoint_returns_hint_for_spec_file() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "KUNNR,Customer number,CHAR\n"
                    "NAME1,Customer name,VARCHAR\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] == {
        "name_col": "Column",
        "description_col": "Description",
        "type_col": "Type",
        "sample_values_col": None,
        "confidence": 1.0,
    }


def test_spec_detect_endpoint_returns_no_hint_for_data_file() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source.csv",
                csv_bytes("cust_id,phone\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_detect_endpoint_does_not_fail_for_mixed_multi_block_csv() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "multi_block_spec.csv",
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
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_detect_endpoint_does_not_fail_for_mixed_multi_block_xlsx() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "multi_block_spec.xlsx",
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
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_detect_endpoint_returns_no_hint_for_malformed_json() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source.json",
                json_bytes('{"records": [{"field": "KUNNR"}, ]}'),
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_detect_endpoint_returns_no_hint_for_shape_invalid_json() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source.json",
                json_bytes('{"customers": [{"customer_id": 1}], "contacts": [{"phone": "0641234567"}]}'),
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_detect_endpoint_returns_no_hint_for_malformed_xml() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source.xml",
                xml_bytes("<rows><row><customer_id>1</customer_id></row>"),
                "application/xml",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_detect_endpoint_returns_no_hint_for_shape_invalid_xml() -> None:
    response = client.post(
        "/upload/spec/detect",
        files={
            "file": (
                "source.xml",
                xml_bytes(
                    "<root>"
                    "<field>KUNNR</field>"
                    "<metadata><description>Customer number</description></metadata>"
                    "</root>"
                ),
                "application/xml",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["hint"] is None


def test_spec_recovery_endpoint_returns_validated_hint_from_llm() -> None:
    provider = StaticLLMProvider(
        """
        {
            "detected_mode": "spec",
            "sheet_name": null,
            "header_row_index": 1,
            "record_path": null,
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
            "selected_table": null,
            "confidence": 0.91,
            "warnings": ["Header labels are non-standard but still field-oriented."]
        }
        """
    )

    with patch("app.api.routes.upload.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/upload/spec/recover",
            files={
                "file": (
                    "source_spec.csv",
                    csv_bytes(
                        "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
                        "AKONT,Reconciliation account,CHAR,160000|170000\n"
                    ),
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "recovered"
    assert payload["hint"] == {
        "name_col": "SENIOR_FIELD",
        "description_col": "Senior Description",
        "type_col": "DataType",
        "sample_values_col": "Example Values",
        "confidence": 0.91,
    }
    assert payload["suggestion"]["detected_mode"] == "spec"


def test_spec_recovery_endpoint_extracts_embedded_csv_block_before_llm() -> None:
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
            "confidence": 0.89,
            "warnings": ["Detected the field-definition block after prose."]
        }
        """
    )

    with patch("app.api.routes.upload.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/upload/spec/recover",
            files={
                "file": (
                    "mixed_spec.csv",
                    csv_bytes(
                        "Introductory note for analysts\n"
                        "The following section lists field definitions\n"
                        "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
                        "AKONT,Reconciliation account,CHAR,160000|170000\n"
                        "ERDAT,Created on,DATS,20240101\n"
                        "Closing comment after the table\n"
                    ),
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "recovered"
    assert payload["suggestion"]["header_row_index"] == 3
    assert any("embedded tabular block starting at row 3" in warning for warning in payload["warnings"])


def test_spec_recovery_endpoint_lets_llm_choose_between_multiple_candidate_blocks() -> None:
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
            "confidence": 0.86,
            "warnings": ["Selected the field-definition block after comparing two tabular candidates."]
        }
        """
    )

    with patch("app.api.routes.upload.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/upload/spec/recover",
            files={
                "file": (
                    "multi_block_spec.csv",
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
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "recovered"
    assert payload["suggestion"]["header_row_index"] == 6
    assert any("considered 2 candidate tabular blocks" in warning for warning in payload["warnings"])


def test_spec_recovery_endpoint_lets_llm_choose_between_multiple_xlsx_candidate_blocks() -> None:
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
            "confidence": 0.85,
            "warnings": ["Selected the field-definition block after comparing two candidate ranges."]
        }
        """
    )

    with patch("app.api.routes.upload.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/upload/spec/recover",
            files={
                "file": (
                    "multi_block_spec.xlsx",
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
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "recovered"
    assert payload["suggestion"]["header_row_index"] == 6
    assert any("considered 2 candidate tabular blocks" in warning for warning in payload["warnings"])


def test_spec_recovery_endpoint_uses_multi_block_alias_fallback_without_provider() -> None:
    with patch("app.api.routes.upload.build_provider_from_settings", return_value=None):
        response = client.post(
            "/upload/spec/recover",
            files={
                "file": (
                    "multi_block_spec.csv",
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
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "recovered"
    assert payload["suggestion"]["header_row_index"] == 6
    assert any("selected candidate block at row 6 via close header aliases" in warning for warning in payload["warnings"])


def test_spec_recovery_endpoint_returns_unavailable_without_configured_provider() -> None:
    with patch("app.api.routes.upload.build_provider_from_settings", return_value=None):
        response = client.post(
            "/upload/spec/recover",
            files={
                "file": (
                    "source_spec.csv",
                    csv_bytes(
                        "A1,B2,C3\n"
                        "AKONT,Reconciliation account,CHAR\n"
                    ),
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["hint"] is None
    assert "disabled or unavailable" in payload["failure_reason"]


def test_spec_recovery_endpoint_rejects_unknown_llm_headers() -> None:
    provider = StaticLLMProvider(
        """
        {
            "detected_mode": "spec",
            "sheet_name": null,
            "header_row_index": 1,
            "record_path": null,
            "name_col": "MissingField",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": null,
            "selected_table": null,
            "confidence": 0.72,
            "warnings": []
        }
        """
    )

    with patch("app.api.routes.upload.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/upload/spec/recover",
            files={
                "file": (
                    "source_spec.csv",
                    csv_bytes(
                        "A1,B2,C3\n"
                        "AKONT,Reconciliation account,CHAR\n"
                    ),
                    "text/csv",
                )
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "invalid_suggestion"
    assert payload["hint"] is None


def test_spec_upload_endpoint_returns_dataset_handle() -> None:
    response = client.post(
        "/upload/spec",
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "KUNNR,Customer number,CHAR\n"
                    "ERDAT,Created on,DATE\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"]
    assert [column["name"] for column in payload["schema_profile"]["columns"]] == ["KUNNR", "ERDAT"]
    assert payload["schema_profile"]["columns"][0]["normalized_name"] == "kunnr"
    assert payload["schema_profile"]["columns"][0]["description"] == "Customer number"
    assert payload["schema_profile"]["columns"][0]["declared_type"] == "CHAR"
    assert payload["preview_rows"] == []


def test_spec_upload_endpoint_accepts_manual_sample_values_column() -> None:
    response = client.post(
        "/upload/spec",
        data={
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
        },
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
                    "AKONT,Reconciliation account,CHAR,160000|170000\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_profile"]["columns"][0]["name"] == "AKONT"
    assert payload["schema_profile"]["columns"][0]["description"] == "Reconciliation account"
    assert payload["schema_profile"]["columns"][0]["declared_type"] == "CHAR"
    assert payload["schema_profile"]["columns"][0]["sample_values"] == ["160000", "170000"]


def test_spec_upload_endpoint_accepts_mixed_text_around_embedded_table() -> None:
    response = client.post(
        "/upload/spec",
        data={
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
        },
        files={
            "file": (
                "mixed_spec.csv",
                csv_bytes(
                    "Introductory note for analysts\n"
                    "The following section lists field definitions\n"
                    "SENIOR_FIELD,Senior Description,DataType,Example Values\n"
                    "AKONT,Reconciliation account,CHAR,160000|170000\n"
                    "ERDAT,Created on,DATS,20240101\n"
                    "Closing comment after the table\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [column["name"] for column in payload["schema_profile"]["columns"]] == ["AKONT", "ERDAT"]


def test_spec_upload_endpoint_accepts_explicit_header_row_for_selected_candidate_block() -> None:
    response = client.post(
        "/upload/spec",
        data={
            "header_row_index": "6",
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
        },
        files={
            "file": (
                "multi_block_spec.csv",
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
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [column["name"] for column in payload["schema_profile"]["columns"]] == ["AKONT", "ERDAT"]


def test_spec_upload_endpoint_accepts_explicit_header_row_for_selected_xlsx_candidate_block() -> None:
    response = client.post(
        "/upload/spec",
        data={
            "header_row_index": "6",
            "name_col": "SENIOR_FIELD",
            "description_col": "Senior Description",
            "type_col": "DataType",
            "sample_values_col": "Example Values",
        },
        files={
            "file": (
                "multi_block_spec.xlsx",
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
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [column["name"] for column in payload["schema_profile"]["columns"]] == ["AKONT", "ERDAT"]


def test_spec_upload_endpoint_returns_400_for_unknown_name_col() -> None:
    response = client.post(
        "/upload/spec",
        data={"name_col": "MissingColumn"},
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "KUNNR,Customer number,CHAR\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown spec name column: MissingColumn"


def test_upload_handle_endpoint_returns_dataset_handle_for_row_data() -> None:
    response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("cust_id,phone\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"]
    assert [column["name"] for column in payload["schema_profile"]["columns"]] == ["cust_id", "phone"]
    assert payload["preview_rows"][0]["cust_id"] == "1"


def test_upload_handle_endpoint_rejects_malformed_json() -> None:
    response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.json",
                json_bytes('{"records": [{"customer_id": 1}, ]}'),
                "application/json",
            )
        },
    )

    assert response.status_code == 400
    assert "Failed to parse tabular file:" in response.json()["detail"]


def test_upload_handle_endpoint_rejects_shape_invalid_json() -> None:
    response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.json",
                json_bytes('{"customers": [{"customer_id": 1}], "contacts": [{"phone": "0641234567"}]}'),
                "application/json",
            )
        },
    )

    assert response.status_code == 400
    assert "JSON uploads must be an object, an array of objects, or an object containing one array of objects" in response.json()["detail"]


def test_upload_handle_endpoint_rejects_malformed_xml() -> None:
    response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.xml",
                xml_bytes("<rows><row><customer_id>1</customer_id></row>"),
                "application/xml",
            )
        },
    )

    assert response.status_code == 400
    assert "Failed to parse tabular file:" in response.json()["detail"]


def test_upload_handle_endpoint_rejects_shape_invalid_xml() -> None:
    response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.xml",
                xml_bytes(
                    "<root>"
                    "<customer_id>1</customer_id>"
                    "<row><phone>0641234567</phone></row>"
                    "</root>"
                ),
                "application/xml",
            )
        },
    )

    assert response.status_code == 400
    assert "XML uploads must be a single record element or a collection of repeated record elements with child fields" in response.json()["detail"]


def test_spec_recovery_endpoint_rejects_malformed_json_without_recovery() -> None:
    response = client.post(
        "/upload/spec/recover",
        files={
            "file": (
                "source.json",
                json_bytes('{"records": [{"field": "KUNNR"}, ]}'),
                "application/json",
            )
        },
    )

    assert response.status_code == 400
    assert "Failed to parse tabular file:" in response.json()["detail"]


def test_spec_recovery_endpoint_rejects_shape_invalid_xml_without_recovery() -> None:
    response = client.post(
        "/upload/spec/recover",
        files={
            "file": (
                "source.xml",
                xml_bytes(
                    "<root>"
                    "<field>KUNNR</field>"
                    "<metadata><description>Customer number</description></metadata>"
                    "</root>"
                ),
                "application/xml",
            )
        },
    )

    assert response.status_code == 400
    assert "Failed to parse tabular file:" in response.json()["detail"]


def test_upload_handle_metadata_endpoint_enriches_existing_dataset_handle() -> None:
    upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("KUNNR,ERDAT\n1,2024-01-01\n2,2024-01-02\n"),
                "text/csv",
            )
        },
    )

    response = client.post(
        "/upload/handle/metadata",
        data={"dataset_id": upload_response.json()["dataset_id"]},
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type,Sample Values\n"
                    "KUNNR,Customer number,CHAR,1000|2000\n"
                    "ERDAT,Created on,DATS,20240101\n"
                    "UNUSED,Unused,CHAR,XX\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["matched_columns"] == 2
    assert payload["unmatched_columns"] == ["UNUSED"]
    assert payload["dataset"]["dataset_id"] == upload_response.json()["dataset_id"]
    assert payload["dataset"]["preview_rows"][0]["KUNNR"] == "1"
    assert payload["dataset"]["schema_profile"]["columns"][0]["description"] == "Customer number"
    assert payload["dataset"]["schema_profile"]["columns"][0]["declared_type"] == "CHAR"
    assert payload["dataset"]["schema_profile"]["columns"][0]["sample_values"] == ["1000", "2000"]


def test_upload_handle_metadata_endpoint_returns_400_when_no_columns_match() -> None:
    upload_response = client.post(
        "/upload/handle",
        files={
            "file": (
                "source.csv",
                csv_bytes("KUNNR,ERDAT\n1,2024-01-01\n"),
                "text/csv",
            )
        },
    )

    response = client.post(
        "/upload/handle/metadata",
        data={"dataset_id": upload_response.json()["dataset_id"]},
        files={
            "file": (
                "source_spec.csv",
                csv_bytes(
                    "Column,Description,Type\n"
                    "LAND1,Country,CHAR\n"
                ),
                "text/csv",
            )
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Companion metadata did not match any existing dataset columns."


def csv_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def json_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def xml_bytes(text: str) -> bytes:
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