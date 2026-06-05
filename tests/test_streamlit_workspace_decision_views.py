"""Tests Streamlit workspace decision and governance helper behavior."""

from unittest.mock import patch

from streamlit_ui.mapping_helpers import trust_layer_rows
from streamlit_ui.workspace_decision_views import _apply_llm_decision_proposal, _saved_mapping_set_apply_block_reason, _section_label
from streamlit_ui import workspace_decision_views


def test_section_label_appends_detail_only_when_present() -> None:
    assert _section_label("Active Decisions", "12 active") == "Active Decisions · 12 active"
    assert _section_label("Export / Import Decisions", None) == "Export / Import Decisions"


def test_draft_session_restore_section_allows_review_when_runtime_exists() -> None:
    assert (
        workspace_decision_views._draft_session_restore_section(
            "Review",
            {"mapping_runtime": {"code_fingerprint": "build-1"}},
        )
        == "Review"
    )
    assert workspace_decision_views._draft_session_restore_section("Output") == "Output"
    assert workspace_decision_views._draft_session_restore_section("Decisions") == "Decisions"
    assert workspace_decision_views._draft_session_restore_section("Review") == "Decisions"


def test_resolve_selected_draft_session_id_uses_requested_selection_key() -> None:
    session_state = {"selected_draft_session_id": 65}
    saved_draft_sessions = [
        {"draft_session_id": 72, "name": "customer-draft-session-0531"},
        {"draft_session_id": 65, "name": "customer-draft-session"},
    ]

    with patch.object(workspace_decision_views.st, "session_state", session_state):
        selected_id = workspace_decision_views._resolve_selected_draft_session_id(
            saved_draft_sessions,
            selection_key="setup_selected_draft_session_id",
        )

    assert selected_id == 72
    assert session_state["selected_draft_session_id"] == 65
    assert session_state["setup_selected_draft_session_id"] == 72


def test_set_active_draft_session_keeps_widget_selection_key_untouched() -> None:
    session_state = {"selected_draft_session_id": 3}

    with patch.object(workspace_decision_views.st, "session_state", session_state):
        workspace_decision_views._set_active_draft_session(
            {
                "draft_session_id": 7,
                "name": "customer-wip",
                "version": 2,
                "active_workspace_section": "Output",
            }
        )

    assert session_state["selected_draft_session_id"] == 3
    assert session_state["active_draft_session"]["draft_session_id"] == 7
    assert session_state["active_draft_session"]["active_workspace_section"] == "Output"


def test_saved_mapping_set_apply_block_reason_requires_approved_status() -> None:
    assert _saved_mapping_set_apply_block_reason({"status": "approved"}) == ""
    assert _saved_mapping_set_apply_block_reason({"status": "review"}) == (
        "Only approved mapping sets can be applied back into Workspace. Current status: review."
    )


def test_mapping_set_status_guidance_routes_approval_to_governance() -> None:
    assert "Governance > Stewardship" in workspace_decision_views._mapping_set_status_guidance("review")
    assert "direct shortcut" in workspace_decision_views._mapping_set_status_guidance("approved")


def test_open_mapping_set_governance_handoff_sets_pending_governance_state() -> None:
    session_state: dict = {}

    with (
        patch.object(workspace_decision_views.st, "session_state", session_state),
        patch.object(workspace_decision_views.st, "rerun", side_effect=RuntimeError("rerun")),
    ):
        try:
            workspace_decision_views._open_mapping_set_governance_handoff(
                {"name": "customer_master", "version": 2, "status": "review"}
            )
        except RuntimeError as error:
            assert str(error) == "rerun"
        else:
            raise AssertionError("Expected governance handoff helper to request a rerun.")

    assert session_state["pending_top_level_area"] == "Governance"
    assert session_state["pending_governance_section"] == "Stewardship"
    assert session_state["last_action"]["level"] == "info"
    assert "customer_master" in session_state["last_action"]["message"]


def test_apply_llm_decision_proposal_switches_target_and_accepts() -> None:
    editor_state = {"op_type": {"target": "operation_label", "status": "needs_review"}}

    applied = _apply_llm_decision_proposal(
        editor_state,
        {
            "source": "op_type",
            "current_target": "operation_label",
            "current_status": "needs_review",
            "proposal_type": "switch_target",
            "proposed_target": "operation_type_code",
            "confidence": 0.8,
            "origin": "mapping_validation",
        },
    )

    assert applied is True
    assert editor_state["op_type"]["target"] == "operation_type_code"
    assert editor_state["op_type"]["status"] == "accepted"
    assert editor_state["op_type"]["llm_proposal_confidence"] == 0.8
    assert editor_state["op_type"]["llm_proposal_origin"] == "mapping_validation"
    assert editor_state["op_type"]["llm_proposal_target"] == "operation_type_code"
    assert editor_state["op_type"]["llm_proposal_status"] == "accepted"


