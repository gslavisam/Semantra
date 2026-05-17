from __future__ import annotations

from types import SimpleNamespace

import httpx

from streamlit_ui import catalog_views
from streamlit_ui import governance


def test_section_label_appends_detail_only_when_present() -> None:
    assert catalog_views._section_label("Integration Detail", "4 versions") == "Integration Detail · 4 versions"
    assert catalog_views._section_label("Concept Usage Summary", "") == "Concept Usage Summary"


def test_build_catalog_reuse_mapping_response_creates_workspace_shape() -> None:
    mapping_response = catalog_views._build_catalog_reuse_mapping_response(
        {
            "name": "customer-master",
            "version": 3,
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id", "customer.name"],
            "unmatched_sources": ["LAND1"],
            "mapping_decisions": [
                {"source": "KUNNR", "target": "customer.id", "status": "accepted"},
                {"source": "NAME1", "target": "customer.name", "status": "accepted"},
                {"source": "LAND1", "target": "", "status": "needs_review"},
            ],
        }
    )

    assert [item["source"] for item in mapping_response["ranked_mappings"]] == ["KUNNR", "NAME1", "LAND1"]
    assert mapping_response["mappings"][0]["canonical_details"]["shared_concepts"][0]["concept_id"] == "customer.id"
    assert mapping_response["canonical_coverage"]["source"]["unmatched_columns"] == ["LAND1"]


