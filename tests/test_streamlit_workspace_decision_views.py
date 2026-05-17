from streamlit_ui.workspace_decision_views import _saved_mapping_set_apply_block_reason, _section_label


def test_section_label_appends_detail_only_when_present() -> None:
    assert _section_label("Active Decisions", "12 active") == "Active Decisions · 12 active"
    assert _section_label("Export / Import Decisions", None) == "Export / Import Decisions"


def test_saved_mapping_set_apply_block_reason_requires_approved_status() -> None:
    assert _saved_mapping_set_apply_block_reason({"status": "approved"}) == ""
    assert _saved_mapping_set_apply_block_reason({"status": "review"}) == (
        "Only approved mapping sets can be applied back into Workspace. Current status: review."
    )