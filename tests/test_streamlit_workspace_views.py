from streamlit_ui.workspace_views import (
    _workspace_codegen_block_reason,
    _workspace_preview_advisory_message,
    companion_enrichment_message,
    should_show_table_selector,
)


def test_should_show_table_selector_for_multitable_sql_snapshot() -> None:
    assert should_show_table_selector(["customers", "contacts"], "data", is_sql=True) is True


def test_should_not_show_table_selector_for_schema_spec_without_sql() -> None:
    assert should_show_table_selector(["customers", "contacts"], "Schema spec", is_sql=False) is False


def test_companion_enrichment_message_includes_unmatched_columns() -> None:
    message = companion_enrichment_message({"matched_columns": 2, "unmatched_columns": ["LAND1", "REGIO"]})

    assert message == "Source companion metadata enriched 2 columns; unmatched spec fields: LAND1, REGIO."


def test_companion_enrichment_message_reports_full_match() -> None:
    message = companion_enrichment_message({"matched_columns": 3, "unmatched_columns": []})

    assert message == "Source companion metadata enriched 3 columns; all companion fields matched."


def test_workspace_codegen_block_reason_requires_all_accepted_decisions() -> None:
    assert _workspace_codegen_block_reason([{"source": "cust_id", "status": "accepted"}]) == ""
    assert _workspace_codegen_block_reason([{"source": "cust_id", "status": "needs_review"}]) == (
        "Pandas code generation is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )


def test_workspace_preview_advisory_message_keeps_preview_available() -> None:
    assert _workspace_preview_advisory_message([{"source": "cust_id", "status": "accepted"}]) == ""
    assert _workspace_preview_advisory_message([{"source": "cust_id", "status": "needs_review"}]) == (
        "Preview is using active mapping decisions that are not fully approved yet. "
        "Review statuses: needs_review. Use it to inspect the current mapping before final approval."
    )