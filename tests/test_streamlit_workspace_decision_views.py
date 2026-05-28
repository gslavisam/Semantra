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
    assert workspace_decision_views._draft_session_restore_section("Decisions") == "Decisions"
    assert workspace_decision_views._draft_session_restore_section("Review") == "Decisions"


def test_saved_mapping_set_apply_block_reason_requires_approved_status() -> None:
    assert _saved_mapping_set_apply_block_reason({"status": "approved"}) == ""
    assert _saved_mapping_set_apply_block_reason({"status": "review"}) == (
        "Only approved mapping sets can be applied back into Workspace. Current status: review."
    )


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
        },
    )

    assert applied is True
    assert editor_state["op_type"]["target"] == "operation_type_code"
    assert editor_state["op_type"]["status"] == "accepted"


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
    assert session_state["mapping_response"]["ranked_mappings"][0]["source"] == "cust_id"
    assert session_state["mapping_response"]["mapping_runtime"]["code_fingerprint"] == "draft-build-1"
    assert trust_rows[0]["source"] == "cust_id"
    assert trust_rows[0]["target"] == "customer_id"
    assert "preview_response" not in session_state
    assert "codegen_response" not in session_state
    assert "review_plan_summary" not in session_state
    assert "mapping_analysis_summary" not in session_state


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