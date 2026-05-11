import pytest

from streamlit_ui.workspace_views import (
    poll_mapping_job,
    default_llm_validation_enabled,
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


def test_default_llm_validation_enabled_defaults_off_but_preserves_user_choice() -> None:
    assert default_llm_validation_enabled({}) is False
    assert default_llm_validation_enabled({"use_llm_validation": False}) is False
    assert default_llm_validation_enabled({"use_llm_validation": True}) is True


def test_poll_mapping_job_raises_on_canceled_status() -> None:
    responses = iter(
        [
            {"job_id": "job-1", "status": "queued"},
            {"job_id": "job-1", "status": "canceled", "activity": ["12:00:00 | Mapping job canceled."]},
        ]
    )

    class StatusRecorder:
        def __init__(self) -> None:
            self.messages: list[str] = []

        def write(self, message: str) -> None:
            self.messages.append(message)

    def api_request(method: str, path: str, **kwargs):
        return next(responses)

    with pytest.raises(RuntimeError, match="canceled"):
        poll_mapping_job(
            api_request=api_request,
            start_path="/mapping/auto/jobs",
            payload={"source_dataset_id": "source", "target_dataset_id": "target", "use_llm": False},
            status=StatusRecorder(),
            timeout_seconds=0.01,
        )