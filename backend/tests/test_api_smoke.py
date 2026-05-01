from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.config import settings
from app.main import app
from app.services.correction_service import correction_store
from app.services.decision_log_service import decision_log_store
from app.services.llm_service import StaticLLMProvider
from app.services.persistence_service import persistence_service
from app.services.upload_store import dataset_store


client = TestClient(app)


def setup_function() -> None:
    dataset_store.clear()
    decision_log_store.clear()
    correction_store.clear()
    persistence_service.clear_benchmark_datasets()
    persistence_service.clear_evaluation_runs()
    settings.admin_api_token = ""


def test_upload_returns_schema_profiles_and_dataset_ids() -> None:
    response = client.post(
        "/upload",
        files={
            "source_file": ("source.csv", csv_bytes("cust_id,phone\n1,0641234567\n2,0659998888\n"), "text/csv"),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id,phone_number\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["dataset_id"]
    assert payload["target"]["dataset_id"]
    assert payload["source"]["schema_profile"]["columns"][0]["name"] == "cust_id"
    assert payload["target"]["schema_profile"]["columns"][1]["name"] == "phone_number"


def test_sql_table_discovery_returns_available_tables() -> None:
    response = client.post(
        "/upload/sql/tables",
        files={
            "file": (
                "source.sql",
                sql_bytes(
                    "CREATE TABLE customers (customer_id BIGINT);\n"
                    "CREATE TABLE contacts (client_mail VARCHAR(255), primary_phone VARCHAR(32));\n"
                ),
                "application/sql",
            )
        },
    )

    assert response.status_code == 200
    assert response.json()["tables"] == ["customers", "contacts"]


def test_upload_accepts_sql_schema_snapshot_and_returns_schema_only_profile() -> None:
    response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.sql",
                sql_bytes(
                    "CREATE TABLE customer_source (\n"
                    "    customer_id BIGINT,\n"
                    "    client_mail VARCHAR(255),\n"
                    "    created_at TIMESTAMP\n"
                    ");\n"
                ),
                "application/sql",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id,customer_email,created_at\n1,ana@example.com,2025-01-01\n"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"]["schema_profile"]["row_count"] == 0
    assert [column["name"] for column in payload["source"]["schema_profile"]["columns"]] == [
        "customer_id",
        "client_mail",
        "created_at",
    ]
    assert payload["source"]["preview_rows"] == []


def test_upload_accepts_json_row_data() -> None:
    response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.json",
                json_bytes('[{"cust_id": 1, "phone": "0641234567"}, {"cust_id": 2, "phone": "0659998888"}]'),
                "application/json",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id,phone_number\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [column["name"] for column in payload["source"]["schema_profile"]["columns"]] == ["cust_id", "phone"]
    assert payload["source"]["preview_rows"][0]["cust_id"] == 1


def test_upload_accepts_xml_row_data() -> None:
    response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.xml",
                xml_bytes(
                    "<rows>"
                    "<row><cust_id>1</cust_id><phone>0641234567</phone></row>"
                    "<row><cust_id>2</cust_id><phone>0659998888</phone></row>"
                    "</rows>"
                ),
                "application/xml",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id,phone_number\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [column["name"] for column in payload["source"]["schema_profile"]["columns"]] == ["cust_id", "phone"]
    assert payload["source"]["preview_rows"][1]["phone"] == "0659998888"


def test_upload_accepts_xlsx_row_data() -> None:
    response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.xlsx",
                xlsx_bytes(
                    ["cust_id", "phone"],
                    [
                        [1, "0641234567"],
                        [2, "0659998888"],
                    ],
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id,phone_number\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [column["name"] for column in payload["source"]["schema_profile"]["columns"]] == ["cust_id", "phone"]
    assert payload["source"]["preview_rows"][0]["phone"] == "0641234567"


def test_upload_rejects_multi_table_sql_without_explicit_selection() -> None:
    response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.sql",
                sql_bytes(
                    "CREATE TABLE customers (customer_id BIGINT);\n"
                    "CREATE TABLE contacts (phone_number VARCHAR(32));\n"
                ),
                "application/sql",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id\n1\n"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 400
    assert "Available tables: customers, contacts" in response.json()["detail"]


def test_upload_accepts_multi_table_sql_with_explicit_table_selection() -> None:
    response = client.post(
        "/upload",
        data={"source_table": "contacts"},
        files={
            "source_file": (
                "source.sql",
                sql_bytes(
                    "CREATE TABLE customers (customer_id BIGINT);\n"
                    "CREATE TABLE contacts (client_mail VARCHAR(255), primary_phone VARCHAR(32));\n"
                ),
                "application/sql",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_email,phone_number\nana@example.com,0641234567\n"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [column["name"] for column in payload["source"]["schema_profile"]["columns"]] == [
        "client_mail",
        "primary_phone",
    ]


def test_auto_map_accepts_mixed_csv_and_sql_schema_inputs() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.sql",
                sql_bytes(
                    "CREATE TABLE source_customers (\n"
                    "    client_mail VARCHAR(255),\n"
                    "    primary_phone VARCHAR(32)\n"
                    ");\n"
                ),
                "application/sql",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_email,phone_number\nana@example.com,0641234567\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()

    map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "target_dataset_id": payload["target"]["dataset_id"],
        },
    )

    assert map_response.status_code == 200
    mappings = {item["source"]: item["target"] for item in map_response.json()["mappings"]}
    assert mappings["client_mail"] == "customer_email"
    assert mappings["primary_phone"] == "phone_number"


def test_auto_map_accepts_json_to_xlsx_inputs() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.json",
                json_bytes('[{"client_mail": "ana@example.com", "primary_phone": "0641234567"}]'),
                "application/json",
            ),
            "target_file": (
                "target.xlsx",
                xlsx_bytes(
                    ["customer_email", "phone_number"],
                    [["ana@example.com", "0641234567"]],
                ),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()

    map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "target_dataset_id": payload["target"]["dataset_id"],
        },
    )

    assert map_response.status_code == 200
    mappings = {item["source"]: item["target"] for item in map_response.json()["mappings"]}
    assert mappings["client_mail"] == "customer_email"
    assert mappings["primary_phone"] == "phone_number"


