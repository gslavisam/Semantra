from __future__ import annotations

import json
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.config import settings
from app.main import app
from app.models.mapping import CanonicalGapSuggestion, MappingJobStatusResponse
from app.services.correction_service import correction_store
from app.services.decision_log_service import decision_log_store
from app.services.llm_service import StaticLLMProvider
from app.services.mapping_job_service import MappingJobCapacityError, mapping_job_store
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service
from app.services.upload_store import dataset_store


client = TestClient(app)


def setup_function() -> None:
    dataset_store.clear()
    decision_log_store.clear()
    correction_store.clear()
    correction_store.clear_reusable_rules()
    persistence_service.clear_mapping_sets()
    persistence_service.clear_benchmark_datasets()
    persistence_service.clear_evaluation_runs()
    persistence_service.clear_transformation_test_sets()
    persistence_service.clear_knowledge_overlays()
    persistence_service.clear_knowledge_stewardship_items()
    persistence_service.clear_knowledge_audit_logs()
    mapping_job_store.clear()
    metadata_knowledge_service.refresh()
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


def test_auto_map_job_reports_progress_activity() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.csv",
                csv_bytes("client_mail,primary_phone\nana@example.com,0641234567\n"),
                "text/csv",
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

    start_response = client.post(
        "/mapping/auto/jobs",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "target_dataset_id": payload["target"]["dataset_id"],
            "use_llm": False,
        },
    )

    assert start_response.status_code == 200
    job_id = start_response.json()["job_id"]

    status_payload = None
    for _ in range(50):
        status_response = client.get(f"/mapping/jobs/{job_id}")
        assert status_response.status_code == 200
        status_payload = status_response.json()
        if status_payload["status"] == "completed":
            break
        time.sleep(0.01)

    assert status_payload is not None
    assert status_payload["status"] == "completed"
    assert any("Ranking 1/2: client_mail" in line for line in status_payload["activity"])
    assert any("Selected 1/2: client_mail" in line for line in status_payload["activity"])
    mappings = {item["source"]: item["target"] for item in status_payload["response"]["mappings"]}
    assert mappings["client_mail"] == "customer_email"


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


def test_auto_map_job_returns_429_when_job_capacity_is_reached() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.csv",
                csv_bytes("client_mail,primary_phone\nana@example.com,0641234567\n"),
                "text/csv",
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

    with patch(
        "app.api.routes.mapping.mapping_job_store.start",
        side_effect=MappingJobCapacityError("Too many active mapping jobs (4/4). Try again after current jobs finish."),
    ):
        response = client.post(
            "/mapping/auto/jobs",
            json={
                "source_dataset_id": payload["source"]["dataset_id"],
                "target_dataset_id": payload["target"]["dataset_id"],
                "use_llm": False,
            },
        )

    assert response.status_code == 429
    assert "Too many active mapping jobs" in response.json()["detail"]
    assert response.headers["Retry-After"] == "5"
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