def test_apply_llm_decision_proposal_rejects_stale_state() -> None:
    editor_state = {"op_type": {"target": "manual_override", "status": "needs_review"}}

    applied = _apply_llm_decision_proposal(
        editor_state,
        {
            "source": "op_type",
            "current_target": "operation_label",
            "current_status": "needs_review",
            "proposal_type": "accept_current",
            "proposed_target": "operation_label",
        },
    )

    assert applied is False


def test_build_draft_session_request_payload_uses_current_workspace_state() -> None:
    session_state = {
        "active_workspace_section": "Review",
        "upload_response": {
            "mapping_mode": "standard",
            "source": {
                "dataset_id": "src-1",
                "dataset_name": "source.csv",
                "schema_profile": {"dataset_id": "src-1", "dataset_name": "source.csv", "row_count": 1, "columns": []},
                "preview_rows": [],
            },
            "target": {
                "dataset_id": "tgt-1",
                "dataset_name": "target.csv",
                "schema_profile": {"dataset_id": "tgt-1", "dataset_name": "target.csv", "row_count": 1, "columns": []},
                "preview_rows": [],
            },
        },
        "mapping_response": {
            "mapping_runtime": {
                "generated_at": "2026-05-27T10:00:00+00:00",
                "app_version": "dev",
                "scoring_profile": "balanced",
                "description_priority": False,
                "code_fingerprint": "draft-build-1",
            }
        },
        "mapping_editor_state": {
            "cust_id": {
                "target": "customer_id",
                "status": "accepted",
                "suggested_target": "customer_id",
                "suggested_transformation_code": "",
                "manual_transformation_code": "",
                "llm_transformation_instruction": "",
                "manual_apply_transformation": False,
                "manual": False,
            }
        },
        "mapping_decision_audit": {
            "cust_id": {
                "origin": "manual_mapping",
                "applied_at": "2026-05-27T10:00:00+00:00",
                "details": {"reason": "validated"},
            }
        },
        "workspace_transformation_spec": {
            "target_grain": "One row per customer",
            "global_rules": "Normalize country codes.",
            "defaults": "Keep unmatched optional fields as null.",
            "examples": "N/A -> null",
            "target_fields": ["customer_id"],
            "field_rules": [{"target_field": "customer_id", "rule": "Cast source code to string."}],
        },
        "preview_response": {
            "preview": [{"values": {"customer_id": "1"}, "warnings": []}],
            "unresolved_targets": [],
            "transformation_previews": [],
        },
        "codegen_response": {"code": "print('artifact')", "language": "python", "warnings": []},
        "mapping_analysis_summary": {"title": "Customer mapping overview"},
        "mapping_analysis_spoken_script": "Customer narration script.",
    }

    with patch.object(workspace_decision_views.st, "session_state", session_state):
        payload = workspace_decision_views._build_draft_session_request_payload("customer-wip")

    assert payload["name"] == "customer-wip"
    assert payload["api_base_url"] == ""
    assert payload["mapping_mode"] == "standard"
    assert payload["active_workspace_section"] == "Review"
    assert payload["mapping_runtime"]["code_fingerprint"] == "draft-build-1"
    assert payload["source_handle"]["dataset_name"] == "source.csv"
    assert payload["target_handle"]["dataset_name"] == "target.csv"
    assert payload["mapping_editor_state"]["cust_id"]["status"] == "accepted"
    assert payload["mapping_decision_audit"]["cust_id"]["origin"] == "manual_mapping"
    assert payload["transformation_spec"]["target_grain"] == "One row per customer"
    assert payload["output_state"]["preview_response"]["preview"][0]["values"]["customer_id"] == "1"
    assert payload["output_state"]["codegen_response"]["language"] == "python"
    assert payload["output_state"]["mapping_analysis_summary"]["title"] == "Customer mapping overview"
    assert payload["output_state"]["mapping_analysis_spoken_script"] == "Customer narration script."


