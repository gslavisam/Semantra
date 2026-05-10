from streamlit_ui.workspace_decision_views import _saved_mapping_set_apply_block_reason


def test_saved_mapping_set_apply_block_reason_requires_approved_status() -> None:
    assert _saved_mapping_set_apply_block_reason({"status": "approved"}) == ""
    assert _saved_mapping_set_apply_block_reason({"status": "review"}) == (
        "Only approved mapping sets can be applied back into Workspace. Current status: review."
    )