def test_cancel_mapping_job_endpoint_returns_cancel_requested_status() -> None:
    with patch(
        "app.api.routes.mapping.mapping_job_store.cancel",
        return_value=MappingJobStatusResponse(
            job_id="job-123",
            status="cancel_requested",
            activity=["12:00:00 | Cancellation requested; the current step will stop at the next progress checkpoint."],
            response=None,
            error=None,
        ),
    ):
        response = client.post("/mapping/jobs/job-123/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancel_requested"
    assert "Cancellation requested" in response.json()["activity"][0]


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
    assert payload["canonical_coverage"]["source"]["total_columns"] == 2
    assert payload["canonical_coverage"]["target"]["total_columns"] == 2
    assert payload["canonical_coverage"]["project"]["total_columns"] == 4
    assert payload["canonical_coverage"]["project"]["matched_columns"] == 4
    assert payload["canonical_coverage"]["project"]["shared_concept_count"] >= 1
    first_ranked = payload["ranked_mappings"][0]
    assert first_ranked["selected"] is not None
    assert first_ranked["candidates"]
    assert "canonical_details" in payload["mappings"][0]
    assert "shared_concepts" in payload["mappings"][0]["canonical_details"]
    assert payload["mappings"][0]["target"] in {"customer_id", "phone_number"}


def test_knowledge_overlay_validate_create_activate_and_reload_flow() -> None:
    overlay_csv = csv_bytes(
        "entry_type,canonical_term,alias,domain,source_system,note\n"
        "field_alias,customer id,LEGACY_CUST,master_data,LegacyERP,Legacy customer identifier\n"
    )

    validate_response = client.post(
        "/knowledge/overlays/validate",
        files={"file": ("knowledge_overlay.csv", overlay_csv, "text/csv")},
    )

    assert validate_response.status_code == 200
    assert validate_response.json()["valid_rows"] == 1

    create_response = client.post(
        "/knowledge/overlays",
        data={"name": "overlay-v1", "created_by": "demo-user"},
        files={"file": ("knowledge_overlay.csv", overlay_csv, "text/csv")},
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    overlay_id = create_payload["version"]["overlay_id"]
    assert create_payload["saved_entry_count"] == 1
    assert create_payload["version"]["status"] == "validated"
    assert create_payload["version"]["created_by"] == "demo-user"

    audit_after_create_response = client.get("/knowledge/audit")
    assert audit_after_create_response.status_code == 200
    assert audit_after_create_response.json()[0]["action"] == "create"

    list_response = client.get("/knowledge/overlays")
    assert list_response.status_code == 200
    assert list_response.json()[0]["overlay_id"] == overlay_id
    assert list_response.json()[0]["created_by"] == "demo-user"

    detail_response = client.get(f"/knowledge/overlays/{overlay_id}")
    assert detail_response.status_code == 200
    assert detail_response.json()["entries"][0]["alias"] == "LEGACY_CUST"
    assert detail_response.json()["version"]["created_by"] == "demo-user"

    activate_response = client.post(f"/knowledge/overlays/{overlay_id}/activate")
    assert activate_response.status_code == 200
    assert activate_response.json()["status"] == "active"

    reload_response = client.post("/knowledge/reload")
    assert reload_response.status_code == 200
    assert reload_response.json()["mode"] == "overlay_active"
    assert reload_response.json()["active_overlay_id"] == overlay_id
    assert reload_response.json()["active_overlay_name"] == "overlay-v1"
    assert reload_response.json()["active_entry_count"] == 1
    assert reload_response.json()["entry_type_counts"] == {"field_alias": 1}

    deactivate_response = client.post(f"/knowledge/overlays/{overlay_id}/deactivate")
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["status"] == "validated"

    base_only_reload_response = client.post("/knowledge/reload")
    assert base_only_reload_response.status_code == 200
    assert base_only_reload_response.json()["mode"] == "base_only"
    assert base_only_reload_response.json()["active_overlay_id"] is None

    create_response_v2 = client.post(
        "/knowledge/overlays",
        data={"name": "overlay-v2"},
        files={"file": ("knowledge_overlay.csv", overlay_csv, "text/csv")},
    )
    assert create_response_v2.status_code == 200
    overlay_id_v2 = create_response_v2.json()["version"]["overlay_id"]

    activate_response_v1 = client.post(f"/knowledge/overlays/{overlay_id}/activate")
    assert activate_response_v1.status_code == 200
    activate_response_v2 = client.post(f"/knowledge/overlays/{overlay_id_v2}/activate")
    assert activate_response_v2.status_code == 200

    rollback_response = client.post("/knowledge/overlays/rollback")
    assert rollback_response.status_code == 200
    assert rollback_response.json()["mode"] == "overlay_active"
    assert rollback_response.json()["active_overlay_id"] == overlay_id

    audit_response = client.get("/knowledge/audit")
    assert audit_response.status_code == 200
    audit_actions = [entry["action"] for entry in audit_response.json()]
    assert "activate" in audit_actions
    assert "deactivate" in audit_actions
    assert "rollback" in audit_actions

    archive_response = client.post(f"/knowledge/overlays/{overlay_id}/archive")
    assert archive_response.status_code == 200
    assert archive_response.json()["status"] == "archived"

    archive_again_response = client.post(f"/knowledge/overlays/{overlay_id}/archive")
    assert archive_again_response.status_code == 409
    assert archive_again_response.json()["detail"] == (
        "Only validated or active knowledge overlays can be archived. Current status: archived."
    )

    archived_activate_response = client.post(f"/knowledge/overlays/{overlay_id}/activate")
    assert archived_activate_response.status_code == 409
    assert archived_activate_response.json()["detail"] == "Only validated knowledge overlays can be activated. Current status: archived."


def test_canonical_glossary_export_and_import_flow() -> None:
    glossary_path = Path(metadata_knowledge_service.canonical_glossary_path)
    original_payload = glossary_path.read_text(encoding="utf-8")
    try:
        export_response = client.get("/knowledge/canonical-glossary/export")
        assert export_response.status_code == 200
        assert "concept_id,entity,attribute,display_name,description,data_type,aliases" in export_response.text
        assert "customer.id" in export_response.text

        import_payload = csv_bytes(
            "concept_id,entity,attribute,display_name,description,data_type,aliases\n"
            'loyalty.id,loyalty,id,Loyalty ID,Identifier for a loyalty profile,string,"loyalty id, loyalty identifier"\n'
        )
        import_response = client.post(
            "/knowledge/canonical-glossary/import",
            files={"file": ("canonical_glossary.csv", import_payload, "text/csv")},
        )
        assert import_response.status_code == 200
        assert import_response.json()["imported_row_count"] == 1
        assert import_response.json()["canonical_concept_count"] == 1

        reexport_response = client.get("/knowledge/canonical-glossary/export")
        assert reexport_response.status_code == 200
        assert "loyalty.id" in reexport_response.text

        reload_response = client.post("/knowledge/reload")
        assert reload_response.status_code == 200
        assert reload_response.json()["canonical_concept_count"] == 1
    finally:
        glossary_path.write_text(original_payload, encoding="utf-8")
        metadata_knowledge_service.refresh()


def test_knowledge_reseed_endpoint_refreshes_runtime_and_writes_audit_entry() -> None:
    response = client.post("/knowledge/reseed")

    assert response.status_code == 200
    payload = response.json()
    assert payload["concept_count"] > 0
    assert payload["canonical_concept_count"] > 0

    audit_response = client.get("/knowledge/audit")
    assert audit_response.status_code == 200
    assert any(entry["action"] == "reseed" for entry in audit_response.json())


def test_canonical_glossary_export_excludes_active_overlay_aliases() -> None:
    overlay_response = client.post(
        "/knowledge/overlays",
        data={"name": "overlay-canonical-export"},
        files={
            "file": (
                "knowledge_overlay.csv",
                csv_bytes(
                    "entry_type,canonical_term,alias,domain,source_system,note\n"
                    "concept_alias,Customer ID,legacy_customer_identifier,master_data,LegacyERP,Canonical alias\n"
                ),
                "text/csv",
            )
        },
    )
    assert overlay_response.status_code == 200
    overlay_id = overlay_response.json()["version"]["overlay_id"]

    activate_response = client.post(f"/knowledge/overlays/{overlay_id}/activate")
    assert activate_response.status_code == 200

    export_response = client.get("/knowledge/canonical-glossary/export")
    assert export_response.status_code == 200
    assert "legacy customer identifier" not in export_response.text
    assert "customer.id" in export_response.text


def test_canonical_gap_candidates_and_approve_endpoint_persist_overlay_alias() -> None:
    mapping_response = {
        "mappings": [
            {
                "source": "NTGEW",
                "target": "net_weight",
                "confidence": 0.72,
                "confidence_label": "medium_confidence",
                "status": "needs_review",
                "method": "multi_signal_heuristic",
                "signals": {"name": 0.8, "semantic": 0.75},
                "explanation": ["Name and semantic signals strongly align."],
                "canonical_details": {"source_concepts": [], "target_concepts": [], "shared_concepts": []},
            }
        ],
        "ranked_mappings": [],
        "canonical_coverage": {},
    }

    candidates_response = client.post(
        "/knowledge/canonical-gaps/candidates",
        json={"mapping_response": mapping_response},
    )

    assert candidates_response.status_code == 200
    candidates = candidates_response.json()["candidates"]
    assert len(candidates) == 1

    proposal_state_response = client.post(
        "/knowledge/canonical-gaps/proposal-state",
        json={
            "candidate_key": "canonical_gap_NTGEW_net_weight",
            "candidate": candidates[0],
            "proposal_state": "ready_for_approval",
            "reviewed_by": "test-reviewer",
        },
    )

    assert proposal_state_response.status_code == 200

    approve_response = client.post(
        "/knowledge/canonical-gaps/approve",
        json={
            "candidate": candidates[0],
            "suggestion": {
                "action": "new_canonical_concept",
                "concept_id": "material.net_weight",
                "display_name": "Material Net Weight",
                "aliases": ["NTGEW", "net_weight", "MARA-NTGEW"],
                "confidence": 0.88,
                "reasoning": ["SAP NTGEW and net_weight describe material net weight."],
            },
            "approved_by": "test",
        },
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["activated"] is True
    assert metadata_knowledge_service.resolve_canonical_concept_id("NTGEW") == "material.net_weight"


def test_canonical_gap_approve_endpoint_blocks_without_ready_for_approval_state() -> None:
    mapping_response = {
        "mappings": [
            {
                "source": "NTGEW",
                "target": "net_weight",
                "confidence": 0.72,
                "confidence_label": "medium_confidence",
                "status": "needs_review",
                "method": "multi_signal_heuristic",
                "signals": {"name": 0.8, "semantic": 0.75},
                "explanation": ["Name and semantic signals strongly align."],
                "canonical_details": {"source_concepts": [], "target_concepts": [], "shared_concepts": []},
            }
        ],
        "ranked_mappings": [],
        "canonical_coverage": {},
    }

    candidates_response = client.post(
        "/knowledge/canonical-gaps/candidates",
        json={"mapping_response": mapping_response},
    )

    assert candidates_response.status_code == 200
    candidate = candidates_response.json()["candidates"][0]

    approve_response = client.post(
        "/knowledge/canonical-gaps/approve",
        json={
            "candidate": candidate,
            "suggestion": {
                "action": "new_canonical_concept",
                "concept_id": "material.net_weight",
                "display_name": "Material Net Weight",
                "aliases": ["NTGEW", "net_weight", "MARA-NTGEW"],
                "confidence": 0.88,
                "reasoning": ["SAP NTGEW and net_weight describe material net weight."],
            },
            "approved_by": "test",
        },
    )

    assert approve_response.status_code == 409
    assert approve_response.json()["detail"] == (
        "Canonical gap approval is blocked until proposal triage is ready_for_approval. Current state: new."
    )


def test_canonical_concept_registry_and_detail_expose_usage_and_active_overlay_aliases() -> None:
    create_mapping_set_response = client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "source_dataset_id": "source-1",
            "target_dataset_id": "target-1",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "interface_type": "batch",
            "description": "Customer master sync",
            "artifact_type": "standard",
            "canonical_concepts": ["customer.id"],
            "unmatched_sources": [],
            "mapping_decisions": [
                {"source": "KUNNR", "target": "customer_id", "status": "accepted"},
            ],
            "created_by": "demo-user",
        },
    )
    assert create_mapping_set_response.status_code == 200

    overlay_response = client.post(
        "/knowledge/overlays",
        data={"name": "overlay-canonical-console", "created_by": "demo-user"},
        files={
            "file": (
                "knowledge_overlay.csv",
                csv_bytes(
                    "entry_type,canonical_term,alias,domain,source_system,note\n"
                    "concept_alias,Customer ID,legacy_customer_identifier,master_data,LegacyERP,Canonical console alias\n"
                ),
                "text/csv",
            )
        },
    )
    assert overlay_response.status_code == 200
    overlay_id = overlay_response.json()["version"]["overlay_id"]

    activate_response = client.post(f"/knowledge/overlays/{overlay_id}/activate")
    assert activate_response.status_code == 200

    list_response = client.get("/knowledge/canonical-concepts")
    detail_response = client.get("/knowledge/canonical-concepts/customer.id")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200

    concept_list = list_response.json()
    customer_id = next(item for item in concept_list if item["concept_id"] == "customer.id")
    assert customer_id["usage_count"] >= 1
    assert customer_id["source"] == "base_plus_active_overlay"
    assert "legacy_customer_identifier" in customer_id["active_overlay_aliases"]

    detail = detail_response.json()
    assert detail["concept"]["concept_id"] == "customer.id"
    assert detail["concept"]["active_overlay_entry_count"] == 1
    assert detail["active_overlay_entries"][0]["overlay_id"] == overlay_id
    assert detail["active_overlay_entries"][0]["alias"] == "legacy_customer_identifier"
    assert detail["integrations"][0]["integration_name"] == "Customer Master Sync"
    assert any(entry["action"] == "activate" for entry in detail["audit_entries"])


def test_material_canonical_gap_suggest_approve_and_rerun_flow() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "material_source.csv",
                csv_bytes("NTGEW\n10.5\n12.0\n"),
                "text/csv",
            ),
            "target_file": (
                "material_target.csv",
                csv_bytes("net_weight,gross_weight\n10.5,11.0\n12.0,12.5\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()

    initial_map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert initial_map_response.status_code == 200
    initial_mapping = initial_map_response.json()["mappings"][0]
    assert initial_mapping["source"] == "NTGEW"
    assert initial_mapping["target"] == "net_weight"
    assert initial_mapping["canonical_details"]["shared_concepts"] == []

    candidates_response = client.post(
        "/knowledge/canonical-gaps/candidates",
        json={"mapping_response": initial_map_response.json()},
    )

    assert candidates_response.status_code == 200
    candidate = candidates_response.json()["candidates"][0]

    with patch(
        "app.api.routes.knowledge.call_canonical_gap_assistant",
        return_value=CanonicalGapSuggestion(
            action="new_canonical_concept",
            concept_id="material.net_weight",
            display_name="Material Net Weight",
            aliases=["NTGEW", "net_weight", "MARA-NTGEW"],
            confidence=0.88,
            reasoning=["SAP NTGEW and net_weight describe material net weight."],
            risk_notes=["Overlay-only approval keeps this change reviewable."],
        ),
    ):
        suggest_response = client.post(
            "/knowledge/canonical-gaps/suggest",
            json={"candidate": candidate},
        )

    assert suggest_response.status_code == 200
    suggestion = suggest_response.json()
    assert suggestion["action"] == "new_canonical_concept"
    assert suggestion["concept_id"] == "material.net_weight"

    proposal_state_response = client.post(
        "/knowledge/canonical-gaps/proposal-state",
        json={
            "candidate_key": "canonical_gap_NTGEW_net_weight",
            "candidate": candidate,
            "proposal_state": "ready_for_approval",
            "reviewed_by": "test-reviewer",
        },
    )

    assert proposal_state_response.status_code == 200

    approve_response = client.post(
        "/knowledge/canonical-gaps/approve",
        json={
            "candidate": candidate,
            "suggestion": suggestion,
            "approved_by": "test",
        },
    )

    assert approve_response.status_code == 200
    assert approve_response.json()["activated"] is True

    rerun_map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert rerun_map_response.status_code == 200
    rerun_mapping = rerun_map_response.json()["mappings"][0]
    assert rerun_mapping["target"] == "net_weight"
    assert rerun_mapping["signals"]["canonical"] > 0
    assert [concept["concept_id"] for concept in rerun_mapping["canonical_details"]["shared_concepts"]] == [
        "material.net_weight"
    ]


def test_material_canonical_gap_reject_persists_audit_event() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "material_source.csv",
                csv_bytes("NTGEW\n10.5\n12.0\n"),
                "text/csv",
            ),
            "target_file": (
                "material_target.csv",
                csv_bytes("net_weight,gross_weight\n10.5,11.0\n12.0,12.5\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()

    initial_map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert initial_map_response.status_code == 200

    candidates_response = client.post(
        "/knowledge/canonical-gaps/candidates",
        json={"mapping_response": initial_map_response.json()},
    )

    assert candidates_response.status_code == 200
    candidate = candidates_response.json()["candidates"][0]

    with patch(
        "app.api.routes.knowledge.call_canonical_gap_assistant",
        return_value=CanonicalGapSuggestion(
            action="new_canonical_concept",
            concept_id="material.net_weight",
            display_name="Material Net Weight",
            aliases=["NTGEW", "net_weight", "MARA-NTGEW"],
            confidence=0.88,
            reasoning=["SAP NTGEW and net_weight describe material net weight."],
            risk_notes=["Overlay-only approval keeps this change reviewable."],
        ),
    ):
        suggest_response = client.post(
            "/knowledge/canonical-gaps/suggest",
            json={"candidate": candidate},
        )

    assert suggest_response.status_code == 200
    suggestion = suggest_response.json()

    reject_response = client.post(
        "/knowledge/canonical-gaps/reject",
        json={
            "candidate": candidate,
            "suggestion": suggestion,
            "disposition": "rejected",
            "rejected_by": "test-reviewer",
            "note": "Duplicate with an existing material weight concept under review.",
        },
    )

    assert reject_response.status_code == 200
    reject_payload = reject_response.json()
    assert reject_payload["action"] == "reject"
    assert "NTGEW -> net_weight" in reject_payload["message"]
    assert "Disposition=rejected." in reject_payload["message"]
    assert "Rejected by=test-reviewer." in reject_payload["message"]

    audit_response = client.get("/knowledge/audit")
    assert audit_response.status_code == 200
    assert any(
        entry["action"] == "reject"
        and "Concept=material.net_weight." in entry["message"]
        and "Duplicate with an existing material weight concept under review." in entry["message"]
        for entry in audit_response.json()
    )


def test_material_canonical_gap_ignore_persists_audit_event() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "material_source.csv",
                csv_bytes("NTGEW\n10.5\n12.0\n"),
                "text/csv",
            ),
            "target_file": (
                "material_target.csv",
                csv_bytes("net_weight,gross_weight\n10.5,11.0\n12.0,12.5\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()

    initial_map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert initial_map_response.status_code == 200

    candidates_response = client.post(
        "/knowledge/canonical-gaps/candidates",
        json={"mapping_response": initial_map_response.json()},
    )

    assert candidates_response.status_code == 200
    candidate = candidates_response.json()["candidates"][0]

    ignore_response = client.post(
        "/knowledge/canonical-gaps/reject",
        json={
            "candidate": candidate,
            "disposition": "ignored",
            "rejected_by": "test-reviewer",
            "note": "Keep this visible only in review for now.",
        },
    )

    assert ignore_response.status_code == 200
    ignore_payload = ignore_response.json()
    assert ignore_payload["action"] == "ignore"
    assert "Ignored canonical gap suggestion for NTGEW -> net_weight." in ignore_payload["message"]
    assert "Disposition=ignored." in ignore_payload["message"]
    assert "Reviewed by=test-reviewer." in ignore_payload["message"]

    audit_response = client.get("/knowledge/audit")
    assert audit_response.status_code == 200
    assert any(
        entry["action"] == "ignore"
        and "NTGEW -> net_weight" in entry["message"]
        and "Keep this visible only in review for now." in entry["message"]
        for entry in audit_response.json()
    )


def test_material_canonical_gap_proposal_state_persists_latest_triage() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "material_source.csv",
                csv_bytes("NTGEW\n10.5\n12.0\n"),
                "text/csv",
            ),
            "target_file": (
                "material_target.csv",
                csv_bytes("net_weight,gross_weight\n10.5,11.0\n12.0,12.5\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()

    initial_map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert initial_map_response.status_code == 200

    candidates_response = client.post(
        "/knowledge/canonical-gaps/candidates",
        json={"mapping_response": initial_map_response.json()},
    )

    assert candidates_response.status_code == 200
    candidate = candidates_response.json()["candidates"][0]
    candidate_key = "canonical_gap_NTGEW_net_weight"

    first_triage_response = client.post(
        "/knowledge/canonical-gaps/proposal-state",
        json={
            "candidate_key": candidate_key,
            "candidate": candidate,
            "proposal_state": "needs_review",
            "reviewed_by": "test-reviewer",
            "note": "Need SME confirmation.",
        },
    )

    assert first_triage_response.status_code == 200
    assert first_triage_response.json()["proposal_state"] == "needs_review"

    second_triage_response = client.post(
        "/knowledge/canonical-gaps/proposal-state",
        json={
            "candidate_key": candidate_key,
            "candidate": candidate,
            "proposal_state": "ready_for_approval",
            "reviewed_by": "test-reviewer",
        },
    )

    assert second_triage_response.status_code == 200
    triage_payload = second_triage_response.json()
    assert triage_payload["candidate_key"] == candidate_key
    assert triage_payload["proposal_state"] == "ready_for_approval"

    proposal_states_response = client.get("/knowledge/canonical-gaps/proposal-states")
    assert proposal_states_response.status_code == 200
    assert proposal_states_response.json() == [
        {
            "candidate_key": candidate_key,
            "source": "NTGEW",
            "target": "net_weight",
            "proposal_state": "ready_for_approval",
            "reviewed_by": "test-reviewer",
            "note": None,
            "created_at": triage_payload["created_at"],
        }
    ]

    audit_response = client.get("/knowledge/audit")
    assert audit_response.status_code == 200
    assert any(
        entry["action"] == "triage"
        and "NTGEW -> net_weight" in entry["message"]
        and "State=ready_for_approval." in entry["message"]
        for entry in audit_response.json()
    )


def test_material_canonical_gap_stewardship_item_create_and_status_update() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "material_source.csv",
                csv_bytes("NTGEW\n10.5\n12.0\n"),
                "text/csv",
            ),
            "target_file": (
                "material_target.csv",
                csv_bytes("net_weight,gross_weight\n10.5,11.0\n12.0,12.5\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    upload_payload = upload_response.json()

    initial_map_response = client.post(
        "/mapping/auto",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "target_dataset_id": upload_payload["target"]["dataset_id"],
        },
    )

    assert initial_map_response.status_code == 200

    candidates_response = client.post(
        "/knowledge/canonical-gaps/candidates",
        json={"mapping_response": initial_map_response.json()},
    )

    assert candidates_response.status_code == 200
    candidate = candidates_response.json()["candidates"][0]
    item_key = "canonical_gap_NTGEW_net_weight"

    create_response = client.post(
        "/knowledge/stewardship-items",
        json={
            "item_type": "canonical_gap",
            "item_key": item_key,
            "title": "NTGEW -> net_weight",
            "status": "needs_review",
            "source": "NTGEW",
            "target": "net_weight",
            "owner": "data-governance",
            "assignee": "analyst-1",
            "review_note": "Needs confirmation from material SME.",
            "candidate_payload": candidate,
            "created_by": "test-reviewer",
            "changed_by": "test-reviewer",
        },
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["item_key"] == item_key
    assert create_payload["status"] == "needs_review"
    assert create_payload["owner"] == "data-governance"
    assert create_payload["candidate_payload"]["source"] == "NTGEW"

    list_response = client.get("/knowledge/stewardship-items", params={"item_type": "canonical_gap"})
    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "item_id": create_payload["item_id"],
            "item_type": "canonical_gap",
            "item_key": item_key,
            "title": "NTGEW -> net_weight",
            "status": "needs_review",
            "concept_id": None,
            "source": "NTGEW",
            "target": "net_weight",
            "source_system": None,
            "business_domain": None,
            "owner": "data-governance",
            "assignee": "analyst-1",
            "review_note": "Needs confirmation from material SME.",
            "created_by": "test-reviewer",
            "changed_by": "test-reviewer",
            "created_at": create_payload["created_at"],
            "updated_at": create_payload["updated_at"],
        }
    ]

    update_response = client.post(
        f"/knowledge/stewardship-items/{create_payload['item_id']}/status",
        json={
            "status": "ready_for_approval",
            "changed_by": "lead-reviewer",
            "assignee": "mdm-lead",
            "review_note": "Validated with material owner.",
            "note": "Promote to approval-ready after SME confirmation.",
        },
    )

    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["status"] == "ready_for_approval"
    assert update_payload["assignee"] == "mdm-lead"
    assert update_payload["review_note"] == "Validated with material owner."

    detail_response = client.get(f"/knowledge/stewardship-items/{create_payload['item_id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["candidate_payload"]["target"] == "net_weight"
    assert detail_response.json()["status"] == "ready_for_approval"

    audit_response = client.get("/knowledge/audit")
    assert audit_response.status_code == 200
    audit_entries = audit_response.json()
    assert any(
        entry["action"] == "stewardship"
        and f"canonical_gap:{item_key}" in entry["message"]
        and "Status=needs_review." in entry["message"]
        for entry in audit_entries
    )
    assert any(
        entry["action"] == "stewardship"
        and f"canonical_gap:{item_key}" in entry["message"]
        and "Status=ready_for_approval." in entry["message"]
        for entry in audit_entries
    )


def test_overlay_promotion_stewardship_item_create_and_status_update() -> None:
    overlay_response = client.post(
        "/knowledge/overlays",
        data={"name": "overlay-promotion-v1", "created_by": "demo-user"},
        files={
            "file": (
                "knowledge_overlay.csv",
                csv_bytes(
                    "entry_type,canonical_term,canonical_concept_id,alias,domain,source_system,note\n"
                    "concept_alias,Customer ID,customer.id,legacy_customer_identifier,master_data,LegacyERP,Promotion candidate\n"
                ),
                "text/csv",
            )
        },
    )

    assert overlay_response.status_code == 200
    overlay_id = overlay_response.json()["version"]["overlay_id"]

    activate_response = client.post(f"/knowledge/overlays/{overlay_id}/activate")
    assert activate_response.status_code == 200

    detail_response = client.get(f"/knowledge/overlays/{overlay_id}")
    assert detail_response.status_code == 200
    entry = detail_response.json()["entries"][0]
    item_key = f"overlay_promotion_{overlay_id}_{entry['entry_id']}"

    create_response = client.post(
        "/knowledge/stewardship-items",
        json={
            "item_type": "overlay_promotion",
            "item_key": item_key,
            "title": "Promote legacy_customer_identifier",
            "status": "new",
            "concept_id": "customer.id",
            "source": "legacy_customer_identifier",
            "target": "customer.id",
            "source_system": "LegacyERP",
            "business_domain": "master_data",
            "owner": "master-data-governance",
            "assignee": "canonical-model-owner",
            "review_note": "Candidate for base glossary promotion.",
            "overlay_entry_payload": {
                **entry,
                "overlay_id": overlay_id,
                "overlay_name": "overlay-promotion-v1",
            },
            "created_by": "demo-user",
            "changed_by": "demo-user",
        },
    )

    assert create_response.status_code == 200
    create_payload = create_response.json()
    assert create_payload["item_type"] == "overlay_promotion"
    assert create_payload["item_key"] == item_key
    assert create_payload["overlay_entry_payload"]["alias"] == "legacy_customer_identifier"

    list_response = client.get("/knowledge/stewardship-items", params={"item_type": "overlay_promotion"})
    assert list_response.status_code == 200
    assert list_response.json() == [
        {
            "item_id": create_payload["item_id"],
            "item_type": "overlay_promotion",
            "item_key": item_key,
            "title": "Promote legacy_customer_identifier",
            "status": "new",
            "concept_id": "customer.id",
            "source": "legacy_customer_identifier",
            "target": "customer.id",
            "source_system": "LegacyERP",
            "business_domain": "master_data",
            "owner": "master-data-governance",
            "assignee": "canonical-model-owner",
            "review_note": "Candidate for base glossary promotion.",
            "created_by": "demo-user",
            "changed_by": "demo-user",
            "created_at": create_payload["created_at"],
            "updated_at": create_payload["updated_at"],
        }
    ]

    update_response = client.post(
        f"/knowledge/stewardship-items/{create_payload['item_id']}/status",
        json={
            "status": "promoted",
            "changed_by": "lead-reviewer",
            "review_note": "Promoted after glossary governance review.",
            "note": "Ready for export/import into stable glossary.",
        },
    )

    assert update_response.status_code == 200
    update_payload = update_response.json()
    assert update_payload["status"] == "promoted"
    assert update_payload["review_note"] == "Promoted after glossary governance review."

    audit_response = client.get("/knowledge/audit")
    assert audit_response.status_code == 200
    assert any(
        entry["action"] == "stewardship"
        and f"overlay_promotion:{item_key}" in entry["message"]
        and "Status=promoted." in entry["message"]
        for entry in audit_response.json()
    )


def test_overlay_promotion_execute_to_canonical_glossary_updates_export_and_item_status() -> None:
    glossary_path = Path(metadata_knowledge_service.canonical_glossary_path)
    original_payload = glossary_path.read_text(encoding="utf-8")
    try:
        overlay_response = client.post(
            "/knowledge/overlays",
            data={"name": "overlay-promotion-execution", "created_by": "demo-user"},
            files={
                "file": (
                    "knowledge_overlay.csv",
                    csv_bytes(
                        "entry_type,canonical_term,canonical_concept_id,alias,domain,source_system,note\n"
                        "concept_alias,Customer ID,customer.id,legacy_customer_identifier,master_data,LegacyERP,Promotion execution candidate\n"
                    ),
                    "text/csv",
                )
            },
        )
        assert overlay_response.status_code == 200
        overlay_id = overlay_response.json()["version"]["overlay_id"]

        activate_response = client.post(f"/knowledge/overlays/{overlay_id}/activate")
        assert activate_response.status_code == 200

        detail_response = client.get(f"/knowledge/overlays/{overlay_id}")
        assert detail_response.status_code == 200
        entry = detail_response.json()["entries"][0]
        item_key = f"overlay_promotion_{overlay_id}_{entry['entry_id']}"

        create_response = client.post(
            "/knowledge/stewardship-items",
            json={
                "item_type": "overlay_promotion",
                "item_key": item_key,
                "title": "Promote legacy_customer_identifier",
                "status": "ready_for_approval",
                "concept_id": "customer.id",
                "source": "legacy_customer_identifier",
                "target": "customer.id",
                "source_system": "LegacyERP",
                "business_domain": "master_data",
                "owner": "master-data-governance",
                "assignee": "canonical-model-owner",
                "review_note": "Ready for stable glossary promotion.",
                "overlay_entry_payload": {**entry, "overlay_id": overlay_id, "overlay_name": "overlay-promotion-execution"},
                "created_by": "demo-user",
                "changed_by": "demo-user",
            },
        )
        assert create_response.status_code == 200
        item_id = create_response.json()["item_id"]

        promote_response = client.post(
            f"/knowledge/stewardship-items/{item_id}/promote-to-glossary",
            json={"changed_by": "lead-reviewer", "note": "Approved stable glossary promotion."},
        )
        assert promote_response.status_code == 200
        promote_payload = promote_response.json()
        assert promote_payload["item"]["status"] == "promoted"
        assert promote_payload["alias_added"] is True
        assert "legacy customer identifier" in promote_payload["glossary_entry"]["aliases"]

        export_response = client.get("/knowledge/canonical-glossary/export")
        assert export_response.status_code == 200
        assert "legacy customer identifier" in export_response.text

        audit_response = client.get("/knowledge/audit")
        assert audit_response.status_code == 200
        assert any(
            entry["action"] == "stewardship"
            and f"overlay_promotion:{item_key}" in entry["message"]
            and "into canonical glossary" in entry["message"]
            and "Status=promoted." in entry["message"]
            for entry in audit_response.json()
        )
    finally:
        glossary_path.write_text(original_payload, encoding="utf-8")
        metadata_knowledge_service.refresh()


def test_overlay_promotion_execute_to_canonical_glossary_creates_new_base_concept_row() -> None:
    glossary_path = Path(metadata_knowledge_service.canonical_glossary_path)
    original_payload = glossary_path.read_text(encoding="utf-8")
    try:
        overlay_response = client.post(
            "/knowledge/overlays",
            data={"name": "overlay-promotion-new-concept", "created_by": "demo-user"},
            files={
                "file": (
                    "knowledge_overlay.csv",
                    csv_bytes(
                        "entry_type,canonical_term,canonical_concept_id,alias,domain,source_system,note\n"
                        "concept_alias,Customer Shadow ID,customer.shadow_id,legacy_shadow_customer_id,master_data,LegacyERP,New canonical concept candidate\n"
                    ),
                    "text/csv",
                )
            },
        )
        assert overlay_response.status_code == 200
        overlay_id = overlay_response.json()["version"]["overlay_id"]

        activate_response = client.post(f"/knowledge/overlays/{overlay_id}/activate")
        assert activate_response.status_code == 200

        detail_response = client.get(f"/knowledge/overlays/{overlay_id}")
        assert detail_response.status_code == 200
        entry = detail_response.json()["entries"][0]
        item_key = f"overlay_promotion_{overlay_id}_{entry['entry_id']}"

        create_response = client.post(
            "/knowledge/stewardship-items",
            json={
                "item_type": "overlay_promotion",
                "item_key": item_key,
                "title": "Promote legacy_shadow_customer_id",
                "status": "ready_for_approval",
                "concept_id": "customer.shadow_id",
                "source": "legacy_shadow_customer_id",
                "target": "customer.shadow_id",
                "source_system": "LegacyERP",
                "business_domain": "master_data",
                "owner": "master-data-governance",
                "assignee": "canonical-model-owner",
                "review_note": "Create a base canonical row from overlay-only concept.",
                "overlay_entry_payload": {**entry, "overlay_id": overlay_id, "overlay_name": "overlay-promotion-new-concept"},
                "created_by": "demo-user",
                "changed_by": "demo-user",
            },
        )
        assert create_response.status_code == 200
        item_id = create_response.json()["item_id"]

        promote_response = client.post(
            f"/knowledge/stewardship-items/{item_id}/promote-to-glossary",
            json={"changed_by": "lead-reviewer", "note": "Approved new base concept promotion."},
        )
        assert promote_response.status_code == 200
        promote_payload = promote_response.json()
        assert promote_payload["item"]["status"] == "promoted"
        assert promote_payload["alias_added"] is True
        assert promote_payload["concept_created"] is True
        assert promote_payload["glossary_entry"]["concept_id"] == "customer.shadow_id"
        assert promote_payload["glossary_entry"]["display_name"] == "Customer Shadow ID"
        assert "legacy shadow customer id" in promote_payload["glossary_entry"]["aliases"]

        export_response = client.get("/knowledge/canonical-glossary/export")
        assert export_response.status_code == 200
        assert "customer.shadow_id" in export_response.text
        assert "legacy shadow customer id" in export_response.text
    finally:
        glossary_path.write_text(original_payload, encoding="utf-8")
        metadata_knowledge_service.refresh()


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
    assert payload["transformation_previews"][0]["status"] == "direct"
    assert payload["transformation_previews"][0]["classification"] == "direct"


def test_preview_allows_non_accepted_mapping_decisions_but_codegen_still_blocks() -> None:
    upload_payload = upload_example_datasets()

    preview_response = client.post(
        "/mapping/preview",
        json={
            "source_dataset_id": upload_payload["source"]["dataset_id"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer_id", "status": "needs_review"},
            ],
        },
    )
    codegen_response = client.post(
        "/mapping/codegen",
        json={
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer_id", "status": "needs_review"},
            ]
        },
    )

    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert len(preview_payload["preview"]) == 2
    assert preview_payload["preview"][0]["values"]["customer_id"] == "1"
    assert preview_payload["unresolved_targets"] == ["customer_id"]
    assert codegen_response.status_code == 409
    assert codegen_response.json()["detail"] == (
        "Code generation is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )


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
    assert preview_payload["transformation_previews"][0]["status"] == "validated"
    assert preview_payload["transformation_previews"][0]["classification"] == "safe"
    assert preview_payload["transformation_previews"][0]["before_samples"][0] == "ana.markovic@example.com"
    assert preview_payload["transformation_previews"][0]["after_samples"][0] == "Ana Markovic"


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
    assert preview_payload["transformation_previews"][0]["status"] == "fallback"
    assert preview_payload["transformation_previews"][0]["classification"] == "risky"
    assert preview_payload["transformation_previews"][0]["warnings"][0]["code"] == "runtime_error"
    assert preview_payload["transformation_previews"][0]["warnings"][0]["severity"] == "error"
    assert preview_payload["transformation_previews"][0]["warnings"][0]["fallback_applied"] is True
    assert preview_payload["transformation_previews"][0]["warnings"][0]["source"] == "email"
    assert preview_payload["transformation_previews"][0]["warnings"][0]["target"] == "customer_name"
    assert preview_payload["transformation_previews"][0]["warnings"][0]["details"]["exception_type"] == "AttributeError"


def test_preview_surfaces_transformation_syntax_errors_and_type_coercion() -> None:
    upload_response = client.post(
        "/upload",
        files={
            "source_file": (
                "source.csv",
                csv_bytes("cust_id\n1\n2\n"),
                "text/csv",
            ),
            "target_file": (
                "target.csv",
                csv_bytes("customer_id\n1\n2\n"),
                "text/csv",
            ),
        },
    )

    assert upload_response.status_code == 200
    payload = upload_response.json()

    syntax_preview_response = client.post(
        "/mapping/preview",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "mapping_decisions": [
                {
                    "source": "cust_id",
                    "target": "customer_id",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_id"] = df_source["cust_id"].astype(int',
                }
            ],
        },
    )

    assert syntax_preview_response.status_code == 200
    syntax_payload = syntax_preview_response.json()
    assert syntax_payload["preview"][0]["values"]["customer_id"] == "1"
    assert syntax_payload["transformation_previews"][0]["status"] == "fallback"
    assert syntax_payload["transformation_previews"][0]["classification"] == "risky"
    assert syntax_payload["transformation_previews"][0]["warnings"][0]["code"] == "syntax_error"
    assert syntax_payload["transformation_previews"][0]["warnings"][0]["severity"] == "error"
    assert syntax_payload["transformation_previews"][0]["warnings"][0]["details"]["line"] == 1

    coercion_preview_response = client.post(
        "/mapping/preview",
        json={
            "source_dataset_id": payload["source"]["dataset_id"],
            "mapping_decisions": [
                {
                    "source": "cust_id",
                    "target": "customer_id",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_id"] = df_source["cust_id"].astype(int)',
                }
            ],
        },
    )

    assert coercion_preview_response.status_code == 200
    coercion_payload = coercion_preview_response.json()
    warning_codes = [warning["code"] for warning in coercion_payload["transformation_previews"][0]["warnings"]]
    assert coercion_payload["transformation_previews"][0]["status"] == "validated"
    assert coercion_payload["transformation_previews"][0]["classification"] == "risky"
    assert "type_coercion" in warning_codes
    assert coercion_payload["transformation_previews"][0]["warnings"][0]["details"]["source_semantic_dtype"] == "string"
    assert coercion_payload["transformation_previews"][0]["warnings"][0]["details"]["result_semantic_dtype"] == "numeric"


def test_preview_scopes_transformation_warnings_to_rows_with_relevant_source_columns() -> None:
    from app.models.mapping import MappingDecision
    from app.models.mapping import TransformationPreviewResult, TransformationPreviewWarning
    from app.services.preview_service import build_preview

    rows = [
        {"email": "ana@example.com"},
        {"phone": "0641234567"},
    ]
    mapping_decisions = [
        MappingDecision(source="email", target="customer_name", status="accepted"),
        MappingDecision(source="phone", target="phone_number", status="accepted"),
    ]

    with patch(
        "app.services.preview_service.build_transformed_target_frame",
        return_value=(
            [
                {"customer_name": "Ana"},
                {"phone_number": "0641234567"},
            ],
            [
                TransformationPreviewResult(
                    source="email",
                    target="customer_name",
                    status="fallback",
                    classification="risky",
                    warnings=[
                        TransformationPreviewWarning(
                            code="runtime_error",
                            message="Transformation failed for email -> customer_name",
                            source="email",
                            target="customer_name",
                            severity="error",
                            fallback_applied=True,
                        )
                    ],
                )
            ],
        ),
    ):
        preview = build_preview(rows, mapping_decisions)

    assert any("Transformation failed for email -> customer_name" in warning for warning in preview.preview[0].warnings)
    assert not any("Transformation failed for email -> customer_name" in warning for warning in preview.preview[1].warnings)


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


def test_codegen_reports_structured_syntax_warning_and_falls_back_to_direct_mapping() -> None:
    response = client.post(
        "/mapping/codegen",
        json={
            "mapping_decisions": [
                {
                    "source": "cust_id",
                    "target": "customer_id",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_id"] = df_source["cust_id"].astype(int',
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert 'df_target["customer_id"] = df_source["cust_id"]' in payload["code"]
    assert payload["warnings"][0]["code"] == "syntax_error"
    assert payload["warnings"][0]["stage"] == "codegen"
    assert payload["warnings"][0]["severity"] == "error"
    assert payload["warnings"][0]["fallback_applied"] is True
    assert payload["warnings"][0]["source"] == "cust_id"
    assert payload["warnings"][0]["target"] == "customer_id"


def test_mapping_set_endpoints_save_list_load_status_and_audit() -> None:
    settings.admin_api_token = "secret-token"

    create_response = client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "source_dataset_id": "source-1",
            "target_dataset_id": "target-1",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "interface_type": "batch",
            "description": "Nightly customer sync",
            "artifact_type": "standard",
            "canonical_concepts": ["customer.id", "customer.phone"],
            "unmatched_sources": ["country_code"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer_id", "status": "accepted"},
                {"source": "phone", "target": "phone_number", "status": "needs_review"},
            ],
            "created_by": "demo-user",
            "note": "Initial draft",
            "owner": "governance-team",
            "assignee": "analyst-1",
            "review_note": "Prepared for governance review",
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200
    created = create_response.json()
    mapping_set_id = created["mapping_set_id"]
    assert created["status"] == "draft"
    assert created["version"] == 1

    list_response = client.get("/mapping/sets", headers=admin_headers())
    detail_response = client.get(f"/mapping/sets/{mapping_set_id}", headers=admin_headers())
    status_response = client.post(
        f"/mapping/sets/{mapping_set_id}/status",
        json={
            "status": "approved",
            "changed_by": "demo-user",
            "note": "Ready for production use",
            "owner": "governance-team",
            "assignee": "analyst-2",
            "review_note": "Approved for reuse",
        },
        headers=admin_headers(),
    )
    apply_response = client.post(
        f"/mapping/sets/{mapping_set_id}/apply",
        json={"changed_by": "demo-user", "note": "Applied to current review state"},
        headers=admin_headers(),
    )
    audit_response = client.get(f"/mapping/sets/{mapping_set_id}/audit", headers=admin_headers())

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert status_response.status_code == 200
    assert apply_response.status_code == 200
    assert audit_response.status_code == 200

    listed = list_response.json()
    detail = detail_response.json()
    updated = status_response.json()
    applied = apply_response.json()
    audits = audit_response.json()

    assert listed[0]["mapping_set_id"] == mapping_set_id
    assert detail["mapping_decisions"][0]["target"] == "customer_id"
    assert detail["decision_count"] == 2
    assert detail["integration_name"] == "Customer Master Sync"
    assert detail["artifact_type"] == "standard"
    assert detail["canonical_concepts"] == ["customer.id", "customer.phone"]
    assert detail["unmatched_sources"] == ["country_code"]
    assert detail["owner"] == "governance-team"
    assert detail["assignee"] == "analyst-1"
    assert detail["review_note"] == "Prepared for governance review"
    assert updated["status"] == "approved"
    assert updated["assignee"] == "analyst-2"
    assert updated["review_note"] == "Approved for reuse"
    assert applied["mapping_set_id"] == mapping_set_id
    assert audits[0]["action"] == "apply"
    assert audits[0]["created_at"] is not None
    assert audits[1]["action"] == "status_change"
    assert audits[-1]["action"] == "create"


def test_apply_mapping_set_blocks_non_approved_versions() -> None:
    settings.admin_api_token = "secret-token"

    create_response = client.post(
        "/mapping/sets",
        json={
            "name": "vendor-master",
            "source_dataset_id": "source-1",
            "target_dataset_id": "target-1",
            "mapping_decisions": [
                {"source": "vendor_id", "target": "supplier.id", "status": "accepted"},
            ],
            "created_by": "demo-user",
            "note": "Draft mapping set",
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200
    mapping_set_id = create_response.json()["mapping_set_id"]

    status_response = client.post(
        f"/mapping/sets/{mapping_set_id}/status",
        json={
            "status": "review",
            "changed_by": "demo-user",
            "note": "Ready for review",
        },
        headers=admin_headers(),
    )
    apply_response = client.post(
        f"/mapping/sets/{mapping_set_id}/apply",
        json={"changed_by": "demo-user", "note": "Attempted workspace apply"},
        headers=admin_headers(),
    )
    audit_response = client.get(f"/mapping/sets/{mapping_set_id}/audit", headers=admin_headers())

    assert status_response.status_code == 200
    assert apply_response.status_code == 409
    assert (
        apply_response.json()["detail"]
        == f"Mapping set #{mapping_set_id} is in status 'review' and cannot be applied. Only approved mapping sets can be used in workspace apply/reuse flows."
    )
    assert [entry["action"] for entry in audit_response.json()] == ["status_change", "create"]


def test_catalog_integrations_endpoint_lists_queryable_mapping_summaries() -> None:
    settings.admin_api_token = "secret-token"

    create_response = client.post(
        "/mapping/sets",
        json={
            "name": "sap-customer-canonical",
            "integration_name": "SAP Customer Canonical",
            "source_system": "SAP",
            "target_system": "canonical",
            "business_domain": "Customer",
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id"],
            "unmatched_sources": ["LAND1"],
            "mapping_decisions": [
                {"source": "KUNNR", "target": "customer.id", "status": "accepted"},
                {"source": "LAND1", "target": "customer.country", "status": "needs_review"},
            ],
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200

    list_response = client.get(
        "/catalog/integrations",
        params={"artifact_type": "canonical-only", "integration_name": "SAP Customer"},
        headers=admin_headers(),
    )

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload[0]["integration_name"] == "SAP Customer Canonical"
    assert payload[0]["artifact_type"] == "canonical-only"
    assert payload[0]["source_system"] == "SAP"
    assert payload[0]["canonical_concepts"] == ["customer.id"]
    assert payload[0]["unmatched_sources"] == ["LAND1"]


def test_catalog_integration_detail_endpoint_returns_versions_and_latest_approved() -> None:
    settings.admin_api_token = "secret-token"

    first_response = client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )
    first_id = first_response.json()["mapping_set_id"]
    client.post(
        f"/mapping/sets/{first_id}/status",
        json={"status": "approved", "owner": "governance-team"},
        headers=admin_headers(),
    )
    client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "canonical_concepts": ["customer.id", "customer.name"],
            "unmatched_sources": ["LAND1"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )

    detail_response = client.get(
        "/catalog/integrations/Customer Master Sync",
        headers=admin_headers(),
    )

    assert detail_response.status_code == 200
    payload = detail_response.json()
    assert payload["integration_name"] == "Customer Master Sync"
    assert payload["latest_version"]["version"] == 2
    assert payload["latest_approved_version"]["version"] == 1
    assert payload["canonical_concepts"] == ["customer.id", "customer.name"]
    assert payload["unmatched_sources"] == ["LAND1"]
    assert [item["version"] for item in payload["versions"]] == [2, 1]


def test_catalog_integration_detail_endpoint_returns_similar_integrations() -> None:
    settings.admin_api_token = "secret-token"

    client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id", "customer.name", "customer.country_code"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )
    client.post(
        "/mapping/sets",
        json={
            "name": "lead-reuse",
            "integration_name": "Lead Reuse Sync",
            "source_system": "CRM",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id", "customer.name"],
            "mapping_decisions": [
                {"source": "lead_ref", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )

    response = client.get("/catalog/integrations/Customer%20Master%20Sync", headers=admin_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["similar_integrations"][0]["integration_name"] == "Lead Reuse Sync"
    assert payload["similar_integrations"][0]["shared_concepts"] == ["customer.id", "customer.name"]
    assert payload["similar_integrations"][0]["same_target_system"] is True


def test_catalog_concept_endpoint_returns_matching_integrations() -> None:
    settings.admin_api_token = "secret-token"

    client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )
    client.post(
        "/mapping/sets",
        json={
            "name": "lead-master",
            "integration_name": "Lead Reuse Sync",
            "source_system": "CRM",
            "target_system": "Salesforce",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {"source": "lead_ref", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )

    concept_response = client.get(
        "/catalog/concepts/customer.id",
        headers=admin_headers(),
    )

    assert concept_response.status_code == 200
    payload = concept_response.json()
    assert payload["concept_id"] == "customer.id"
    assert payload["usage_count"] == 2
    assert [item["integration_name"] for item in payload["integrations"]] == [
        "Customer Master Sync",
        "Lead Reuse Sync",
    ]


def test_canonical_concept_registry_exposes_source_system_and_business_domain_facets() -> None:
    settings.admin_api_token = "secret-token"

    client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )
    client.post(
        "/mapping/sets",
        json={
            "name": "customer-lead-sync",
            "integration_name": "Customer Lead Sync",
            "source_system": "CRM",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {"source": "lead_ref", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )

    response = client.get("/knowledge/canonical-concepts", headers=admin_headers())

    assert response.status_code == 200
    payload = response.json()
    customer_id = next(item for item in payload if item["concept_id"] == "customer.id")
    assert customer_id["source_systems"] == ["CRM", "SAP"]
    assert customer_id["business_domains"] == ["Customer"]


def test_canonical_concept_registry_filters_numeric_only_base_aliases_from_dirty_db() -> None:
    settings.admin_api_token = "secret-token"

    with persistence_service.connection() as connection:
        row = connection.execute(
            "SELECT aliases_json FROM canonical_concepts WHERE concept_id = ?",
            ("purchase_order.id",),
        ).fetchone()
        assert row is not None
        aliases = set(json.loads(row[0]))
        aliases.update({"130", "140", "196"})
        connection.execute(
            "UPDATE canonical_concepts SET aliases_json = ? WHERE concept_id = ?",
            (json.dumps(sorted(aliases)), "purchase_order.id"),
        )

    response = client.get("/knowledge/canonical-concepts", headers=admin_headers())

    assert response.status_code == 200
    payload = response.json()
    purchase_order_id = next(item for item in payload if item["concept_id"] == "purchase_order.id")
    assert "130" not in purchase_order_id["base_aliases"]
    assert "140" not in purchase_order_id["base_aliases"]
    assert "196" not in purchase_order_id["base_aliases"]
    assert "ebeln" in purchase_order_id["base_aliases"]


def test_catalog_search_endpoint_returns_metadata_and_concept_matches() -> None:
    settings.admin_api_token = "secret-token"

    client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "integration_name": "Customer Master Sync",
            "source_system": "SAP",
            "target_system": "Salesforce",
            "business_domain": "Customer",
            "owner": "governance-team",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )
    client.post(
        "/mapping/sets",
        json={
            "name": "vendor-master",
            "integration_name": "Vendor Master Sync",
            "source_system": "SAP",
            "target_system": "Coupa",
            "business_domain": "Vendor",
            "owner": "finance-team",
            "canonical_concepts": ["vendor.id"],
            "mapping_decisions": [
                {"source": "vendor_id", "target": "vendor.id", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )

    search_response = client.get(
        "/catalog/search",
        params={"q": "customer.id", "business_domain": "Customer", "owner": "governance-team"},
        headers=admin_headers(),
    )

    assert search_response.status_code == 200
    payload = search_response.json()
    assert [item["integration_name"] for item in payload] == ["Customer Master Sync"]


def test_mapping_set_diff_endpoint_returns_version_changes() -> None:
    settings.admin_api_token = "secret-token"

    baseline_response = client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer_id", "status": "accepted"},
                {"source": "phone", "target": "phone_number", "status": "needs_review"},
            ],
        },
        headers=admin_headers(),
    )
    current_response = client.post(
        "/mapping/sets",
        json={
            "name": "customer-master",
            "mapping_decisions": [
                {"source": "cust_id", "target": "customer_number", "status": "accepted"},
                {"source": "city", "target": "city_name", "status": "accepted"},
            ],
        },
        headers=admin_headers(),
    )

    baseline_id = baseline_response.json()["mapping_set_id"]
    current_id = current_response.json()["mapping_set_id"]

    diff_response = client.get(
        f"/mapping/sets/{current_id}/diff",
        params={"against_id": baseline_id},
        headers=admin_headers(),
    )

    assert diff_response.status_code == 200
    payload = diff_response.json()
    assert payload["current_version"] == 2
    assert payload["against_version"] == 1
    assert payload["added_count"] == 1
    assert payload["removed_count"] == 1
    assert payload["changed_count"] == 1
    assert [item["change_type"] for item in payload["changes"]] == ["added", "changed", "removed"]


def test_transformation_templates_endpoint_returns_reusable_templates() -> None:
    response = client.get("/mapping/transformation/templates")

    assert response.status_code == 200
    payload = response.json()
    template_ids = {item["template_id"] for item in payload}
    assert "trim_whitespace" in template_ids
    assert "email_local_part_title" in template_ids


def test_transformation_test_set_endpoints_persist_and_run_cases() -> None:
    create_response = client.post(
        "/mapping/transformation/test-sets",
        json={
            "name": "customer-name-transform",
            "mapping_decisions": [
                {
                    "source": "email",
                    "target": "customer_name",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_name"] = df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
                }
            ],
            "cases": [
                {
                    "case_name": "safe email name extraction",
                    "source_rows": [
                        {"email": "ana.markovic@example.com"},
                        {"email": "marko.petrovic@example.com"},
                    ],
                    "assertions": [
                        {
                            "target": "customer_name",
                            "expected_status": "validated",
                            "expected_classification": "safe",
                            "expected_warning_codes": [],
                            "expected_output_values": ["Ana Markovic", "Marko Petrovic"],
                        }
                    ],
                }
            ],
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200
    created = create_response.json()

    list_response = client.get("/mapping/transformation/test-sets", headers=admin_headers())
    detail_response = client.get(f"/mapping/transformation/test-sets/{created['test_set_id']}", headers=admin_headers())
    run_response = client.post(f"/mapping/transformation/test-sets/{created['test_set_id']}/run", headers=admin_headers())

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert run_response.status_code == 200

    listed = list_response.json()
    detail = detail_response.json()
    run_payload = run_response.json()
    assert listed[0]["name"] == "customer-name-transform"
    assert detail["mapping_decisions"][0]["target"] == "customer_name"
    assert detail["cases"][0]["case_name"] == "safe email name extraction"
    assert run_payload["passed"] is True
    assert run_payload["passed_cases"] == 1
    assert run_payload["case_results"][0]["preview"][0]["values"]["customer_name"] == "Ana Markovic"


def test_transformation_test_set_run_reports_assertion_failures() -> None:
    create_response = client.post(
        "/mapping/transformation/test-sets",
        json={
            "name": "customer-name-transform",
            "mapping_decisions": [
                {
                    "source": "email",
                    "target": "customer_name",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_name"] = df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
                }
            ],
            "cases": [
                {
                    "case_name": "expected mismatch",
                    "source_rows": [{"email": "ana.markovic@example.com"}],
                    "assertions": [
                        {
                            "target": "customer_name",
                            "expected_status": "validated",
                            "expected_classification": "safe",
                            "expected_warning_codes": [],
                            "expected_output_values": ["Wrong Name"],
                        }
                    ],
                }
            ],
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200
    run_response = client.post(
        f"/mapping/transformation/test-sets/{create_response.json()['test_set_id']}/run",
        headers=admin_headers(),
    )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert payload["passed"] is False
    assert payload["passed_cases"] == 0
    assert "Expected output values ['Wrong Name']" in payload["case_results"][0]["failures"][0]


def test_transformation_test_set_run_blocks_non_accepted_mapping_decisions() -> None:
    create_response = client.post(
        "/mapping/transformation/test-sets",
        json={
            "name": "customer-name-transform-review",
            "mapping_decisions": [
                {
                    "source": "email",
                    "target": "customer_name",
                    "status": "needs_review",
                    "transformation_code": 'df_target["customer_name"] = df_source["email"].str.title()',
                }
            ],
            "cases": [
                {
                    "case_name": "blocked until review is closed",
                    "source_rows": [{"email": "ana.markovic@example.com"}],
                    "assertions": [
                        {
                            "target": "customer_name",
                            "expected_status": "validated",
                            "expected_classification": "safe",
                            "expected_warning_codes": [],
                            "expected_output_values": ["Ana.Markovic@Example.Com"],
                        }
                    ],
                }
            ],
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 409
    assert create_response.json()["detail"] == (
        "Transformation test set save is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )


def test_transformation_test_set_run_blocks_persisted_non_accepted_mapping_decisions() -> None:
    persisted = persistence_service.save_transformation_test_set(
        "customer-name-transform-review",
        [
            {
                "source": "email",
                "target": "customer_name",
                "status": "needs_review",
                "transformation_code": 'df_target["customer_name"] = df_source["email"].str.title()',
            }
        ],
        [
            {
                "case_name": "blocked until review is closed",
                "source_rows": [{"email": "ana.markovic@example.com"}],
                "assertions": [
                    {
                        "target": "customer_name",
                        "expected_status": "validated",
                        "expected_classification": "safe",
                        "expected_warning_codes": [],
                        "expected_output_values": ["Ana.Markovic@Example.Com"],
                    }
                ],
            }
        ],
    )

    run_response = client.post(
        f"/mapping/transformation/test-sets/{persisted.test_set_id}/run",
        headers=admin_headers(),
    )

    assert run_response.status_code == 409
    assert run_response.json()["detail"] == (
        "Transformation test set run is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )


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
            "status": "overridden",
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
    assert payload[0]["status"] == "overridden"
    assert payload[0]["version"] == 1
    assert payload[0]["correction_id"] is not None


def test_reusable_correction_rule_candidates_endpoint_groups_repeated_history() -> None:
    settings.admin_api_token = "secret-token"

    for _ in range(3):
        correction_store.append(
            {
                "source": "cust_ref",
                "suggested_target": "customer_id",
                "corrected_target": "account_id",
                "status": "accepted",
                "note": "Prefer account id",
            }
        )

    response = client.get("/observability/corrections/reusable-rules", headers=admin_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["source"] == "cust_ref"
    assert payload[0]["status"] == "accepted"
    assert payload[0]["occurrence_count"] == 3
    assert "Prefer target 'account_id'" in payload[0]["recommendation"]


def test_reusable_correction_rule_promotion_endpoint_persists_rule_and_marks_candidate() -> None:
    settings.admin_api_token = "secret-token"

    for _ in range(3):
        correction_store.append(
            {
                "source": "cust_ref",
                "suggested_target": "customer_id",
                "corrected_target": "account_id",
                "status": "accepted",
                "note": "Prefer account id",
            }
        )

    promote_response = client.post(
        "/observability/corrections/reusable-rules/promote",
        json={
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "account_id",
            "status": "accepted",
            "occurrence_count": 3,
            "created_by": "demo-user",
            "note": "Promoted from repeated overrides",
        },
        headers=admin_headers(),
    )

    assert promote_response.status_code == 200
    promoted = promote_response.json()
    assert promoted["rule_id"] is not None
    assert promoted["created_by"] == "demo-user"

    list_response = client.get(
        "/observability/corrections/reusable-rules/active",
        headers=admin_headers(),
    )
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed[0]["source"] == "cust_ref"
    assert listed[0]["occurrence_count"] == 3

    candidates_response = client.get(
        "/observability/corrections/reusable-rules",
        headers=admin_headers(),
    )
    assert candidates_response.status_code == 200
    assert candidates_response.json()[0]["already_promoted"] is True
    assert candidates_response.json()[0]["promoted_rule_id"] == promoted["rule_id"]


def test_reusable_correction_rule_candidates_ignore_repeated_unclosed_override_history() -> None:
    settings.admin_api_token = "secret-token"

    for _ in range(3):
        correction_store.append(
            {
                "source": "cust_ref",
                "suggested_target": "customer_id",
                "corrected_target": "account_id",
                "status": "overridden",
                "note": "Legacy unresolved override",
            }
        )

    response = client.get("/observability/corrections/reusable-rules", headers=admin_headers())

    assert response.status_code == 200
    assert response.json() == []


def test_reusable_correction_rule_promotion_rejects_unclosed_override_history() -> None:
    settings.admin_api_token = "secret-token"

    for _ in range(3):
        correction_store.append(
            {
                "source": "cust_ref",
                "suggested_target": "customer_id",
                "corrected_target": "account_id",
                "status": "overridden",
                "note": "Legacy unresolved override",
            }
        )

    promote_response = client.post(
        "/observability/corrections/reusable-rules/promote",
        json={
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": "account_id",
            "status": "overridden",
            "occurrence_count": 3,
            "created_by": "demo-user",
            "note": "Should be blocked",
        },
        headers=admin_headers(),
    )

    assert promote_response.status_code == 400
    assert promote_response.json()["detail"] == "Reusable correction rules require closed review outcomes (accepted or rejected)."


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


def test_saved_benchmark_correction_impact_reports_improvement_from_history() -> None:
    settings.admin_api_token = "secret-token"

    for _ in range(4):
        correction_store.append(
            {
                "source": "cust_ref",
                "suggested_target": "customer_id",
                "corrected_target": "account_id",
                "status": "accepted",
                "note": "Historical correction prefers account id",
            }
        )

    create_response = client.post(
        "/evaluation/datasets",
        json={
            "name": "correction-impact-benchmark",
            "cases": [
                {
                    "source_columns": [
                        {
                            "name": "cust_ref",
                            "sample_values": ["1", "2"],
                            "distinct_sample_values": ["1", "2"],
                            "detected_patterns": ["numeric_id"],
                            "unique_ratio": 1.0,
                            "tokenized_name": ["cust", "ref"],
                        }
                    ],
                    "target_columns": [
                        {
                            "name": "customer_id",
                            "sample_values": ["1", "2"],
                            "distinct_sample_values": ["1", "2"],
                            "detected_patterns": ["numeric_id"],
                            "unique_ratio": 1.0,
                            "tokenized_name": ["customer", "id"],
                        },
                        {
                            "name": "account_id",
                            "sample_values": ["1", "2"],
                            "distinct_sample_values": ["1", "2"],
                            "detected_patterns": ["numeric_id"],
                            "unique_ratio": 1.0,
                            "tokenized_name": ["account", "id"],
                        },
                    ],
                    "ground_truth": {"cust_ref": "account_id"},
                }
            ],
        },
        headers=admin_headers(),
    )

    assert create_response.status_code == 200
    dataset_id = create_response.json()["dataset_id"]

    impact_response = client.post(
        f"/evaluation/datasets/{dataset_id}/correction-impact",
        headers=admin_headers(),
    )

    assert impact_response.status_code == 200
    payload = impact_response.json()
    assert payload["baseline"]["accuracy"] == 0.0
    assert payload["correction_aware"]["accuracy"] == 1.0
    assert payload["accuracy_delta"] == 1.0
    assert payload["correct_matches_delta"] == 1


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