@pytest.mark.parametrize("source_format", ["csv", "json", "xml", "xlsx"])
@pytest.mark.parametrize("target_format", ["csv", "json", "xml", "xlsx"])
def test_auto_map_accepts_every_row_format_pair(source_format: str, target_format: str) -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": build_row_format_upload(source_format, dataset_role="source"),
            "target_file": build_row_format_upload(target_format, dataset_role="target"),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    assert payload["source"]["schema_profile"]["columns"][0]["name"] == "client_mail"
    assert payload["target"]["schema_profile"]["columns"][0]["name"] == "customer_email"

    map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "target_dataset_id": payload["target"]["dataset_id"],
        },
    )

    assert map_response.status_code == 200
    mappings = {item["source"]: item["target"] for item in map_response.json()["mappings"]}
    assert mappings["client_mail"] == "customer_email"
    assert mappings["primary_phone"] == "phone_number"


def test_auto_map_accepts_multi_table_selection_on_both_sides() -> None:
    upload_response = client.post(
        "/upload",
        data={"source_table": "contacts", "target_table": "crm_contact"},
        files={
            "source_file": (
                "source.sql",
                sql_bytes(
                    "CREATE TABLE customers (customer_id BIGINT);\n"
                    "CREATE TABLE contacts (client_mail VARCHAR(255), primary_phone VARCHAR(32));\n"
                ),
                "application/sql",
            ),
            "target_file": (
                "target.sql",
                sql_bytes(
                    "CREATE TABLE account_dim (account_id BIGINT);\n"
                    "CREATE TABLE crm_contact (customer_email VARCHAR(255), phone_number VARCHAR(32));\n"
                ),
                "application/sql",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()

    map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "target_dataset_id": payload["target"]["dataset_id"],
        },
    )

    assert map_response.status_code == 200
    mappings = {item["source"]: item["target"] for item in map_response.json()["mappings"]}
    assert mappings["client_mail"] == "customer_email"
    assert mappings["primary_phone"] == "phone_number"


def test_preview_returns_empty_rows_for_schema_only_source() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.sql",
                sql_bytes("CREATE TABLE source_customers (client_mail VARCHAR(255));\n"),
                "application/sql",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_email\nana@example.com\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    preview_response = client.post(
        "/mapping/preview",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "mapping_decisions": [
                {"source": "client_mail", "target": "customer_email", "status": "accepted"},
            ],
        },
    )

    assert preview_response.status_code == 200
    assert preview_response.json()["preview"] == []


