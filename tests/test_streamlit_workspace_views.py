"""Tests the main Streamlit workspace helpers and workflow glue logic."""

import pytest
from types import SimpleNamespace

from streamlit_ui.workspace_views import (
    WORKSPACE_SECTIONS,
    _workspace_copilot_context,
    _workspace_copilot_decisions_result,
    _workspace_copilot_handoff,
    _workspace_copilot_output_result,
    _workspace_copilot_review_result,
    _workspace_copilot_setup_result,
    poll_mapping_job,
    default_llm_validation_enabled,
    _workspace_codegen_action_label,
    _workspace_codegen_button_label,
    _workspace_codegen_block_reason,
    _workspace_codegen_format_label,
    _workspace_generated_artifact_header,
    _workspace_generated_artifact_code_language,
    _workspace_llm_refinement_enabled,
    _workspace_output_section_label,
    _workspace_preview_advisory_message,
    _workspace_refinement_source_response,
    companion_enrichment_message,
    resolve_active_workspace_section,
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


def test_companion_enrichment_message_supports_target_label() -> None:
    message = companion_enrichment_message({"matched_columns": 1, "unmatched_columns": []}, "Target")

    assert message == "Target companion metadata enriched 1 columns; all companion fields matched."


def test_workspace_codegen_block_reason_requires_all_accepted_decisions() -> None:
    assert _workspace_codegen_block_reason([{"source": "cust_id", "status": "accepted"}]) == ""
    assert _workspace_codegen_block_reason([{"source": "cust_id", "status": "needs_review"}]) == (
        "Pandas code generation is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )
    assert _workspace_codegen_block_reason(
        [{"source": "cust_id", "status": "needs_review"}],
        allow_unaccepted=True,
    ) == ""


def test_workspace_codegen_helpers_switch_to_pyspark_labels() -> None:
    assert _workspace_codegen_action_label("pyspark") == "PySpark code generation"
    assert _workspace_codegen_button_label("pyspark") == "Generate PySpark code"
    assert _workspace_generated_artifact_header("python-pyspark") == "Generated PySpark Code"
    assert _workspace_codegen_block_reason([{"source": "cust_id", "status": "needs_review"}], "pyspark") == (
        "PySpark code generation is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )
    assert _workspace_codegen_block_reason(
        [{"source": "cust_id", "status": "needs_review"}],
        "pyspark",
        allow_unaccepted=True,
    ) == ""


def test_workspace_codegen_helpers_support_dbt_labels() -> None:
    assert _workspace_codegen_action_label("dbt") == "dbt model generation"
    assert _workspace_codegen_button_label("dbt") == "Generate dbt model"
    assert _workspace_codegen_format_label("dbt") == "dbt model starter"
    assert _workspace_generated_artifact_header("sql-dbt") == "Generated dbt Model SQL"
    assert _workspace_generated_artifact_code_language("sql-dbt") == "sql"
    assert _workspace_codegen_block_reason([{"source": "cust_id", "status": "needs_review"}], "dbt") == (
        "dbt model generation is blocked until all active mapping decisions are accepted. "
        "Review statuses: needs_review."
    )


def test_workspace_output_section_label_appends_detail_only_when_present() -> None:
    assert _workspace_output_section_label("Preview Result", "12 rows") == "Preview Result · 12 rows"
    assert _workspace_output_section_label("Generated Pandas Code", "") == "Generated Pandas Code"


def test_workspace_llm_refinement_enabled_requires_reachable_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from streamlit_ui import workspace_views

    monkeypatch.setattr(
        workspace_views,
        "st",
        SimpleNamespace(session_state={"runtime_config_snapshot": {"llm_provider": "lmstudio", "llm_status": "reachable"}}),
    )
    assert _workspace_llm_refinement_enabled() is True

    monkeypatch.setattr(
        workspace_views,
        "st",
        SimpleNamespace(session_state={"runtime_config_snapshot": {"llm_provider": "none", "llm_status": "disabled"}}),
    )
    assert _workspace_llm_refinement_enabled() is False


def test_workspace_refinement_source_response_prefers_pending_refinement() -> None:
    base = {"code": 'df_target["customer_id"] = df_source["cust_id"]'}
    refined = {"code": 'df_target["customer_id"] = df_source["cust_id"].astype(str)'}

    assert _workspace_refinement_source_response(base, refined) is refined
    assert _workspace_refinement_source_response(base, None) is base
    assert _workspace_refinement_source_response(base, {"code": "   "}) is base


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


def test_resolve_active_workspace_section_prefers_pending_handoff() -> None:
    session_state = {"active_workspace_section": "Setup", "pending_workspace_section": "Review"}

    assert resolve_active_workspace_section(session_state) == "Review"
    assert session_state["active_workspace_section"] == "Review"
    assert "pending_workspace_section" not in session_state


def test_resolve_active_workspace_section_defaults_to_setup_for_unknown_state() -> None:
    session_state = {"active_workspace_section": "Unknown"}

    assert resolve_active_workspace_section(session_state) == WORKSPACE_SECTIONS[0]
    assert session_state["active_workspace_section"] == "Setup"


def test_workspace_copilot_context_reads_workspace_state() -> None:
    context = _workspace_copilot_context(
        {
            "mapping_editor_state": {
                "cust_id": {"target": "customer_id", "status": "accepted"},
                "phone": {"target": "phone_number", "status": "needs_review"},
            },
            "llm_decision_proposals": [{"source": "phone"}],
            "runtime_config_snapshot": {"llm_provider": "lmstudio", "llm_status": "reachable", "llm_resolved_model": "gemma"},
        },
        selected_workspace_section="Review",
        upload_response={"mapping_mode": "canonical", "target_system": "sap"},
        mapping_response={"mapping_runtime": {"target_system": "sap", "target_projection_mode": "target_aware_canonical"}},
        preview_response=None,
        codegen_response=None,
    )

    assert context["section"] == "Review"
    assert context["active_decisions"] == 2
    assert context["accepted_items"] == 1
    assert context["open_review_items"] == 1
    assert context["pending_proposals"] == 1
    assert context["target_intent"] == "SAP"
    assert context["runtime_level"] == "ready"


def test_workspace_copilot_output_result_reports_codegen_blocker() -> None:
    result = _workspace_copilot_output_result(
        {
            "mapping_ready": True,
        },
        [{"source": "phone", "status": "needs_review"}],
        "pandas",
    )

    assert result["level"] == "warning"
    assert "blocked until all active mapping decisions are accepted" in result["answer"]
    assert any("Accept or close remaining review statuses" in item for item in result["next_actions"])


def test_workspace_copilot_decisions_result_reports_open_items() -> None:
    result = _workspace_copilot_decisions_result(
        {
            "mapping_ready": True,
            "open_review_items": 2,
            "pending_proposals": 1,
        }
    )

    assert result["level"] == "warning"
    assert "2 review item(s) and 1 pending proposal(s)" in result["answer"]
    assert result["handoff_actions"][0]["target_section"] == "Review"


def test_workspace_copilot_setup_result_offers_review_handoff_when_mapping_ready() -> None:
    result = _workspace_copilot_setup_result({"has_upload": True, "mapping_ready": True})

    assert result["level"] == "success"
    assert result["handoff_actions"][0]["target_section"] == "Review"


def test_workspace_copilot_handoff_sets_workspace_pending_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import workspace_views

    rerun_called = {"value": False}

    monkeypatch.setattr(
        workspace_views,
        "st",
        SimpleNamespace(
            session_state={},
            rerun=lambda: rerun_called.__setitem__("value", True),
        ),
    )

    _workspace_copilot_handoff(
        workspace_views.st.session_state,
        target_section="Decisions",
        message="Workspace Copilot handoff -> Decisions.",
    )

    assert workspace_views.st.session_state["pending_top_level_area"] == "Workspace"
    assert workspace_views.st.session_state["pending_workspace_section"] == "Decisions"
    assert workspace_views.st.session_state["active_workspace_section"] == "Decisions"
    assert rerun_called["value"] is True


def test_workspace_copilot_review_result_reuses_existing_summary_request() -> None:
    session_state = {"mapping_response": {"mappings": []}}

    result = _workspace_copilot_review_result(
        session_state,
        lambda: {
            "overall_mapping_health": {
                "accepted_count": 3,
                "needs_review_count": 1,
                "unmatched_count": 0,
                "summary": "Most mappings are stable, with one field still needing review.",
            }
        },
    )

    assert result["level"] == "success"
    assert result["answer"] == "Most mappings are stable, with one field still needing review."
    assert session_state["mapping_analysis_summary"]["overall_mapping_health"]["accepted_count"] == 3


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


def test_poll_mapping_job_timeout_tracks_active_job_for_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import workspace_views

    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(workspace_views, "st", fake_streamlit)

    def api_request(method: str, path: str, **kwargs):
        if method == "POST":
            return {"job_id": "job-timeout", "status": "queued"}
        return {"job_id": "job-timeout", "status": "running", "activity": []}

    with pytest.raises(RuntimeError, match="Resume current mapping job"):
        poll_mapping_job(
            api_request=api_request,
            start_path="/mapping/canonical/jobs",
            payload={"source_dataset_id": "source", "target_system": "canonical", "use_llm": False},
            status=SimpleNamespace(write=lambda _message: None),
            timeout_seconds=0.01,
        )

    assert fake_streamlit.session_state["active_mapping_job"]["job_id"] == "job-timeout"


def test_poll_mapping_job_resume_returns_completed_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import workspace_views

    fake_streamlit = SimpleNamespace(session_state={"active_mapping_job": {"job_id": "job-1"}})
    monkeypatch.setattr(workspace_views, "st", fake_streamlit)

    def api_request(method: str, path: str, **kwargs):
        assert method == "GET"
        assert path == "/mapping/jobs/job-1"
        return {
            "job_id": "job-1",
            "status": "completed",
            "activity": ["12:00:00 | Mapping job completed."],
            "response": {"mappings": [{"source": "A", "target": "B"}]},
        }

    response = poll_mapping_job(
        api_request=api_request,
        start_path="/mapping/canonical/jobs",
        payload={"source_dataset_id": "source", "target_system": "canonical", "use_llm": False},
        status=SimpleNamespace(write=lambda _message: None),
        existing_job_id="job-1",
        timeout_seconds=0.01,
    )

    assert response == {"mappings": [{"source": "A", "target": "B"}]}
    assert "active_mapping_job" not in fake_streamlit.session_state