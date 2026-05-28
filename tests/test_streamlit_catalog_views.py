"""Tests Streamlit catalog view helpers for reuse and discovery flows."""

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


def test_merge_mapping_set_fields_into_workspace_updates_only_selected_sources(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "upload_response": {
                "source": {
                    "schema_profile": {
                        "columns": [
                            {"name": "KUNNR"},
                            {"name": "NAME1"},
                            {"name": "LAND1"},
                        ]
                    }
                }
            },
            "mapping_editor_state": {
                "KUNNR": {
                    "target": "customer_id",
                    "status": "needs_review",
                    "suggested_target": "customer_id",
                    "suggested_transformation_code": "",
                    "manual_transformation_code": "",
                    "llm_transformation_instruction": "",
                    "generated_transformation_reasoning": [],
                    "generated_transformation_warnings": [],
                    "apply_transformation": False,
                    "manual_apply_transformation": False,
                    "manual": False,
                },
                "NAME1": {
                    "target": "customer_name",
                    "status": "needs_review",
                    "suggested_target": "customer_name",
                    "suggested_transformation_code": "",
                    "manual_transformation_code": "",
                    "llm_transformation_instruction": "",
                    "generated_transformation_reasoning": [],
                    "generated_transformation_warnings": [],
                    "apply_transformation": False,
                    "manual_apply_transformation": False,
                    "manual": False,
                },
            },
            "mapping_decision_audit": {
                "NAME1": {"origin": "manual", "applied_at": "", "details": {}}
            },
            "preview_response": {"preview": []},
            "codegen_response": {"code": "x"},
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    applied_count = catalog_views._merge_mapping_set_fields_into_workspace(
        {
            "mapping_set_id": 9,
            "name": "customer-master",
            "version": 3,
            "mapping_decisions": [
                {
                    "source": "KUNNR",
                    "target": "customer.id",
                    "status": "accepted",
                    "transformation_code": 'df_target["customer_id"] = df_source["KUNNR"]',
                },
                {
                    "source": "LAND1",
                    "target": "customer.country_code",
                    "status": "accepted",
                },
            ],
        },
        selected_sources=["KUNNR"],
    )

    assert applied_count == 1
    assert fake_streamlit.session_state["mapping_editor_state"]["KUNNR"]["target"] == "customer.id"
    assert fake_streamlit.session_state["mapping_editor_state"]["NAME1"]["target"] == "customer_name"
    assert fake_streamlit.session_state["manual_transform_KUNNR"] == 'df_target["customer_id"] = df_source["KUNNR"]'
    assert fake_streamlit.session_state["mapping_decision_audit"]["KUNNR"]["origin"] == "catalog_field_reuse"
    assert fake_streamlit.session_state[catalog_views.CATALOG_LAST_FIELD_IMPORT_STATE_KEY]["imported_sources"] == ["KUNNR"]
    assert "preview_response" not in fake_streamlit.session_state
    assert "codegen_response" not in fake_streamlit.session_state


def test_catalog_field_reuse_compare_rows_shows_current_vs_saved_state(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "mapping_editor_state": {
                "KUNNR": {
                    "target": "customer_id",
                    "status": "needs_review",
                    "manual_transformation_code": "existing_transform()",
                },
                "LAND1": {
                    "target": "",
                    "status": "rejected",
                    "manual_transformation_code": "",
                },
            }
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    rows = catalog_views._catalog_field_reuse_compare_rows(
        [
            {
                "source_field": "KUNNR",
                "target": "customer.id",
                "status": "accepted",
                "transformation_present": True,
            },
            {
                "source_field": "LAND1",
                "target": "customer.country_code",
                "status": "accepted",
                "transformation_present": False,
            },
        ]
    )

    assert rows[0]["source_field"] == "KUNNR"
    assert rows[0]["target_change"] == "override"
    assert rows[0]["transformation_change"] == "transform replace"
    assert rows[0]["reuse_label"] == "override + transform replace"
    assert rows[0]["conflict"] == "yes"
    assert rows[1]["source_field"] == "LAND1"
    assert rows[1]["target_change"] == "safe fill"
    assert rows[1]["reuse_label"] == "safe fill"
    assert rows[1]["conflict"] == "no"


def test_restore_last_field_import_reverts_selected_sources(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "mapping_editor_state": {
                "KUNNR": {
                    "target": "customer.id",
                    "status": "accepted",
                    "suggested_target": "customer_id",
                    "suggested_transformation_code": "",
                    "manual_transformation_code": 'df_target["customer_id"] = df_source["KUNNR"]',
                    "llm_transformation_instruction": "",
                    "generated_transformation_reasoning": [],
                    "generated_transformation_warnings": [],
                    "apply_transformation": False,
                    "manual_apply_transformation": True,
                    "manual": False,
                },
                "NAME1": {
                    "target": "customer_name",
                    "status": "needs_review",
                    "suggested_target": "customer_name",
                    "suggested_transformation_code": "",
                    "manual_transformation_code": "",
                    "llm_transformation_instruction": "",
                    "generated_transformation_reasoning": [],
                    "generated_transformation_warnings": [],
                    "apply_transformation": False,
                    "manual_apply_transformation": False,
                    "manual": False,
                },
            },
            "mapping_decision_audit": {
                "KUNNR": {"origin": "catalog_field_reuse", "applied_at": "", "details": {}},
                "NAME1": {"origin": "manual", "applied_at": "", "details": {}},
            },
            "manual_transform_KUNNR": 'df_target["customer_id"] = df_source["KUNNR"]',
            "manual_apply_KUNNR": True,
            "transform_KUNNR": False,
            "preview_response": {"preview": []},
            catalog_views.CATALOG_LAST_FIELD_IMPORT_STATE_KEY: {
                "mapping_set_id": 9,
                "mapping_set_name": "customer-master",
                "mapping_set_version": 3,
                "imported_sources": ["KUNNR"],
                "previous_editor_state": {
                    "KUNNR": {
                        "target": "customer_id",
                        "status": "needs_review",
                        "suggested_target": "customer_id",
                        "suggested_transformation_code": "",
                        "manual_transformation_code": "",
                        "llm_transformation_instruction": "",
                        "generated_transformation_reasoning": [],
                        "generated_transformation_warnings": [],
                        "apply_transformation": False,
                        "manual_apply_transformation": False,
                        "manual": False,
                    }
                },
                "previous_decision_audit": {"KUNNR": None},
                "previous_manual_transform": {"KUNNR": None},
                "previous_manual_apply": {"KUNNR": None},
                "previous_transform_apply": {"KUNNR": True},
            },
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    restored_count = catalog_views._restore_last_field_import()

    assert restored_count == 1
    assert fake_streamlit.session_state["mapping_editor_state"]["KUNNR"]["target"] == "customer_id"
    assert "KUNNR" not in fake_streamlit.session_state["mapping_decision_audit"]
    assert "manual_transform_KUNNR" not in fake_streamlit.session_state
    assert "manual_apply_KUNNR" not in fake_streamlit.session_state
    assert fake_streamlit.session_state["transform_KUNNR"] is True
    assert catalog_views.CATALOG_LAST_FIELD_IMPORT_STATE_KEY not in fake_streamlit.session_state
    assert "preview_response" not in fake_streamlit.session_state


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
            "mapping_response": {
                "ranked_mappings": [
                    {"source": "KUNNR", "status": "accepted"},
                    {"source": "NAME1", "status": "needs_review"},
                ],
                "canonical_coverage": {
                    "source": {"unmatched_columns": ["LAND1"]},
                    "project": {
                        "concept_count": 3,
                        "shared_concepts": ["customer.id", "customer.name"],
                    },
                },
            },
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
        "current_status_counts": {"accepted": 1, "needs_review": 1},
        "current_shared_concepts": ["customer.id", "customer.name"],
        "current_unmatched_sources": ["LAND1"],
        "current_concept_count": 3,
    }


def test_catalog_reuse_fit_payload_wraps_mapping_set_and_workspace_context(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "upload_response": {
                "mapping_mode": "standard",
                "source": {"dataset_name": "sap_customer.csv"},
                "target": {"dataset_name": "crm_customer.csv"},
            },
            "mapping_response": {
                "mappings": [{"source": "KUNNR", "status": "accepted"}],
                "canonical_coverage": {
                    "source": {"unmatched_columns": ["LEGACY_ID"]},
                    "project": {
                        "concept_count": 2,
                        "shared_concepts": ["customer.id"],
                        "concepts": ["customer.id", "customer.name"],
                    },
                },
            },
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
            "current_status_counts": {"accepted": 1},
            "current_shared_concepts": ["customer.id"],
            "current_unmatched_sources": ["LEGACY_ID"],
            "current_concept_count": 2,
        },
    }


def test_catalog_reuse_fit_label_formats_known_values() -> None:
    assert catalog_views._catalog_reuse_fit_label("strong_fit") == "strong fit"
    assert catalog_views._catalog_reuse_fit_label("partial_fit") == "partial fit"
    assert catalog_views._catalog_reuse_fit_label("unknown") == ""


def test_preferred_catalog_review_handoff_concept_prefers_shared_concept() -> None:
    assert catalog_views._preferred_catalog_review_handoff_concept(
        ["customer.id", "customer.name"],
        ["customer.id", "customer.email"],
    ) == "customer.id"


def test_preferred_catalog_review_handoff_concept_falls_back_to_first_available() -> None:
    assert catalog_views._preferred_catalog_review_handoff_concept([], ["customer.email"]) == "customer.email"
    assert catalog_views._preferred_catalog_review_handoff_concept(["customer.id"], []) == "customer.id"


def test_catalog_mapping_set_record_by_id_returns_matching_version_record() -> None:
    assert catalog_views._catalog_mapping_set_record_by_id(
        [
            {"mapping_set_id": 4, "name": "customer-master", "version": 1},
            {"mapping_set_id": 7, "name": "customer-master", "version": 2},
        ],
        7,
    ) == {"mapping_set_id": 7, "name": "customer-master", "version": 2}


def test_catalog_mapping_set_record_by_id_returns_none_for_missing_id() -> None:
    assert catalog_views._catalog_mapping_set_record_by_id([{"mapping_set_id": 4}], 0) is None
    assert catalog_views._catalog_mapping_set_record_by_id([{"mapping_set_id": 4}], 7) is None


def test_catalog_mapping_set_diff_focus_sources_returns_unique_ordered_sources() -> None:
    assert catalog_views._catalog_mapping_set_diff_focus_sources(
        [
            {"source": "KUNNR"},
            {"source": "LAND1"},
            {"source": "KUNNR"},
            {"source": ""},
        ]
    ) == ["KUNNR", "LAND1"]


def test_catalog_reuse_fit_section_detail_combines_fit_and_generation_mode() -> None:
    assert catalog_views._catalog_reuse_fit_section_detail(None) == ""
    assert catalog_views._catalog_reuse_fit_section_detail(
        {"fit_assessment": "strong_fit", "generation_metadata": {"used_llm": True}}
    ) == "strong fit | LLM"
    assert catalog_views._catalog_reuse_fit_section_detail(
        {"fit_assessment": "partial_fit", "generation_metadata": {"used_llm": False}}
    ) == "partial fit | Fallback"


def test_catalog_reuse_fit_action_and_empty_state_helpers_use_explanation_noun() -> None:
    assert catalog_views._catalog_reuse_fit_action_label(None) == "Generate reuse-fit explanation"
    assert catalog_views._catalog_reuse_fit_action_label({"summary": "x"}) == "Refresh reuse-fit explanation"
    assert catalog_views._catalog_reuse_fit_empty_message() == (
        "No workspace reuse-fit explanation has been generated yet for the selected version."
    )


def test_catalog_reuse_fit_intro_and_unlock_helpers_state_read_only_role() -> None:
    assert catalog_views._catalog_reuse_fit_intro_caption() == (
        "Generate one bounded reuse-fit explanation for the selected catalog version against the current workspace snapshot before applying reuse. "
        "This is a read-only guidance surface and does not apply or approve anything automatically."
    )
    assert catalog_views._catalog_reuse_fit_unlock_message() == (
        "Open the selected catalog version first to unlock reuse-fit review against the current workspace snapshot."
    )


def test_catalog_reuse_fit_success_and_error_helpers_use_shared_copy_pattern() -> None:
    assert catalog_views._catalog_reuse_fit_success_message() == (
        "Generated workspace reuse-fit explanation for the selected catalog mapping set."
    )
    assert catalog_views._catalog_reuse_fit_error_message("boom") == (
        "Workspace reuse-fit explanation generation failed: boom"
    )


def test_catalog_reuse_fit_metadata_caption_uses_llm_fallback_pattern() -> None:
    assert catalog_views._catalog_reuse_fit_metadata_caption(None) == ""
    assert catalog_views._catalog_reuse_fit_metadata_caption(
        {"generation_metadata": {"used_llm": True, "fallback_used": False}}
    ) == "LLM"
    assert catalog_views._catalog_reuse_fit_metadata_caption(
        {"generation_metadata": {"used_llm": False, "fallback_used": True}}
    ) == "Fallback with fallback contract"


def test_catalog_reuse_fit_output_heading_preserves_section_title() -> None:
    assert catalog_views._catalog_reuse_fit_output_heading("Key matches") == "Key matches"
    assert catalog_views._catalog_reuse_fit_output_heading(" Risks ") == "Risks"


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


def test_catalog_version_compare_payload_prefers_latest_approved_baseline() -> None:
    payload = catalog_views._catalog_version_compare_payload(
        {
            "mapping_set_id": 7,
            "name": "customer-master",
            "version": 4,
            "status": "review",
            "decision_count": 6,
            "canonical_concepts": ["customer.id", "customer.name", "customer.email"],
        },
        [
            {
                "mapping_set_id": 7,
                "name": "customer-master",
                "version": 4,
                "status": "review",
                "decision_count": 6,
                "canonical_concepts": ["customer.id", "customer.name", "customer.email"],
            },
            {
                "mapping_set_id": 5,
                "name": "customer-master",
                "version": 3,
                "status": "approved",
                "decision_count": 5,
                "canonical_concepts": ["customer.id", "customer.name"],
            },
            {
                "mapping_set_id": 4,
                "name": "customer-master",
                "version": 2,
                "status": "draft",
                "decision_count": 4,
                "canonical_concepts": ["customer.id"],
            },
        ],
        {"mapping_set_id": 5, "version": 3, "status": "approved"},
    )

    assert payload["recommended_target"]["mapping_set_id"] == 5
    assert "latest approved baseline" in payload["recommended_reason"]
    assert payload["rows"][0]["decision_delta"] == "+1"
    assert payload["rows"][0]["shared_concepts"] == "customer.id, customer.name"
    assert payload["rows"][0]["suggested_action"] == "Recommended diff baseline"


def test_catalog_similar_compare_payload_prefers_approved_same_system_peer() -> None:
    payload = catalog_views._catalog_similar_compare_payload(
        {
            "mapping_set_id": 7,
            "canonical_concepts": ["customer.id", "customer.name", "customer.email"],
        },
        [
            {
                "integration_name": "SAP Customer to CRM",
                "similarity_score": 0.91,
                "shared_concepts": ["customer.id", "customer.name"],
                "shared_concept_count": 2,
                "same_source_system": True,
                "same_target_system": True,
                "same_business_domain": True,
                "same_artifact_type": True,
                "latest_version": {"mapping_set_id": 11, "version": 5, "status": "review"},
                "latest_approved_version": {"mapping_set_id": 10, "version": 4, "status": "approved"},
            },
            {
                "integration_name": "Legacy Customer to CRM",
                "similarity_score": 0.88,
                "shared_concepts": ["customer.id"],
                "shared_concept_count": 1,
                "same_source_system": False,
                "same_target_system": True,
                "same_business_domain": True,
                "same_artifact_type": False,
                "latest_version": {"mapping_set_id": 12, "version": 3, "status": "approved"},
                "latest_approved_version": None,
            },
        ],
    )

    assert payload["recommended_integration_name"] == "SAP Customer to CRM"
    assert "approved peer version available" in payload["recommended_reason"]
    assert "same system pair" in payload["rows"][0]["compare_reason"]
    assert payload["rows"][0]["drilldown_version"] == 4
    assert payload["rows"][0]["suggested_action"] == "Open peer version"


def test_catalog_next_action_plan_prefers_governance_for_unapproved_version() -> None:
    plan = catalog_views._catalog_next_action_plan(
        {
            "mapping_set_id": 7,
            "name": "customer-master",
            "version": 4,
            "status": "review",
            "artifact_type": "standard",
            "unmatched_sources": [],
        },
        {"workspace_loaded": True, "mapping_mode": "standard"},
    )

    assert plan["table_label"] == "Canonical governance handoff"
    assert plan["primary_area"] == "Governance"
    assert plan["primary_label"] == "Open Canonical review"
    assert plan["secondary_area"] == "Workspace"
    assert "Inspect governance owner" in plan["primary_summary"]


def test_catalog_next_action_plan_adds_canonical_secondary_for_unmatched_sources() -> None:
    plan = catalog_views._catalog_next_action_plan(
        {
            "mapping_set_id": 7,
            "name": "customer-master",
            "version": 4,
            "status": "approved",
            "artifact_type": "canonical-only",
            "unmatched_sources": ["LAND1"],
        },
        {"workspace_loaded": True, "mapping_mode": "canonical"},
    )

    assert plan["table_label"] == "Workspace review handoff"
    assert plan["primary_area"] == "Workspace"
    assert plan["secondary_area"] == "Governance"
    assert plan["secondary_label"] == "Open Stewardship"
    assert "canonical gaps" in plan["primary_summary"]


def test_catalog_governance_handoff_summary_prefers_primary_governance_path() -> None:
    assert catalog_views._catalog_governance_handoff_summary(
        {
            "primary_area": "Governance",
            "primary_summary": "Inspect governance owner, review note, and canonical coverage.",
            "secondary_area": "Workspace",
            "secondary_summary": "Keep review visible.",
        }
    ) == "Inspect governance owner, review note, and canonical coverage."


def test_catalog_governance_handoff_summary_falls_back_to_secondary_governance_path() -> None:
    assert catalog_views._catalog_governance_handoff_summary(
        {
            "primary_area": "Workspace",
            "primary_summary": "Keep review visible.",
            "secondary_area": "Governance",
            "secondary_summary": "Inspect canonical usage before reuse.",
        }
    ) == "Inspect canonical usage before reuse."
    assert catalog_views._catalog_governance_handoff_summary({"primary_area": "Workspace"}) == ""


def test_catalog_governance_handoff_payload_prioritizes_stewardship_for_unmatched_sources() -> None:
    payload = catalog_views._catalog_governance_handoff_payload(
        {
            "artifact_type": "canonical-only",
            "canonical_concepts": ["customer.id", "customer.name"],
            "unmatched_sources": ["LAND1", "REGIO", "LAND1"],
            "source_system": "SAP",
            "business_domain": "Customer",
        }
    )

    assert payload == {
        "section": "Stewardship",
        "canonical_concept_id": "customer.id",
        "canonical_source_system": "SAP",
        "canonical_business_domain": "Customer",
        "focus_sources": ["LAND1", "REGIO"],
        "gap_source_filter": "",
    }


def test_catalog_governance_handoff_action_label_prefers_stewardship_destination() -> None:
    label = catalog_views._catalog_governance_handoff_action_label(
        {
            "unmatched_sources": ["LAND1", "REGIO"],
            "canonical_concepts": ["customer.id"],
        },
        scope_label="current diff",
    )

    assert label == "Open current diff Stewardship"


def test_catalog_governance_handoff_action_label_prefers_canonical_review_for_draft() -> None:
    label = catalog_views._catalog_governance_handoff_action_label(
        {
            "status": "draft",
            "canonical_concepts": ["customer.id"],
            "artifact_type": "canonical-only",
        },
        scope_label="baseline diff",
    )

    assert label == "Open baseline diff Canonical review"


def test_catalog_governance_handoff_action_label_supports_empty_scope_label() -> None:
    label = catalog_views._catalog_governance_handoff_action_label(
        {
            "status": "draft",
            "canonical_concepts": ["customer.id"],
        },
        scope_label="",
    )

    assert label == "Open Canonical review"


def test_catalog_governance_follow_up_caption_uses_reason_priority() -> None:
    unmatched_caption = catalog_views._catalog_governance_follow_up_caption(
        {
            "unmatched_sources": ["LAND1", "REGIO"],
            "canonical_concepts": ["customer.id"],
        },
        scope_label="Current diff",
    )
    draft_caption = catalog_views._catalog_governance_follow_up_caption(
        {
            "status": "draft",
            "canonical_concepts": ["customer.id"],
            "artifact_type": "canonical-only",
        },
        scope_label="Baseline diff",
    )

    assert unmatched_caption == "Current diff: Stewardship for 2 unmatched source fields."
    assert draft_caption == "Baseline diff: Canonical for draft version."


def test_open_catalog_handoff_switches_top_level_area(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._open_catalog_handoff(
        "Workspace",
        {"name": "customer-master", "version": 4},
        "Continue in Workspace Review.",
    )

    assert fake_streamlit.session_state["pending_top_level_area"] == "Workspace"
    assert fake_streamlit.session_state["last_action"]["level"] == "info"
    assert "Catalog handoff: customer-master v4 -> Workspace." in fake_streamlit.session_state["last_action"]["message"]


def test_open_catalog_handoff_governance_sets_pending_focus_state(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._open_catalog_handoff(
        "Governance",
        {
            "name": "customer-master",
            "version": 4,
            "canonical_concepts": ["customer.id"],
            "unmatched_sources": ["LAND1", "REGIO"],
            "source_system": "SAP",
            "business_domain": "Customer",
        },
        "Inspect canonical usage before reuse.",
    )

    assert fake_streamlit.session_state["pending_top_level_area"] == "Governance"
    assert fake_streamlit.session_state["pending_governance_section"] == "Stewardship"
    assert fake_streamlit.session_state["pending_governance_canonical_concept_id"] == "customer.id"
    assert fake_streamlit.session_state["pending_governance_canonical_source_system"] == "SAP"
    assert fake_streamlit.session_state["pending_governance_canonical_business_domain"] == "Customer"
    assert fake_streamlit.session_state["governance_focus_sources"] == ["LAND1", "REGIO"]
    assert "-> Governance (Stewardship)." in fake_streamlit.session_state["last_action"]["message"]


def test_open_catalog_handoff_governance_clears_stale_stewardship_filters(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "debug_canonical_gap_status_filter": "ready_for_approval",
            "debug_canonical_gap_owner_filter": "governance-team",
            "debug_canonical_gap_assignee_filter": "analyst-1",
            "debug_canonical_gap_source_filter": "OLD_FIELD",
            "debug_selected_canonical_gap_label": "stale gap",
            "governance_focus_sources": ["OLD_FIELD"],
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._open_catalog_handoff(
        "Governance",
        {
            "name": "customer-master",
            "version": 4,
            "canonical_concepts": ["customer.id"],
            "unmatched_sources": ["LAND1", "REGIO"],
        },
        "Inspect canonical usage before reuse.",
    )

    assert fake_streamlit.session_state["debug_canonical_gap_status_filter"] == ""
    assert fake_streamlit.session_state["debug_canonical_gap_owner_filter"] == ""
    assert fake_streamlit.session_state["debug_canonical_gap_assignee_filter"] == ""
    assert fake_streamlit.session_state["debug_canonical_gap_source_filter"] == ""
    assert "debug_selected_canonical_gap_label" not in fake_streamlit.session_state
    assert fake_streamlit.session_state["governance_focus_sources"] == ["LAND1", "REGIO"]


def test_open_catalog_handoff_governance_clears_stale_canonical_filters(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "debug_canonical_concept_query": "legacy",
            "debug_canonical_concept_focus": "overlay_only",
            "debug_canonical_concept_source_system": "LegacyERP",
            "debug_canonical_concept_business_domain": "Vendor",
            "debug_selected_canonical_concept_label": "stale concept",
            "governance_focus_sources": ["OLD_FIELD"],
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._open_catalog_handoff(
        "Governance",
        {
            "name": "customer-master",
            "version": 4,
            "canonical_concepts": ["customer.id"],
            "artifact_type": "canonical-only",
            "source_system": "SAP",
            "business_domain": "Customer",
            "unmatched_sources": [],
        },
        "Inspect canonical usage before reuse.",
    )

    assert fake_streamlit.session_state["pending_governance_section"] == "Canonical"
    assert fake_streamlit.session_state["debug_canonical_concept_query"] == ""
    assert fake_streamlit.session_state["debug_canonical_concept_focus"] == "all"
    assert fake_streamlit.session_state["debug_canonical_concept_source_system"] == ""
    assert fake_streamlit.session_state["debug_canonical_concept_business_domain"] == ""
    assert "debug_selected_canonical_concept_label" not in fake_streamlit.session_state
    assert "governance_focus_sources" not in fake_streamlit.session_state


def test_open_catalog_review_focus_handoff_sets_workspace_review_filters(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={"review_focus_sources": ["stale"]})
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._open_catalog_review_focus_handoff(
        mapping_set_detail={"name": "customer-master", "version": 4},
        canonical_concept="customer.id",
    )

    assert fake_streamlit.session_state["pending_top_level_area"] == "Workspace"
    assert fake_streamlit.session_state["pending_workspace_section"] == "Review"
    assert fake_streamlit.session_state["filter_status"] == "needs_review"
    assert fake_streamlit.session_state["filter_confidence"] == "All"
    assert fake_streamlit.session_state["filter_source"] == "All"
    assert fake_streamlit.session_state["filter_canonical_concept"] == "customer.id"
    assert "review_focus_sources" not in fake_streamlit.session_state
    assert "Workspace Review with filters" in fake_streamlit.session_state["last_action"]["message"]


def test_open_catalog_review_focus_handoff_preserves_multi_source_diff_focus(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    catalog_views._open_catalog_review_focus_handoff(
        mapping_set_detail={"name": "customer-master", "version": 4},
        canonical_concept="customer.id",
        source_fields=["KUNNR", "LAND1", "KUNNR"],
    )

    assert fake_streamlit.session_state["filter_source"] == "All"
    assert fake_streamlit.session_state["pending_workspace_section"] == "Review"
    assert fake_streamlit.session_state["review_focus_sources"] == ["KUNNR", "LAND1"]
    assert "source_scope=2 diff fields" in fake_streamlit.session_state["last_action"]["message"]


def test_catalog_detail_state_recovery_clears_stale_catalog_state(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "catalog_results": [{"integration_name": "Customer Master Sync"}],
            "selected_catalog_integration_name": "Lead Reuse Sync",
            "catalog_integration_detail": {"integration_name": "Customer Master Sync"},
            "catalog_selected_mapping_set_detail": {"mapping_set_id": 7},
        }
    )
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    request = httpx.Request("GET", "http://testserver/catalog/integrations/Lead%20Reuse%20Sync")
    response = httpx.Response(
        404,
        json={"detail": "'Unknown catalog integration: Lead Reuse Sync'"},
        request=request,
    )
    error = httpx.HTTPStatusError("HTTP 404: missing", request=request, response=response)

    payload = catalog_views._catalog_detail_state_recovery(error)

    assert payload == {
        "level": "warning",
        "message": "Catalog results look stale relative to the backend. Reload catalog query results before opening integration detail again.",
    }
    assert fake_streamlit.session_state == {}


def test_catalog_detail_state_recovery_ignores_other_errors(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={"catalog_results": [1]})
    monkeypatch.setattr(catalog_views, "st", fake_streamlit)

    request = httpx.Request("GET", "http://testserver/catalog/integrations/foo")
    response = httpx.Response(409, json={"detail": "blocked"}, request=request)
    error = httpx.HTTPStatusError("HTTP 409", request=request, response=response)

    assert catalog_views._catalog_detail_state_recovery(error) is None
    assert fake_streamlit.session_state["catalog_results"] == [1]


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