def test_auto_map_returns_selected_mapping_and_ranked_candidates() -> None:
    upload_payload = upload_example_datasets()
    response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["mappings"]) == 2
    assert len(payload["ranked_mappings"]) == 2
    first_ranked = payload["ranked_mappings"][0]
    assert first_ranked["selected"] is not None
    assert first_ranked["candidates"]
    assert payload["mappings"][0]["target"] in {"customer_id", "phone_number"}


def test_preview_projects_rows_from_mapping_decisions() -> None:
    upload_payload = upload_example_datasets()
    preview_response = client.post(
        "/mapping/preview",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer_id", "status": "accepted"},
                {"source": "phone", "target": "phone_number", "status": "accepted"},
            ],
        },
    )

    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert len(payload["preview"]) == 2
    assert payload["preview"][0]["values"]["customer_id"] == "1"
    assert payload["preview"][0]["values"]["phone_number"] == "0641234567"
    assert payload["unresolved_targets"] == []


def test_preview_applies_transformation_code_to_rows() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.csv",
                csv_bytes("email\nana.markovic@example.com\nmarko.petrovic@example.com\n"),
                "text/csv",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_name\nAna Markovic\nMarko Petrovic\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    preview_response = client.post(
        "/mapping/preview",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "mapping_decisions": [
                {
                    "source": "email",
                    "target": "customer_name",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_name"] = df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
                }
            ],
        },
    )

    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["preview"][0]["values"]["customer_name"] == "Ana Markovic"
    assert preview_payload["preview"][1]["values"]["customer_name"] == "Marko Petrovic"
    assert preview_payload["preview"][0]["warnings"] == []


def test_preview_falls_back_to_direct_mapping_when_transformation_fails() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.csv",
                csv_bytes("email\nana.markovic@example.com\n"),
                "text/csv",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_name\nAna Markovic\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    preview_response = client.post(
        "/mapping/preview",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "mapping_decisions": [
                {
                    "source": "email",
                    "target": "customer_name",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_name"] = df_source["email"].str.not_a_real_method()',
                }
            ],
        },
    )

    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["preview"][0]["values"]["customer_name"] == "ana.markovic@example.com"
    assert any("Transformation failed for email -> customer_name" in warning for warning in preview_payload["preview"][0]["warnings"])


