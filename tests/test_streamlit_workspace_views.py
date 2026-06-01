"""Tests the main Streamlit workspace helpers and workflow glue logic."""

import pytest
from types import SimpleNamespace

from streamlit_ui.workspace_views import (
    WORKSPACE_COPILOT_ACTIONS,
    WORKSPACE_SECTIONS,
    _load_setup_saved_draft_sessions,
    _resume_setup_saved_draft,
    _workspace_build_transformation_spec,
    _workspace_apply_transformation_spec_to_state,
    _workspace_copilot_chat_result,
    _workspace_copilot_context,
    _workspace_copilot_decisions_result,
    _workspace_copilot_execute_action_button,
    _workspace_copilot_handoff,
    _workspace_copilot_output_result,
    _workspace_copilot_review_result,
    _workspace_copilot_result_from_chat_response,
    _workspace_copilot_setup_result,
    _workspace_uploaded_file_or_none,
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
    _workspace_ready_transformation_spec,
    _workspace_refinement_source_response,
    _workspace_reset_transformation_design_state,
    _workspace_transformation_summary_caption,
    _workspace_transformation_spec_status,
    _workspace_transformation_target_fields,
    companion_enrichment_message,
    render_workspace_tab,
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


def test_workspace_transformation_target_fields_preserve_order_without_duplicates() -> None:
    assert _workspace_transformation_target_fields(
        [
            {"source": "cust_id", "target": "customer_id"},
            {"source": "name", "target": "customer_name"},
            {"source": "customer_code", "target": "customer_id"},
            {"source": "ignored", "target": "   "},
        ]
    ) == ["customer_id", "customer_name"]


def test_workspace_build_transformation_spec_reads_active_target_rules_only() -> None:
    spec = _workspace_build_transformation_spec(
        [{"target": "customer_id"}, {"target": "customer_name"}],
        {
            "workspace_transformation_target_grain": "One row per customer",
            "workspace_transformation_global_rules": "Deduplicate by customer_id.",
            "workspace_transformation_defaults": "Trim whitespace.",
            "workspace_transformation_examples": "N/A -> null",
            "workspace_transformation_rule::customer_id": "Cast source code to string.",
            "workspace_transformation_rule::customer_name": "Join first_name and last_name.",
            "workspace_transformation_rule::stale": "ignore",
        },
    )

    assert spec == {
        "target_grain": "One row per customer",
        "global_rules": "Deduplicate by customer_id.",
        "defaults": "Trim whitespace.",
        "examples": "N/A -> null",
        "target_fields": ["customer_id", "customer_name"],
        "field_rules": [
            {"target_field": "customer_id", "rule": "Cast source code to string."},
            {"target_field": "customer_name", "rule": "Join first_name and last_name."},
        ],
    }


def test_workspace_ready_transformation_spec_returns_none_until_ready() -> None:
    session_state = {
        "workspace_transformation_target_grain": "",
        "workspace_transformation_defaults": "",
        "workspace_transformation_global_rules": "",
        "workspace_transformation_rule::customer_id": "Cast KUNNR to string.",
    }

    assert _workspace_ready_transformation_spec([{"target": "customer_id"}], session_state) is None


def test_workspace_ready_transformation_spec_returns_spec_when_ready() -> None:
    session_state = {
        "workspace_transformation_target_grain": "One row per customer",
        "workspace_transformation_defaults": "Keep unmatched optional fields as null.",
        "workspace_transformation_global_rules": "",
        "workspace_transformation_examples": "",
        "workspace_transformation_rule::customer_id": "Cast KUNNR to string.",
    }

    assert _workspace_ready_transformation_spec(
        [{"target": "customer_id"}, {"target": "country_code"}],
        session_state,
    ) == {
        "target_grain": "One row per customer",
        "global_rules": "",
        "defaults": "Keep unmatched optional fields as null.",
        "examples": "",
        "target_fields": ["customer_id", "country_code"],
        "field_rules": [{"target_field": "customer_id", "rule": "Cast KUNNR to string."}],
    }


def test_workspace_transformation_spec_status_requires_target_grain() -> None:
    status = _workspace_transformation_spec_status(
        {
            "target_grain": "",
            "global_rules": "Normalize country codes.",
            "defaults": "",
            "target_fields": ["country_code"],
            "field_rules": [{"target_field": "country_code", "rule": "Map SAP land1 to ISO alpha-2."}],
        }
    )

    assert status["state"] == "incomplete"
    assert status["title"] == "Missing target grain"


def test_workspace_transformation_spec_status_uses_defaults_for_remaining_fields() -> None:
    status = _workspace_transformation_spec_status(
        {
            "target_grain": "One row per customer",
            "global_rules": "",
            "defaults": "Keep unmatched optional attributes as null.",
            "target_fields": ["customer_id", "country_code"],
            "field_rules": [{"target_field": "customer_id", "rule": "Cast KUNNR to string."}],
        }
    )

    assert status["state"] == "ready"
    assert status["missing_fields"] == ["country_code"]


def test_workspace_reset_transformation_design_state_clears_widget_and_snapshot_keys() -> None:
    session_state = {
        "workspace_transformation_target_grain": "One row per customer",
        "workspace_transformation_global_rules": "Normalize country codes.",
        "workspace_transformation_defaults": "Trim whitespace.",
        "workspace_transformation_examples": "N/A -> null",
        "workspace_transformation_proposal_instruction": "Propose customer mastering rules.",
        "workspace_transformation_spec_proposal": {"summary": {"state": "ready"}},
        "workspace_transformation_rule::customer_id": "Cast code to string.",
        "workspace_transformation_spec": {"target_grain": "One row per customer"},
        "workspace_transformation_spec_status": "ready",
        "other_key": 1,
    }

    _workspace_reset_transformation_design_state(session_state)

    assert session_state == {"other_key": 1}


def test_load_setup_saved_draft_sessions_caches_first_success(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import workspace_views

    calls: list[tuple[str, str]] = []
    fake_streamlit = SimpleNamespace(session_state={})
    monkeypatch.setattr(workspace_views, "st", fake_streamlit)

    def api_request(method: str, path: str, **_kwargs):
        calls.append((method, path))
        return [{"draft_session_id": 7, "name": "customer-wip"}]

    first = _load_setup_saved_draft_sessions(api_request)
    second = _load_setup_saved_draft_sessions(api_request)

    assert first == [{"draft_session_id": 7, "name": "customer-wip"}]
    assert second == first
    assert calls == [("GET", "/mapping/draft-sessions")]
    assert fake_streamlit.session_state["saved_draft_sessions"][0]["draft_session_id"] == 7


def test_resume_setup_saved_draft_restores_workspace_and_refreshes_list(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import workspace_views

    rerun_called = {"value": False}
    applied_detail = {"value": None}
    fake_streamlit = SimpleNamespace(
        session_state={},
        rerun=lambda: rerun_called.__setitem__("value", True),
    )
    monkeypatch.setattr(workspace_views, "st", fake_streamlit)

    def apply_draft_session_detail(detail: dict) -> str:
        applied_detail["value"] = detail
        fake_streamlit.session_state["upload_response"] = {"source": {"dataset_name": "source.csv"}}
        return "Output"

    monkeypatch.setattr(workspace_views, "_apply_draft_session_detail_to_workspace", apply_draft_session_detail)

    def api_request(method: str, path: str, **kwargs):
        if method == "GET" and path == "/mapping/draft-sessions":
            return [
                {
                    "draft_session_id": 7,
                    "name": "customer-wip",
                    "active_workspace_section": "Output",
                    "source_dataset_name": "source.csv",
                }
            ]
        if method == "GET" and path == "/mapping/draft-sessions/7":
            assert kwargs["params"] == {"created_by": "qa-user", "workspace_id": "ws-customer-01"}
            return {
                "draft_session_id": 7,
                "name": "customer-wip",
                "active_workspace_section": "Output",
                "source_handle": {"dataset_name": "source.csv", "schema_profile": {"columns": []}, "preview_rows": []},
                "target_handle": {"dataset_name": "target.csv", "schema_profile": {"columns": []}, "preview_rows": []},
                "mapping_mode": "standard",
                "mapping_editor_state": {},
                "mapping_decision_audit": {},
                "mapping_runtime": {},
            }
        raise AssertionError(f"Unexpected API request: {(method, path, kwargs)}")

    restored_section = _resume_setup_saved_draft(
        api_request,
        {
            "draft_session_id": 7,
            "name": "customer-wip",
            "created_by": "qa-user",
            "workspace_id": "ws-customer-01",
        },
    )

    assert restored_section == "Output"
    assert applied_detail["value"]["name"] == "customer-wip"
    assert fake_streamlit.session_state["saved_draft_sessions"][0]["draft_session_id"] == 7
    assert fake_streamlit.session_state["last_action"]["level"] == "success"
    assert "continued draft session 'customer-wip'".lower() in fake_streamlit.session_state["last_action"]["message"].lower()
    assert rerun_called["value"] is True


def test_workspace_apply_transformation_spec_to_state_replaces_existing_rules() -> None:
    session_state = {
        "workspace_transformation_rule::stale": "old",
        "workspace_transformation_rule::customer_id": "old id",
    }

    _workspace_apply_transformation_spec_to_state(
        session_state,
        {
            "target_grain": "One row per customer",
            "global_rules": "Deduplicate by customer_id.",
            "defaults": "Trim whitespace.",
            "examples": "N/A -> null",
            "target_fields": ["customer_id", "customer_name"],
            "field_rules": [
                {"target_field": "customer_id", "rule": "Cast KUNNR to string."},
                {"target_field": "customer_name", "rule": "Join first_name and last_name."},
            ],
        },
    )

    assert session_state == {
        "workspace_transformation_target_grain": "One row per customer",
        "workspace_transformation_global_rules": "Deduplicate by customer_id.",
        "workspace_transformation_defaults": "Trim whitespace.",
        "workspace_transformation_examples": "N/A -> null",
        "workspace_transformation_rule::customer_id": "Cast KUNNR to string.",
        "workspace_transformation_rule::customer_name": "Join first_name and last_name.",
    }


def test_workspace_transformation_summary_caption_compacts_backend_summary() -> None:
    assert _workspace_transformation_summary_caption(
        {"state": "ready", "described_count": 1, "target_count": 2, "missing_fields": ["country_code"]}
    ) == "Spec state: ready | described fields: 1/2 | missing: country_code"


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


def test_workspace_uploaded_file_or_none_filters_deleted_file_like_objects() -> None:
    class DeletedFile:
        pass

    file_like = SimpleNamespace(name="source.csv")

    assert _workspace_uploaded_file_or_none(file_like) is file_like
    assert _workspace_uploaded_file_or_none(DeletedFile()) is None
    assert _workspace_uploaded_file_or_none(SimpleNamespace(name="")) is None


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


def test_workspace_copilot_actions_expose_new_closure_and_output_questions() -> None:
    assert WORKSPACE_COPILOT_ACTIONS["Review"] == (
        "Summarize current mapping state",
        "Summarize Review -> Decisions risks",
    )
    assert WORKSPACE_COPILOT_ACTIONS["Decisions"] == (
        "What still needs a decision?",
        "Am I ready for Output?",
    )
    assert WORKSPACE_COPILOT_ACTIONS["Output"] == (
        "Why is codegen blocked?",
        "Explain output gating and warning priority",
    )


def test_workspace_copilot_result_from_chat_response_maps_handoffs() -> None:
    result = _workspace_copilot_result_from_chat_response(
        "Review",
        {
            "level": "warning",
            "answer": "Review is not closed enough.",
            "why": "Open review items remain.",
            "next_actions": ["Close the top blockers first."],
            "action_buttons": [
                {"label": "Focus top review rows", "action": "open_review_focus", "focus_sources": ["phone"]},
                {"label": "Open Decisions", "action": "open_decisions"},
            ],
        },
    )

    assert result["section"] == "Review"
    assert result["level"] == "warning"
    assert result["handoff_actions"][0] == {
        "label": "Focus top review rows",
        "target_section": "Review",
        "message": "Workspace Copilot handoff -> Review.",
        "focus_sources": ["phone"],
    }
    assert result["handoff_actions"][1]["target_section"] == "Decisions"
    assert result["action_buttons"][0] == {
        "label": "Focus top review rows",
        "action": "open_review_focus",
        "focus_sources": ["phone"],
    }


def test_workspace_copilot_result_from_chat_response_preserves_apply_safe_action() -> None:
    result = _workspace_copilot_result_from_chat_response(
        "Decisions",
        {
            "level": "warning",
            "answer": "There are pending proposals.",
            "why": "One proposal is safe.",
            "next_actions": ["Apply the safe proposal first."],
            "action_buttons": [
                {"label": "Apply safe proposals", "action": "apply_safe_proposals"},
                {"label": "Open Decisions", "action": "open_decisions"},
            ],
        },
    )

    assert result["handoff_actions"] == [
        {
            "label": "Open Decisions",
            "target_section": "Decisions",
            "message": "Workspace Copilot handoff -> Decisions.",
            "focus_sources": None,
        }
    ]
    assert result["action_buttons"][0] == {
        "label": "Apply safe proposals",
        "action": "apply_safe_proposals",
        "focus_sources": None,
    }


def test_workspace_copilot_chat_result_adapts_sidebar_response(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import shared_views

    monkeypatch.setattr(
        shared_views,
        "workspace_copilot_chat_response",
        lambda question, session_state, request_mapping_analysis_summary_func: {
            "level": "success",
            "answer": f"Handled: {question}",
            "why": "Bounded sidebar response reused by panel.",
            "next_actions": ["Open Output next."],
            "action_buttons": [{"label": "Open Output", "action": "open_output"}],
        },
    )

    result = _workspace_copilot_chat_result(
        {"active_workspace_section": "Decisions"},
        section="Decisions",
        question="Am I ready for Output?",
        request_mapping_analysis_summary=lambda: {},
    )

    assert result["section"] == "Decisions"
    assert result["answer"] == "Handled: Am I ready for Output?"
    assert result["handoff_actions"] == [
        {
            "label": "Open Output",
            "target_section": "Output",
            "message": "Workspace Copilot handoff -> Output.",
            "focus_sources": None,
        }
    ]


def test_workspace_copilot_execute_action_button_applies_safe_proposals(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import shared_views, workspace_views

    rerun_called = {"value": False}
    monkeypatch.setattr(workspace_views, "st", SimpleNamespace(rerun=lambda: rerun_called.__setitem__("value", True)))
    monkeypatch.setattr(shared_views, "_workspace_apply_safe_proposals", lambda state: (1, ["cust_id"]))
    monkeypatch.setattr(shared_views, "_workspace_run_action", lambda state, action_key, focus_sources=None, origin="Workspace Copilot": False)

    session_state = {"active_workspace_section": "Decisions"}
    _workspace_copilot_execute_action_button(
        session_state,
        {"label": "Apply safe proposals", "action": "apply_safe_proposals"},
        {"section": "Decisions"},
    )

    assert rerun_called["value"] is True
    assert session_state["workspace_copilot_result"]["answer"] == "Applied 1 safe proposal(s)."
    assert session_state["workspace_copilot_result"]["action_buttons"] == [{"label": "Open Decisions", "action": "open_decisions"}]
    assert session_state["last_action"]["message"] == "Applied 1 safe LLM proposal(s): cust_id."


def test_render_workspace_tab_renders_section_content_without_copilot_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import workspace_views

    rendered = {"content": 0}
    fake_streamlit = SimpleNamespace(
        session_state={},
        radio=lambda *args, **kwargs: "Review",
    )

    monkeypatch.setattr(workspace_views, "st", fake_streamlit)
    monkeypatch.setattr(workspace_views, "resolve_active_workspace_section", lambda session_state: "Review")
    monkeypatch.setattr(
        workspace_views,
        "_render_workspace_section_content",
        lambda **kwargs: rendered.__setitem__("content", rendered["content"] + 1),
    )

    render_workspace_tab(
        all_upload_types=["csv"],
        detect_spec_hint_for_upload=lambda uploaded_file, cache_key: None,
        recover_spec_hint_for_upload=lambda uploaded_file, cache_key: None,
        sql_tables_for_upload=lambda uploaded_file, cache_key: [],
        api_request=lambda *args, **kwargs: {},
        upload_dataset_handle=lambda *args, **kwargs: {},
        enrich_dataset_metadata=lambda *args, **kwargs: {},
        uploaded_file_bytes=lambda uploaded_file: b"",
        render_dataset_summary=lambda *args, **kwargs: None,
        initialize_mapping_editor_state=lambda *args, **kwargs: None,
        render_mapping_analysis_panel=lambda *args, **kwargs: None,
        display_trust_layer=lambda *args, **kwargs: None,
        render_mapping_review=lambda *args, **kwargs: None,
        render_mapping_editor=lambda *args, **kwargs: None,
        render_canonical_gap_assistant=lambda *args, **kwargs: None,
        render_canonical_concept_summary=lambda *args, **kwargs: None,
        render_active_draft_review_state_panel=lambda *args, **kwargs: None,
        render_active_draft_decision_state_panel=lambda *args, **kwargs: None,
        render_manual_mapping_panel=lambda *args, **kwargs: None,
        render_mapping_decision_summary=lambda *args, **kwargs: None,
        render_mapping_io_panel=lambda *args, **kwargs: None,
        render_mapping_set_versions_panel=lambda *args, **kwargs: None,
        render_correction_panel=lambda *args, **kwargs: None,
        build_mapping_decisions=lambda: [],
        request_mapping_analysis_summary=lambda: {},
    )

    assert rendered == {"content": 1}


def test_render_workspace_tab_ignores_deleted_file_like_state(monkeypatch: pytest.MonkeyPatch) -> None:
    from streamlit_ui import workspace_views

    class DeletedFile:
        pass

    rendered = {"content": 0}
    fake_streamlit = SimpleNamespace(
        session_state={"source_file": DeletedFile(), "target_file": DeletedFile(), "mapping_mode": "Standard"},
        radio=lambda *args, **kwargs: "Setup",
    )

    monkeypatch.setattr(workspace_views, "st", fake_streamlit)
    monkeypatch.setattr(workspace_views, "resolve_active_workspace_section", lambda session_state: "Setup")
    monkeypatch.setattr(
        workspace_views,
        "_render_workspace_section_content",
        lambda **kwargs: rendered.__setitem__("content", rendered["content"] + 1),
    )

    render_workspace_tab(
        all_upload_types=["csv"],
        detect_spec_hint_for_upload=lambda uploaded_file, cache_key: None,
        recover_spec_hint_for_upload=lambda uploaded_file, cache_key: None,
        sql_tables_for_upload=lambda uploaded_file, cache_key: (_ for _ in ()).throw(AssertionError("Should not inspect deleted files")),
        api_request=lambda *args, **kwargs: {},
        upload_dataset_handle=lambda *args, **kwargs: {},
        enrich_dataset_metadata=lambda *args, **kwargs: {},
        uploaded_file_bytes=lambda uploaded_file: b"",
        render_dataset_summary=lambda *args, **kwargs: None,
        initialize_mapping_editor_state=lambda *args, **kwargs: None,
        render_mapping_analysis_panel=lambda *args, **kwargs: None,
        display_trust_layer=lambda *args, **kwargs: None,
        render_mapping_review=lambda *args, **kwargs: None,
        render_mapping_editor=lambda *args, **kwargs: None,
        render_canonical_gap_assistant=lambda *args, **kwargs: None,
        render_canonical_concept_summary=lambda *args, **kwargs: None,
        render_active_draft_review_state_panel=lambda *args, **kwargs: None,
        render_active_draft_decision_state_panel=lambda *args, **kwargs: None,
        render_manual_mapping_panel=lambda *args, **kwargs: None,
        render_mapping_decision_summary=lambda *args, **kwargs: None,
        render_mapping_io_panel=lambda *args, **kwargs: None,
        render_mapping_set_versions_panel=lambda *args, **kwargs: None,
        render_correction_panel=lambda *args, **kwargs: None,
        build_mapping_decisions=lambda: [],
        request_mapping_analysis_summary=lambda: {},
    )

    assert rendered == {"content": 1}


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
    assert "active_workspace_section" not in workspace_views.st.session_state
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