def test_apply_mapping_set_detail_to_workspace_sets_editor_state(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._apply_mapping_set_detail_to_workspace(
        {
            "name": "customer-master",
            "version": 2,
            "owner": "governance-team",
            "assignee": "analyst-1",
            "review_note": "Ready for reuse",
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id"],
            "mapping_decisions": [
                {
                    "source": "KUNNR",
                    "target": "customer.id",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_id"] = df_source["KUNNR"]',
                }
            ],
        }
    )

    assert fake_streamlit.session_state["mapping_response"]["ranked_mappings"][0]["source"] == "KUNNR"
    assert fake_streamlit.session_state["mapping_editor_state"]["KUNNR"]["target"] == "customer.id"
    assert fake_streamlit.session_state["manual_transform_KUNNR"] == 'df_target["customer_id"] = df_source["KUNNR"]'
    assert fake_streamlit.session_state["mapping_set_owner"] == "governance-team"


def test_mapping_set_reuse_block_reason_requires_approved_status() -> None:
    assert catalog_views._mapping_set_reuse_block_reason("approved") == ""
    assert (
        catalog_views._mapping_set_reuse_block_reason("review")
        == "Only approved mapping sets can be reused in Workspace. Current status: review."
    )


def test_catalog_reuse_fit_workspace_context_reads_current_workspace(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "upload_response": {
                "mapping_mode": "canonical",
                "source": {"dataset_name": "sap_customer.csv"},
                "target_system": "customer_canonical",
            },
            "mapping_response": {"ranked_mappings": [{"source": "KUNNR"}, {"source": "NAME1"}]},
            "analysis_source_system": "SAP",
            "analysis_target_system": "Canonical Customer",
            "analysis_business_domain": "Customer",
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    assert catalog_views._catalog_reuse_fit_workspace_context() == {
        "workspace_loaded": True,
        "mapping_mode": "canonical",
        "source_dataset_name": "sap_customer.csv",
        "target_dataset_name": "customer_canonical",
        "source_system": "SAP",
        "target_system": "Canonical Customer",
        "business_domain": "Customer",
        "current_decision_count": 2,
    }


def test_catalog_reuse_fit_payload_wraps_mapping_set_and_workspace_context(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "upload_response": {
                "mapping_mode": "standard",
                "source": {"dataset_name": "sap_customer.csv"},
                "target": {"dataset_name": "crm_customer.csv"},
            },
            "mapping_response": {"mappings": [{"source": "KUNNR"}]},
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    payload = catalog_views._catalog_reuse_fit_payload({"mapping_set_id": 7, "name": "customer-master"})

    assert payload == {
        "mapping_set_detail": {"mapping_set_id": 7, "name": "customer-master"},
        "workspace_context": {
            "workspace_loaded": True,
            "mapping_mode": "standard",
            "source_dataset_name": "sap_customer.csv",
            "target_dataset_name": "crm_customer.csv",
            "source_system": None,
            "target_system": None,
            "business_domain": None,
            "current_decision_count": 1,
        },
    }


def test_catalog_reuse_fit_label_formats_known_values() -> None:
    assert catalog_views._catalog_reuse_fit_label("strong_fit") == "strong fit"
    assert catalog_views._catalog_reuse_fit_label("partial_fit") == "partial fit"
    assert catalog_views._catalog_reuse_fit_label("unknown") == "not generated"


def test_catalog_reuse_fit_ready_for_selected_version_requires_matching_drilldown() -> None:
    assert catalog_views._catalog_reuse_fit_ready_for_selected_version(
        {"mapping_set_id": 7},
        {"mapping_set_id": 7},
    ) is True
    assert catalog_views._catalog_reuse_fit_ready_for_selected_version(
        {"mapping_set_id": 7},
        {"mapping_set_id": 8},
    ) is False
    assert catalog_views._catalog_reuse_fit_ready_for_selected_version(
        {"mapping_set_id": 7},
        None,
    ) is False


def test_catalog_concept_reuse_rows_group_integrations_and_approval_state() -> None:
    concept_detail = {
        "concept_id": "customer.id",
        "usage_count": 4,
        "integrations": [
            {
                "integration_name": "Customer SAP to CRM",
                "version": 3,
                "status": "approved",
                "artifact_type": "standard",
                "source_system": "SAP",
                "target_system": "CRM",
                "business_domain": "Customer",
                "owner": "team-a",
            },
            {
                "integration_name": "Customer SAP to CRM",
                "version": 2,
                "status": "review",
                "artifact_type": "standard",
                "source_system": "SAP",
                "target_system": "CRM",
                "business_domain": "Customer",
                "owner": "team-a",
            },
            {
                "integration_name": "Customer Hub to Billing",
                "version": 5,
                "status": "approved",
                "artifact_type": "canonical-only",
                "source_system": "Hub",
                "target_system": "Billing",
                "business_domain": "Customer",
                "owner": "team-b",
            },
            {
                "integration_name": "Customer Hub to Billing",
                "version": 4,
                "status": "approved",
                "artifact_type": "canonical-only",
                "source_system": "Hub",
                "target_system": "Billing",
                "business_domain": "Customer",
                "owner": "team-c",
            },
        ],
    }

    summary = catalog_views._catalog_concept_reuse_summary(concept_detail)
    rows = catalog_views._catalog_concept_reuse_rows(concept_detail)

    assert summary == {
        "usage_count": 4,
        "integration_count": 2,
        "approved_integration_count": 2,
        "source_system_count": 2,
        "target_system_count": 2,
    }
    assert rows == [
        {
            "integration_name": "Customer Hub to Billing",
            "source_system": "Hub",
            "target_system": "Billing",
            "business_domain": "Customer",
            "usage_versions": 2,
            "latest_version": 5,
            "latest_approved_version": 5,
            "approved_versions": 2,
            "artifact_types": "canonical-only",
            "owners": "team-b, team-c",
            "status_mix": "approved=2",
        },
        {
            "integration_name": "Customer SAP to CRM",
            "source_system": "SAP",
            "target_system": "CRM",
            "business_domain": "Customer",
            "usage_versions": 2,
            "latest_version": 3,
            "latest_approved_version": 3,
            "approved_versions": 1,
            "artifact_types": "standard",
            "owners": "team-a",
            "status_mix": "approved=1, review=1",
        },
    ]


def test_catalog_system_pair_matrix_rows_builds_discovery_overview() -> None:
    rows = catalog_views._catalog_system_pair_matrix_rows(
        [
            {
                "integration_name": "Customer SAP to CRM",
                "status": "approved",
                "source_system": "SAP",
                "target_system": "CRM",
                "canonical_concepts": ["customer.id", "customer.name"],
            },
            {
                "integration_name": "Customer SAP to CRM",
                "status": "review",
                "source_system": "SAP",
                "target_system": "CRM",
                "canonical_concepts": ["customer.id"],
            },
            {
                "integration_name": "Vendor SAP to ERP",
                "status": "approved",
                "source_system": "SAP",
                "target_system": "ERP",
                "canonical_concepts": ["vendor.id"],
            },
            {
                "integration_name": "CRM to Billing",
                "status": "draft",
                "source_system": "CRM",
                "target_system": "Billing",
                "canonical_concepts": ["customer.id"],
            },
        ]
    )

    assert rows == [
        {
            "source_system": "SAP",
            "integration_count": 2,
            "approved_integrations": 2,
            "system_pair_count": 2,
            "canonical_concept_hits": 4,
            "Billing": 0,
            "CRM": 1,
            "ERP": 1,
        },
        {
            "source_system": "CRM",
            "integration_count": 1,
            "approved_integrations": 0,
            "system_pair_count": 1,
            "canonical_concept_hits": 1,
            "Billing": 1,
            "CRM": 0,
            "ERP": 0,
        },
    ]


def test_catalog_result_reuse_hints_prefers_approved_peer_with_shared_concepts() -> None:
    hints = catalog_views._catalog_result_reuse_hints(
        [
            {
                "integration_name": "SAP Customer to CRM",
                "status": "approved",
                "source_system": "SAP",
                "target_system": "CRM",
                "canonical_concepts": ["customer.id", "customer.name", "customer.email"],
            },
            {
                "integration_name": "Legacy Customer to CRM",
                "status": "review",
                "source_system": "LegacyERP",
                "target_system": "CRM",
                "canonical_concepts": ["customer.id", "customer.name", "customer.phone"],
            },
            {
                "integration_name": "Vendor to ERP",
                "status": "approved",
                "source_system": "SAP",
                "target_system": "ERP",
                "canonical_concepts": ["vendor.id"],
            },
        ]
    )

    assert hints == {
        "SAP Customer to CRM": "",
        "Legacy Customer to CRM": (
            "Similar approved integration exists: SAP Customer to CRM "
            "(2 shared concepts; e.g. customer.id, customer.name)"
        ),
        "Vendor to ERP": "",
    }


def test_api_error_message_returns_backend_detail_for_governance_conflict() -> None:
    request = httpx.Request("POST", "http://testserver/mapping/sets/7/apply")
    response = httpx.Response(
        409,
        json={"detail": "Mapping set #7 is in status 'review' and cannot be applied."},
        request=request,
    )
    error = httpx.HTTPStatusError("HTTP 409: blocked", request=request, response=response)

    assert governance.api_error_message(error, default_prefix="Applying saved mapping set failed") == (
        "Mapping set #7 is in status 'review' and cannot be applied."
    )


def test_api_error_message_keeps_context_for_non_governance_errors() -> None:
    request = httpx.Request("POST", "http://testserver/mapping/sets/7/apply")
    response = httpx.Response(500, json={"detail": "Server exploded"}, request=request)
    error = httpx.HTTPStatusError("HTTP 500: Server exploded", request=request, response=response)

    assert governance.api_error_message(error, default_prefix="Applying saved mapping set failed") == (
        "Applying saved mapping set failed: HTTP 500: Server exploded"
    )