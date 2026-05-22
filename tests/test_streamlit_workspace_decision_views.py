"""Tests Streamlit workspace decision and governance helper behavior."""

from streamlit_ui.workspace_decision_views import _apply_llm_decision_proposal, _saved_mapping_set_apply_block_reason, _section_label


def test_section_label_appends_detail_only_when_present() -> None:
    assert _section_label("Active Decisions", "12 active") == "Active Decisions · 12 active"
    assert _section_label("Export / Import Decisions", None) == "Export / Import Decisions"


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