def test_apply_draft_session_detail_to_workspace_restores_review_state_and_clears_outputs() -> None:
    session_state = {
        "api_base_url": "http://127.0.0.1:8000",
        "preview_response": {"status": "stale"},
        "codegen_response": {"code": "old"},
        "review_plan_summary": {"summary": "stale"},
        "mapping_analysis_summary": {"summary": "stale"},
    }
    detail = {
        "name": "customer-wip",
        "api_base_url": "http://127.0.0.1:8000",
        "mapping_mode": "standard",
        "active_workspace_section": "Review",
        "mapping_runtime": {
            "generated_at": "2026-05-27T10:00:00+00:00",
            "app_version": "dev",
            "scoring_profile": "balanced",
            "description_priority": False,
            "code_fingerprint": "draft-build-1",
        },
        "source_handle": {
            "dataset_id": "src-1",
            "dataset_name": "source.csv",
            "schema_profile": {
                "dataset_id": "src-1",
                "dataset_name": "source.csv",
                "row_count": 2,
                "columns": [
                    {"name": "cust_id"},
                    {"name": "phone"},
                ],
            },
            "preview_rows": [],
        },
        "target_handle": {
            "dataset_id": "tgt-1",
            "dataset_name": "target.csv",
            "schema_profile": {
                "dataset_id": "tgt-1",
                "dataset_name": "target.csv",
                "row_count": 2,
                "columns": [
                    {"name": "customer_id"},
                    {"name": "phone_number"},
                ],
            },
            "preview_rows": [],
        },
        "mapping_editor_state": {
            "cust_id": {
                "target": "customer_id",
                "status": "accepted",
                "suggested_target": "customer_id",
                "manual_transformation_code": "",
            },
            "phone": {
                "target": "phone_number",
                "status": "needs_review",
                "suggested_target": "phone_number",
                "manual_transformation_code": "value.strip()",
            },
        },
        "mapping_decision_audit": {
            "cust_id": {"origin": "manual_mapping", "applied_at": "", "details": {}},
        },
        "transformation_spec": {
            "target_grain": "One row per customer",
            "global_rules": "Normalize country codes.",
            "defaults": "Keep unmatched optional fields as null.",
            "examples": "N/A -> null",
            "target_fields": ["customer_id", "phone_number"],
            "field_rules": [{"target_field": "customer_id", "rule": "Cast source code to string."}],
        },
    }

    with patch.object(workspace_decision_views.st, "session_state", session_state):
        restored_section = workspace_decision_views._apply_draft_session_detail_to_workspace(detail)
        trust_rows = trust_layer_rows(session_state["mapping_response"], session_state)

    assert session_state["upload_response"]["source"]["dataset_name"] == "source.csv"
    assert session_state["upload_response"]["target"]["dataset_name"] == "target.csv"
    assert session_state["mapping_mode"] == "Standard"
    assert restored_section == "Review"
    assert session_state["pending_top_level_area"] == "Workspace"
    assert session_state["pending_workspace_section"] == "Review"
    assert session_state["mapping_editor_state"]["phone"]["manual_transformation_code"] == "value.strip()"
    assert session_state["mapping_decision_audit"]["cust_id"]["origin"] == "manual_mapping"
    assert session_state["workspace_transformation_target_grain"] == "One row per customer"
    assert session_state["workspace_transformation_rule::customer_id"] == "Cast source code to string."
    assert session_state["workspace_transformation_spec_status"] == "ready"
    assert session_state["workspace_transformation_spec_summary"]["title"] == "Ready for next output step"
    assert session_state["mapping_response"]["ranked_mappings"][0]["source"] == "cust_id"
    assert session_state["mapping_response"]["mapping_runtime"]["code_fingerprint"] == "draft-build-1"
    assert trust_rows[0]["source"] == "cust_id"
    assert trust_rows[0]["target"] == "customer_id"
    assert "preview_response" not in session_state
    assert "codegen_response" not in session_state
    assert "review_plan_summary" not in session_state
    assert "mapping_analysis_summary" not in session_state