def test_codegen_returns_pandas_snippet_for_mapping_decisions() -> None:
    response = client.post(
        "/mapping/codegen",
        json={
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer_id", "status": "accepted"},
                {"source": "phone", "target": "phone_number", "status": "accepted"},
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["language"] == "python-pandas"
    assert 'df_target["customer_id"] = df_source["cust_id"]' in payload["code"]
    assert 'df_target["phone_number"] = df_source["phone"]' in payload["code"]


def test_codegen_uses_transformation_code_when_present() -> None:
    response = client.post(
        "/mapping/codegen",
        json={
            "mapping_decisions": [
                {
                    "source": "email",
                    "target": "customer_name",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_name"] = df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert 'df_target["customer_name"] = df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()' in payload["code"]


def test_transformation_generation_endpoint_returns_llm_generated_code() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.csv",
                csv_bytes("email\nana.markovic@example.com\n"),
                "text/csv",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_name\nAna Markovic\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()
    provider = StaticLLMProvider(
        json.dumps(
            {
                "transformation_code": 'df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
                "reasoning": ["Extract the local part of the email", "Replace dots with spaces"],
            }
        )
    )

    with patch("app.api.routes.mapping.build_provider_from_settings", return_value=provider):
        response = client.post(
            "/mapping/transformation/generate",
            json={
                "source_dataset_id": payload["source"]["dataset_id"],
                "target_dataset_id": payload["target"]["dataset_id"],
                "source_column": "email",
                "target_column": "customer_name",
                "instruction": "Extract the person's name from the email address.",
            },
        )

    assert response.status_code == 200
    generated = response.json()
    assert 'df_source["email"]' in generated["transformation_code"]
    assert generated["reasoning"]


def test_decision_logs_endpoint_returns_mapping_run_logs() -> None:
    upload_payload = upload_example_datasets()
    auto_map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert auto_map_response.status_code == 200

    logs_response = client.get("/observability/decision-logs", headers=admin_headers())

    assert logs_response.status_code == 200
    payload = logs_response.json()
    assert len(payload) == 2
    assert payload[0]["source"] in {"cust_id", "phone"}
    assert "candidate_targets" in payload[0]


def test_admin_guard_blocks_sensitive_endpoints_when_token_is_configured() -> None:
    settings.admin_api_token = "secret-token"

    response = client.get("/observability/decision-logs")

    assert response.status_code == 403


def test_admin_guard_allows_sensitive_endpoints_with_correct_token() -> None:
    settings.admin_api_token = "secret-token"

    response = client.get("/observability/config", headers=admin_headers())

    assert response.status_code == 200
    assert "llm_provider" in response.json()


def test_evaluation_benchmark_endpoint_returns_metrics() -> None:
    response = client.get("/evaluation/benchmark")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_cases"] == 3
    assert payload["total_fields"] == 4
    assert "accuracy" in payload


def test_custom_evaluation_run_endpoint_accepts_custom_cases() -> None:
    response = client.post(
        "/evaluation/run",
        json={
            "cases": [
                {
                    "source_columns": [
                        {
                            "name": "client_mail",
                            "sample_values": ["ana@example.com"],
                            "distinct_sample_values": ["ana@example.com"],
                            "detected_patterns": ["email"],
                            "unique_ratio": 1.0,
                            "tokenized_name": ["client", "mail"],
                        }
                    ],
                    "target_columns": [
                        {
                            "name": "customer_email",
                            "sample_values": ["ana@example.com"],
                            "distinct_sample_values": ["ana@example.com"],
                            "detected_patterns": ["email"],
                            "unique_ratio": 1.0,
                            "tokenized_name": ["customer", "email"],
                        }
                    ],
                    "ground_truth": {"client_mail": "customer_email"},
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_cases"] == 1
    assert payload["accuracy"] == 1.0


def test_corrections_endpoints_persist_and_return_user_feedback() -> None:
    settings.admin_api_token = "secret-token"

    create_response = client.post(
        "/observability/corrections",
        json={
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "phone_number",
            "note": "pattern shows phone number",
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200

    list_response = client.get("/observability/corrections", headers=admin_headers())

    assert list_response.status_code == 200
    payload = list_response.json()
    assert len(payload) == 1
    assert payload[0]["corrected_target"] == "phone_number"
    assert payload[0]["version"] == 1
    assert payload[0]["correction_id"] is not None


def test_runtime_config_endpoints_expose_and_reload_settings() -> None:
    settings.admin_api_token = "secret-token"

    get_response = client.get("/observability/config", headers=admin_headers())

    assert get_response.status_code == 200
    assert "llm_provider" in get_response.json()

    reload_response = client.post("/observability/config/reload", headers=admin_headers())

    assert reload_response.status_code == 200
    assert "sqlite_path" in reload_response.json()


def test_benchmark_dataset_endpoints_save_list_and_run_custom_benchmark() -> None:
    settings.admin_api_token = "secret-token"

    create_response = client.post(
        "/evaluation/datasets",
        json={
            "name": "email-case",
            "cases": [
                {
                    "source_columns": [
                        {
                            "name": "client_mail",
                            "sample_values": ["ana@example.com"],
                            "distinct_sample_values": ["ana@example.com"],
                            "detected_patterns": ["email"],
                            "unique_ratio": 1.0,
                            "tokenized_name": ["client", "mail"],
                        }
                    ],
                    "target_columns": [
                        {
                            "name": "customer_email",
                            "sample_values": ["ana@example.com"],
                            "distinct_sample_values": ["ana@example.com"],
                            "detected_patterns": ["email"],
                            "unique_ratio": 1.0,
                            "tokenized_name": ["customer", "email"],
                        }
                    ],
                    "ground_truth": {"client_mail": "customer_email"},
                }
            ],
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200
    dataset_id = create_response.json()["dataset_id"]

    list_response = client.get("/evaluation/datasets", headers=admin_headers())
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["version"] == 1

    run_response = client.post(f"/evaluation/datasets/{dataset_id}/run", headers=admin_headers())
    assert run_response.status_code == 200
    assert run_response.json()["accuracy"] == 1.0

    runs_response = client.get("/evaluation/runs", headers=admin_headers())
    assert runs_response.status_code == 200
    assert len(runs_response.json()) == 1
    assert runs_response.json()[0]["dataset_id"] == dataset_id


def upload_example_datasets() -> dict:
    response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.csv",
                csv_bytes("cust_id,phone\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id,phone_number\n1,0641234567\n2,0659998888\n"),
                "text/csv",
            ),
        },
    )
    assert response.status_code == 200
    return response.json()


def build_row_format_upload(file_format: str, dataset_role: str) -> tuple[str, bytes, str]:
    if dataset_role == "source":
        headers = ["client_mail", "primary_phone"]
        rows = [["ana@example.com", "0641234567"]]
        json_payload = '[{"client_mail": "ana@example.com", "primary_phone": "0641234567"}]'
        xml_payload = (
            "<rows>"
            "<row><client_mail>ana@example.com</client_mail><primary_phone>0641234567</primary_phone></row>"
            "</rows>"
        )
    else:
        headers = ["customer_email", "phone_number"]
        rows = [["ana@example.com", "0641234567"]]
        json_payload = '[{"customer_email": "ana@example.com", "phone_number": "0641234567"}]'
        xml_payload = (
            "<rows>"
            "<row><customer_email>ana@example.com</customer_email><phone_number>0641234567</phone_number></row>"
            "</rows>"
        )

    if file_format == "csv":
        return (
            f"{dataset_role}.csv",
            csv_bytes(",".join(headers) + "\n" + ",".join(str(value) for value in rows[0]) + "\n"),
            "text/csv",
        )
    if file_format == "json":
        return (f"{dataset_role}.json", json_bytes(json_payload), "application/json")
    if file_format == "xml":
        return (f"{dataset_role}.xml", xml_bytes(xml_payload), "application/xml")
    if file_format == "xlsx":
        return (
            f"{dataset_role}.xlsx",
            xlsx_bytes(headers, rows),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    raise ValueError(f"Unsupported test format: {file_format}")


def csv_bytes(value: str) -> bytes:
    return value.encode("utf-8")


def json_bytes(value: str) -> bytes:
    return value.encode("utf-8")


def sql_bytes(value: str) -> bytes:
    return value.encode("utf-8")


def xml_bytes(value: str) -> bytes:
    return value.encode("utf-8")


def xlsx_bytes(headers: list[str], rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    return buffer.getvalue()


def admin_headers() -> dict[str, str]:
    if not settings.admin_api_token:
        return {}
    return {"X-Admin-Token": settings.admin_api_token}