def test_apply_draft_session_detail_to_workspace_restores_bounded_output_state() -> None:
    session_state = {
        "api_base_url": "http://127.0.0.1:8000",
    }
    detail = {
        "name": "customer-output-wip",
        "api_base_url": "http://127.0.0.1:8000",
        "mapping_mode": "standard",
        "active_workspace_section": "Output",
        "mapping_runtime": {
            "generated_at": "2026-05-27T10:00:00+00:00",
            "app_version": "dev",
            "scoring_profile": "balanced",
            "description_priority": False,
            "code_fingerprint": "draft-build-output",
        },
        "source_handle": {
            "dataset_id": "src-1",
            "dataset_name": "source.csv",
            "schema_profile": {"dataset_id": "src-1", "dataset_name": "source.csv", "row_count": 1, "columns": [{"name": "cust_id"}]},
            "preview_rows": [{"cust_id": 1}],
        },
        "target_handle": {
            "dataset_id": "tgt-1",
            "dataset_name": "target.csv",
            "schema_profile": {"dataset_id": "tgt-1", "dataset_name": "target.csv", "row_count": 1, "columns": [{"name": "customer_id"}]},
            "preview_rows": [],
        },
        "mapping_editor_state": {
            "cust_id": {
                "target": "customer_id",
                "status": "accepted",
                "suggested_target": "customer_id",
                "manual_transformation_code": "",
            }
        },
        "mapping_decision_audit": {},
        "transformation_spec": {},
        "output_state": {
            "preview_response": {
                "preview": [{"values": {"customer_id": "1"}, "warnings": []}],
                "unresolved_targets": [],
                "transformation_previews": [],
            },
            "codegen_response": {"code": "df_target['customer_id'] = df_source['cust_id']", "language": "python", "warnings": []},
            "codegen_refinement_response": {"code": "df_target['customer_id'] = df_source['cust_id'].astype(str)", "language": "python", "warnings": []},
            "mapping_analysis_summary": {"title": "Customer mapping overview"},
            "mapping_analysis_spoken_script": "Customer narration script.",
        },
    }

    with patch.object(workspace_decision_views.st, "session_state", session_state):
        restored_section = workspace_decision_views._apply_draft_session_detail_to_workspace(detail)

    assert restored_section == "Output"
    assert session_state["pending_workspace_section"] == "Output"
    assert session_state["preview_response"]["preview"][0]["values"]["customer_id"] == "1"
    assert session_state["codegen_response"]["language"] == "python"
    assert "astype(str)" in session_state["codegen_refinement_response"]["code"]
    assert session_state["mapping_analysis_summary"]["title"] == "Customer mapping overview"
    assert session_state["mapping_analysis_spoken_script"] == "Customer narration script."


def test_draft_session_restore_conflict_reason_blocks_api_base_url_mismatch() -> None:
    session_state = {
        "api_base_url": "http://127.0.0.1:8001",
    }

    with patch.object(workspace_decision_views.st, "session_state", session_state):
        reason = workspace_decision_views._draft_session_restore_conflict_reason(
            {
                "name": "customer-wip",
                "api_base_url": "http://127.0.0.1:8000",
                "mapping_mode": "standard",
                "source_handle": {"schema_profile": {"columns": []}},
                "target_handle": {"schema_profile": {"columns": []}},
            }
        )

    assert "API base URL" in reason


def test_apply_draft_session_detail_to_workspace_blocks_source_schema_mismatch() -> None:
    session_state = {
        "api_base_url": "http://127.0.0.1:8000",
        "upload_response": {
            "mapping_mode": "standard",
            "source": {"schema_profile": {"columns": [{"name": "legacy_id"}]}},
            "target": {"schema_profile": {"columns": [{"name": "customer_id"}]}},
        },
    }
    detail = {
        "name": "customer-wip",
        "api_base_url": "http://127.0.0.1:8000",
        "mapping_mode": "standard",
        "source_handle": {
            "dataset_name": "source.csv",
            "schema_profile": {"columns": [{"name": "cust_id"}]},
        },
        "target_handle": {
            "dataset_name": "target.csv",
            "schema_profile": {"columns": [{"name": "customer_id"}]},
        },
        "mapping_editor_state": {},
        "mapping_decision_audit": {},
    }

    with patch.object(workspace_decision_views.st, "session_state", session_state):
        try:
            workspace_decision_views._apply_draft_session_detail_to_workspace(detail)
        except ValueError as error:
            message = str(error)
        else:
            raise AssertionError("Expected draft-session restore to reject a source schema mismatch.")

    assert "source schema" in message


def test_draft_session_resume_transformation_message_reports_restored_spec_status() -> None:
    message = workspace_decision_views._draft_session_resume_transformation_message(
        {
            "transformation_spec": {
                "target_grain": "One row per customer",
                "global_rules": "Normalize country codes.",
                "defaults": "Keep unmatched optional fields as null.",
                "target_fields": ["customer_id", "phone_number"],
                "field_rules": [{"target_field": "customer_id", "rule": "Cast source code to string."}],
            }
        }
    )

    assert "Transformation Design restored" in message
    assert "Ready for next output step" in message


def test_draft_session_resume_output_message_reports_restored_snapshots() -> None:
    message = workspace_decision_views._draft_session_resume_output_message(
        {
            "output_state": {
                "preview_response": {"preview": [{"values": {"customer_id": "1"}}]},
                "codegen_refinement_response": {"code": "refined"},
                "mapping_analysis_summary": {"title": "Customer mapping overview"},
                "mapping_analysis_spoken_script": "Narration.",
            }
        }
    )

    assert "Output snapshot restored" in message
    assert "preview snapshot" in message
    assert "refined artifact" in message
    assert "mapping analysis" in message
    assert "narration script" in message