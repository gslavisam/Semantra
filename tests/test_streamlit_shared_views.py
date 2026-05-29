"""Tests reusable Streamlit shared-view helpers and rendering support logic."""

from types import SimpleNamespace

from streamlit_ui import shared_views


def _fake_streamlit(session_state: dict[str, object]) -> tuple[SimpleNamespace, dict[str, list[str]]]:
    captured: dict[str, list[str]] = {
        "markdown": [],
        "subheader": [],
        "warning": [],
        "info": [],
        "success": [],
        "error": [],
        "caption": [],
        "write": [],
    }

    fake_streamlit = SimpleNamespace(session_state=session_state)
    for method_name in captured:
        setattr(
            fake_streamlit,
            method_name,
            lambda message, method_name=method_name, **kwargs: captured[method_name].append(message),
        )
    return fake_streamlit, captured


def test_render_llm_runtime_status_shows_llm_and_tts_details(monkeypatch) -> None:
    fake_streamlit, captured = _fake_streamlit(
        {
            "admin_requirement": {"reachable": True, "requires_token": False},
            "runtime_config_snapshot": {
                "app_version": "0.1.0",
                "backend_build": "abc123def456",
                "scoring_profile": "balanced",
                "llm_provider": "lmstudio",
                "llm_model": "gemma-4-e2b-it",
                "llm_resolved_model": "gemma-4-e2b-it",
                "llm_status": "reachable",
                "llm_status_detail": "LM Studio is reachable and the configured model is available.",
                "lmstudio_base_url": "http://127.0.0.1:1234/v1/chat/completions",
                "llm_gate_min_score": 0.3,
                "llm_gate_max_score": 0.75,
                "tts_provider": "lmstudio_orpheus",
                "tts_status": "reachable",
                "tts_status_detail": "LM Studio is reachable and the configured TTS model is available.",
                "tts_timeout_seconds": 300.0,
                "lmstudio_tts_base_url": "http://127.0.0.1:1234",
                "lmstudio_orpheus_model": "orpheus-3b-0.1-ft",
                "lmstudio_orpheus_voice": "tara",
            },
        }
    )

    monkeypatch.setattr(shared_views, "st", fake_streamlit)
    monkeypatch.setattr(shared_views, "admin_token_required", lambda: False)

    shared_views.render_llm_runtime_status()

    assert captured["subheader"] == ["Runtime"]
    assert "LLM reachable: lmstudio / gemma-4-e2b-it" in captured["success"]
    assert "TTS reachable: lmstudio / orpheus-3b-0.1-ft" in captured["success"]
    assert "Version: 0.1.0" in captured["caption"]
    assert "Build: abc123def456" in captured["caption"]
    assert "Scoring profile: balanced" in captured["caption"]
    assert "LLM endpoint: http://127.0.0.1:1234/v1/chat/completions" in captured["caption"]
    assert "LM Studio is reachable and the configured TTS model is available." in captured["caption"]
    assert "TTS endpoint: http://127.0.0.1:1234" in captured["caption"]
    assert "TTS voice: tara | timeout=300.0s" in captured["caption"]


def test_render_llm_runtime_status_handles_disabled_tts(monkeypatch) -> None:
    fake_streamlit, captured = _fake_streamlit(
        {
            "admin_requirement": {"reachable": True, "requires_token": False},
            "runtime_config_snapshot": {
                "app_version": "0.1.0",
                "backend_build": "abc123def456",
                "scoring_profile": "balanced",
                "llm_provider": "none",
                "llm_model": "mock-validator",
                "llm_status": "disabled",
                "llm_gate_min_score": 0.3,
                "llm_gate_max_score": 0.75,
                "tts_provider": "none",
            },
        }
    )

    monkeypatch.setattr(shared_views, "st", fake_streamlit)
    monkeypatch.setattr(shared_views, "admin_token_required", lambda: False)

    shared_views.render_llm_runtime_status()

    assert "LLM is currently disabled." in captured["warning"]
    assert "TTS is currently disabled." in captured["info"]


def test_render_llm_runtime_status_marks_unreachable_tts_as_error(monkeypatch) -> None:
    fake_streamlit, captured = _fake_streamlit(
        {
            "admin_requirement": {"reachable": True, "requires_token": False},
            "runtime_config_snapshot": {
                "app_version": "0.1.0",
                "backend_build": "abc123def456",
                "scoring_profile": "balanced",
                "llm_provider": "none",
                "llm_model": "mock-validator",
                "llm_status": "disabled",
                "llm_gate_min_score": 0.3,
                "llm_gate_max_score": 0.75,
                "tts_provider": "lmstudio_orpheus",
                "tts_status": "unreachable",
                "tts_status_detail": "network_error: <urlopen error connection refused>",
                "tts_timeout_seconds": 300.0,
                "lmstudio_tts_base_url": "http://127.0.0.1:1234",
                "lmstudio_orpheus_model": "orpheus-3b-0.1-ft",
                "lmstudio_orpheus_voice": "tara",
            },
        }
    )

    monkeypatch.setattr(shared_views, "st", fake_streamlit)
    monkeypatch.setattr(shared_views, "admin_token_required", lambda: False)

    shared_views.render_llm_runtime_status()

    assert "TTS configured but unreachable: lmstudio / orpheus-3b-0.1-ft" in captured["error"]
    assert "network_error: <urlopen error connection refused>" in captured["caption"]


def test_workspace_copilot_sidebar_context_summarizes_workspace_state() -> None:
    context = shared_views.workspace_copilot_sidebar_context(
        {
            "active_top_level_area": "Workspace",
            "active_workspace_section": "Review",
            "upload_response": {"mapping_mode": "canonical", "target_system": "sap"},
            "mapping_response": {
                "mapping_runtime": {
                    "target_system": "sap",
                    "target_projection_mode": "target_aware_canonical",
                }
            },
            "preview_response": {"rows": 12},
            "codegen_response": {"code": "print('ok')"},
            "mapping_editor_state": {
                "cust_id": {"target": "customer_id", "status": "accepted"},
                "phone": {"target": "phone_number", "status": "needs_review"},
            },
            "llm_decision_proposals": [{"source": "phone"}],
            "runtime_config_snapshot": {
                "llm_provider": "lmstudio",
                "llm_status": "reachable",
                "llm_resolved_model": "gemma-4-e2b-it",
            },
            "workspace_copilot_result": {"answer": "Most mappings are stable, but one field still needs review."},
        }
    )

    assert context["active_area"] == "Workspace"
    assert context["section"] == "Review"
    assert context["target_intent"] == "SAP"
    assert context["projection_label"] == "target-aware canonical"
    assert context["runtime_message"] == "LLM ready: lmstudio / gemma-4-e2b-it"
    assert context["active_decisions"] == 2
    assert context["accepted_items"] == 1
    assert context["open_review_items"] == 1
    assert context["pending_proposals"] == 1
    assert context["preview_ready"] is True
    assert context["output_ready"] is True
    assert context["latest_answer"] == "Most mappings are stable, but one field still needs review."
    assert context["readiness_level"] == "warning"


def test_workspace_copilot_sidebar_context_marks_non_workspace_area_and_missing_uploads() -> None:
    context = shared_views.workspace_copilot_sidebar_context(
        {
            "active_top_level_area": "Catalog",
            "active_workspace_section": "Setup",
            "runtime_config_snapshot": {"llm_provider": "none", "llm_status": "disabled"},
        }
    )

    assert context["active_area"] == "Catalog"
    assert context["section"] == "Setup"
    assert context["target_intent"] == "Uploaded target dataset"
    assert context["projection_label"] == "dataset-to-dataset"
    assert context["runtime_message"] == "LLM unavailable"
    assert context["area_note"] == "Viewing Catalog while this sidebar mirrors the latest Workspace state."
    assert context["has_upload"] is False
    assert context["mapping_ready"] is False
    assert context["readiness_level"] == "info"
    assert context["readiness_message"] == "Setup is waiting for source and target upload context."


def test_workspace_copilot_sidebar_brief_highlights_review_work() -> None:
    brief = shared_views.workspace_copilot_sidebar_brief(
        {
            "active_top_level_area": "Workspace",
            "active_workspace_section": "Review",
            "upload_response": {"mapping_mode": "standard"},
            "mapping_response": {"mapping_runtime": {}},
            "mapping_editor_state": {
                "cust_id": {"target": "customer_id", "status": "accepted"},
                "phone": {"target": "phone_number", "status": "needs_review"},
            },
            "llm_decision_proposals": [{"source": "phone"}],
            "runtime_config_snapshot": {
                "llm_provider": "lmstudio",
                "llm_status": "reachable",
                "llm_resolved_model": "gemma-4-e2b-it",
            },
            "workspace_copilot_result": {"answer": "One field still needs review."},
            "last_action": {"message": "Generated a bounded mapping summary."},
        }
    )

    assert brief["context"]["section"] == "Review"
    assert brief["now"] == "Work the remaining 1 review item(s) in Review."
    assert "There are 1 open review item(s) still unresolved." in brief["risks"]
    assert "There are 1 pending proposal(s) that can drift decisions." in brief["risks"]
    assert "Close or accept the remaining review items." in brief["next_actions"]
    assert "Resolve pending proposals before final output steps." in brief["next_actions"]
    assert brief["top_blocker"] == "phone -> phone_number is needs review."
    assert brief["primary_action"] == {
        "label": "Focus top blocker",
        "action": "open_review_focus",
        "focus_sources": ["phone"],
    }
    assert brief["last_action_message"] == "Generated a bounded mapping summary."
    assert brief["latest_answer"] == "One field still needs review."


def test_workspace_copilot_sidebar_brief_points_to_output_when_workspace_is_stable() -> None:
    brief = shared_views.workspace_copilot_sidebar_brief(
        {
            "active_top_level_area": "Workspace",
            "active_workspace_section": "Decisions",
            "upload_response": {"mapping_mode": "standard"},
            "mapping_response": {"mapping_runtime": {}},
            "mapping_editor_state": {
                "cust_id": {"target": "customer_id", "status": "accepted"},
            },
        }
    )

    assert brief["now"] == "Review is stable enough to move into Output for preview or code generation."
    assert brief["top_blocker"] is None
    assert brief["primary_action"] == {"label": "Open Output", "action": "open_output"}
    assert brief["risks"] == ["No major blockers are visible in the current workspace snapshot."]
    assert brief["next_actions"] == ["Open Output and generate a preview or code artifact."]


def test_workspace_copilot_sidebar_brief_points_setup_when_upload_missing() -> None:
    brief = shared_views.workspace_copilot_sidebar_brief(
        {
            "active_top_level_area": "Workspace",
            "active_workspace_section": "Setup",
        }
    )

    assert brief["top_blocker"] == "No dataset pair is loaded yet, so the workspace flow cannot leave Setup."
    assert brief["primary_action"] == {"label": "Open Setup", "action": "open_setup"}


def test_workspace_copilot_quick_asks_group_by_section_and_fallback_to_default() -> None:
    review_groups = shared_views._workspace_copilot_quick_ask_groups("Review")
    fallback_groups = shared_views._workspace_copilot_quick_ask_groups("Unknown")
    review_prompts = shared_views._workspace_copilot_quick_asks("Review")

    assert review_groups[0][0] == "Most useful now"
    assert review_groups[1][0] == "Explain this step"
    assert "What should I review first?" in review_prompts
    assert "What does Output do?" in review_prompts
    assert len(review_prompts) >= 5
    assert fallback_groups == shared_views.WORKSPACE_COPILOT_CHAT_QUICK_ASK_GROUPS["default"]


def test_workspace_copilot_apply_selected_prompt_prefills_chat_input() -> None:
    state = {
        "workspace_copilot_quick_ask_review": ("Most useful now", "What should I review first?"),
    }

    prompt = shared_views._workspace_copilot_apply_selected_prompt("workspace_copilot_quick_ask_review", state)

    assert prompt == "What should I review first?"
    assert state[shared_views.WORKSPACE_COPILOT_CHAT_INPUT_KEY] == "What should I review first?"


def test_workspace_copilot_pending_widget_reset_clears_prompt_and_input() -> None:
    state = {
        shared_views.WORKSPACE_COPILOT_CHAT_INPUT_KEY: "What unlocks Review?",
        "workspace_copilot_quick_ask_setup": ("Most useful now", "What unlocks Review?"),
    }

    shared_views._workspace_copilot_queue_widget_reset("workspace_copilot_quick_ask_setup", state)
    applied = shared_views._workspace_copilot_apply_pending_widget_reset("workspace_copilot_quick_ask_setup", state)

    assert applied is True
    assert state[shared_views.WORKSPACE_COPILOT_CHAT_INPUT_KEY] == ""
    assert state["workspace_copilot_quick_ask_setup"] == shared_views.WORKSPACE_COPILOT_QUICK_ASK_PLACEHOLDER
    assert shared_views.WORKSPACE_COPILOT_PENDING_RESET_KEY not in state


def test_workspace_copilot_chat_response_explains_workspace_sections() -> None:
    response = shared_views.workspace_copilot_chat_response("What does Review do?", {"active_workspace_section": "Setup"})

    assert response["kind"] == "guide"
    assert "Review is where you inspect suggested mappings" in response["answer"]


def test_workspace_copilot_chat_response_reports_blocker_without_mapping() -> None:
    response = shared_views.workspace_copilot_chat_response(
        "Summarize current mapping state",
        {"active_top_level_area": "Workspace", "active_workspace_section": "Setup"},
    )

    assert response["kind"] == "mapping-blocked"
    assert "There is no active mapping result yet" in response["answer"]


def test_workspace_copilot_chat_response_uses_mapping_summary_when_available() -> None:
    state = {
        "active_top_level_area": "Workspace",
        "active_workspace_section": "Review",
        "upload_response": {"mapping_mode": "canonical", "target_system": "sap"},
        "mapping_response": {"mapping_runtime": {"target_system": "sap", "target_projection_mode": "target_aware_canonical"}},
        "mapping_editor_state": {
            "cust_id": {"target": "customer_id", "status": "accepted"},
        },
    }

    response = shared_views.workspace_copilot_chat_response(
        "Summarize current mapping state",
        state,
        request_mapping_analysis_summary_func=lambda: {
            "overall_mapping_health": {
                "accepted_count": 3,
                "needs_review_count": 1,
                "unmatched_count": 0,
                "summary": "Most mappings are stable, with one field still needing review.",
            }
        },
    )

    assert response["kind"] == "mapping-summary"
    assert "Most mappings are stable, with one field still needing review." in response["answer"]
    assert "SAP / target-aware canonical" in response["answer"]
    assert state["mapping_analysis_summary"]["overall_mapping_health"]["accepted_count"] == 3


def test_submit_workspace_copilot_chat_question_appends_history() -> None:
    state: dict[str, object] = {}

    response = shared_views.submit_workspace_copilot_chat_question("What does Output do?", state)

    assert response["kind"] == "guide"
    history = state["workspace_copilot_chat_history"]
    assert len(history) == 1
    assert history[0]["question"] == "What does Output do?"
    assert "Output is where you preview mapped results" in history[0]["answer"]
    assert "why" in history[0]


def test_workspace_copilot_chat_response_unlocks_review_from_setup() -> None:
    response = shared_views.workspace_copilot_chat_response(
        "What unlocks Review?",
        {"active_top_level_area": "Workspace", "active_workspace_section": "Setup"},
    )

    assert response["kind"] == "setup-unlock"
    assert "Review unlocks only after you upload" in response["answer"]
    assert response["action_buttons"] == [{"label": "Open Setup", "action": "open_setup"}]


def test_workspace_copilot_chat_response_returns_review_plan_for_current_slice(monkeypatch) -> None:
    state = {
        "active_top_level_area": "Workspace",
        "active_workspace_section": "Review",
        "upload_response": {"mapping_mode": "standard"},
        "mapping_response": {"mapping_runtime": {}},
    }

    monkeypatch.setattr(
        shared_views,
        "_workspace_review_plan_payload",
        lambda current_state: ([{"source": "cust_id"}], [{"source": "cust_id", "reason": "low confidence"}], {"status": "All", "confidence": "All", "source": "All"}),
    )

    response = shared_views.workspace_copilot_chat_response(
        "What should I review first?",
        state,
        request_review_plan_summary_func=lambda filtered_rows, attention_summary_rows, status_filter, confidence_filter, source_filter: {
            "queue_summary": "Start with cust_id because it combines low confidence and target ambiguity.",
            "risks": ["cust_id is likely to drift downstream if left unresolved."],
            "next_actions": ["Inspect cust_id in Review before broader queue cleanup."],
        },
    )

    assert response["kind"] == "review-plan"
    assert "Start with cust_id" in response["answer"]
    assert response["why"] == "cust_id is likely to drift downstream if left unresolved."
    assert response["next_actions"] == ["Inspect cust_id in Review before broader queue cleanup."]
    assert response["action_buttons"] == [{"label": "Open Review", "action": "open_review"}]


def test_workspace_copilot_chat_response_adds_focus_rows_to_review_plan(monkeypatch) -> None:
    state = {
        "active_top_level_area": "Workspace",
        "active_workspace_section": "Review",
        "upload_response": {"mapping_mode": "standard"},
        "mapping_response": {"mapping_runtime": {}},
    }

    monkeypatch.setattr(
        shared_views,
        "_workspace_review_plan_payload",
        lambda current_state: ([{"source": "cust_id"}], [{"source": "cust_id", "reason": "low confidence"}], {"status": "All", "confidence": "All", "source": "All"}),
    )
    monkeypatch.setattr(
        shared_views,
        "_workspace_review_priority_rows",
        lambda current_state, limit=3: [
            {
                "source": "cust_id",
                "target": "customer_id",
                "status": "needs_review",
                "confidence_label": "low_confidence",
                "validator": "LLM validator",
                "canonical_path": "cust_id -> Customer Identifier -> customer_id",
            }
        ],
    )

    response = shared_views.workspace_copilot_chat_response(
        "What should I review first?",
        state,
        request_review_plan_summary_func=lambda filtered_rows, attention_summary_rows, status_filter, confidence_filter, source_filter: {
            "queue_summary": "Start with cust_id because it combines low confidence and target ambiguity.",
            "risks": ["cust_id is likely to drift downstream if left unresolved."],
            "next_actions": ["Inspect cust_id in Review before broader queue cleanup."],
        },
    )

    assert response["kind"] == "review-plan"
    assert "First focus: cust_id -> customer_id" in response["answer"]
    assert "Priority rows: cust_id -> customer_id" in response["why"]
    assert response["next_actions"][0] == "Focus Review on: cust_id."
    assert response["action_buttons"][0] == {
        "label": "Focus top review rows",
        "action": "open_review_focus",
        "focus_sources": ["cust_id"],
    }


def test_workspace_copilot_chat_response_summarizes_safe_proposals() -> None:
    response = shared_views.workspace_copilot_chat_response(
        "Which proposals are safe to apply?",
        {
            "active_top_level_area": "Workspace",
            "active_workspace_section": "Decisions",
            "llm_decision_proposals": [
                {"source": "cust_id", "safe_to_apply": True, "summary": "cust_id -> customer_id"},
                {"source": "order_amt", "safe_to_apply": False, "summary": "order_amt still needs review"},
            ],
        },
    )

    assert response["kind"] == "proposal-summary"
    assert "2 pending proposal(s), and 1 are marked safe_to_apply" in response["answer"]
    assert "cust_id -> customer_id" in response["why"]
    assert response["action_buttons"][0] == {"label": "Apply safe proposals", "action": "apply_safe_proposals"}


def test_workspace_copilot_chat_response_blocks_refinement_without_artifact() -> None:
    response = shared_views.workspace_copilot_chat_response(
        "Refine this artifact",
        {"active_top_level_area": "Workspace", "active_workspace_section": "Output"},
    )

    assert response["kind"] == "artifact-refinement-blocked"
    assert "until a generated artifact exists" in response["answer"]
    assert response["action_buttons"] == [{"label": "Open Output", "action": "open_output"}]


def test_workspace_copilot_chat_response_explains_output_artifact_details(monkeypatch) -> None:
    monkeypatch.setattr(shared_views, "_workspace_output_block_reason", lambda state: "")

    response = shared_views.workspace_copilot_chat_response(
        "Why is codegen blocked?",
        {
            "active_top_level_area": "Workspace",
            "active_workspace_section": "Output",
            "upload_response": {"mapping_mode": "standard"},
            "mapping_response": {"mapping_runtime": {}},
            "codegen_response": {
                "code": "print('ok')",
                "language": "python",
                "warnings": [{"code": "W001", "message": "Review null handling."}],
            },
            "codegen_refinement_response": {
                "code": "print('better')",
                "language": "python",
                "reasoning": ["Replaced the transformation step with a null-safe variant."],
                "warnings": [{"code": "RW01", "message": "Verify target type casting."}],
            },
        },
    )

    assert response["kind"] == "output-ready"
    assert "currently unblocked" in response["answer"]
    assert "Current artifact: Python artifact with 1 warning(s)." in response["why"]
    assert "Warning codes: W001." in response["why"]
    assert "pending with 1 reasoning note(s) and 1 warning(s)" in response["why"]


def test_workspace_copilot_chat_response_explains_artifact_refinement_state() -> None:
    response = shared_views.workspace_copilot_chat_response(
        "Refine this artifact",
        {
            "active_top_level_area": "Workspace",
            "active_workspace_section": "Output",
            "codegen_response": {
                "code": "select * from model",
                "language": "sql-dbt",
                "warnings": [{"code": "DBT01", "message": "Add explicit casts."}],
            },
            "codegen_refinement_response": {
                "code": "select cast(id as bigint) as id from model",
                "language": "sql-dbt",
                "reasoning": ["Added explicit casting for downstream safety."],
                "warnings": [{"code": "DBTR1", "message": "Verify warehouse-specific syntax."}],
            },
        },
    )

    assert response["kind"] == "artifact-refinement"
    assert "current dbt SQL artifact" in response["answer"]
    assert "Current artifact: dbt SQL artifact with 1 warning(s)." in response["why"]
    assert "Current warning codes: DBT01." in response["why"]
    assert "Pending refinement candidate: 1 reasoning note(s), 1 warning(s)." in response["why"]
    assert response["next_actions"][0] == "Use the existing warnings to target the refinement request."


def test_workspace_execute_artifact_refinement_pins_output_context(monkeypatch) -> None:
    state = {
        "active_top_level_area": "Workspace",
        "active_workspace_section": "Setup",
        "codegen_response": {"code": "print('ok')", "language": "python"},
        "workspace_copilot_refinement_instruction": "Add a defensive copy.",
    }

    monkeypatch.setattr(
        shared_views,
        "api_request",
        lambda method, path, json, timeout: {"code": "print('better')", "language": "python", "reasoning": ["Added copy."]},
    )

    response = shared_views._workspace_execute_artifact_refinement(state)

    assert response["code"] == "print('better')"
    assert state["pending_top_level_area"] == "Workspace"
    assert state["active_top_level_area"] == "Workspace"
    assert state["pending_workspace_section"] == "Output"
    assert state["active_workspace_section"] == "Output"
    assert state["codegen_refinement_response"]["code"] == "print('better')"


def test_workspace_accept_and_discard_refinement_preserve_output_context(monkeypatch) -> None:
    reruns: list[str] = []
    monkeypatch.setattr(shared_views, "st", SimpleNamespace(rerun=lambda: reruns.append("rerun")))

    accept_state = {
        "active_top_level_area": "Workspace",
        "active_workspace_section": "Setup",
        "codegen_refinement_response": {"code": "print('better')", "language": "python"},
    }
    shared_views._workspace_accept_refinement(accept_state)

    assert accept_state["pending_workspace_section"] == "Output"
    assert accept_state["active_workspace_section"] == "Output"
    assert accept_state["codegen_response"]["code"] == "print('better')"
    assert "codegen_refinement_response" not in accept_state

    discard_state = {
        "active_top_level_area": "Workspace",
        "active_workspace_section": "Setup",
        "codegen_refinement_response": {"code": "print('better')", "language": "python"},
    }
    shared_views._workspace_discard_refinement(discard_state)

    assert discard_state["pending_workspace_section"] == "Output"
    assert discard_state["active_workspace_section"] == "Output"
    assert "codegen_refinement_response" not in discard_state
    assert reruns == ["rerun", "rerun"]


def test_render_sidebar_help_uses_english_help_markdown(monkeypatch) -> None:
    fake_streamlit, captured = _fake_streamlit({})

    monkeypatch.setattr(shared_views, "st", fake_streamlit)
    monkeypatch.setattr(shared_views, "load_english_help_markdown", lambda: "# Help for the Semantra UI\n\nEnglish reference")

    shared_views.render_sidebar_help()

    assert captured["subheader"] == ["Help"]
    assert captured["caption"] == ["English reference guide for the Semantra UI."]
    assert captured["markdown"] == ["# Help for the Semantra UI\n\nEnglish reference"]


def test_available_reference_documents_filters_and_sorts_markdown(tmp_path) -> None:
    (tmp_path / "z-last.md").write_text("# Z", encoding="utf-8")
    (tmp_path / "A-first.md").write_text("# A", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")

    documents = shared_views.available_reference_documents(tmp_path, extra_documents=())

    assert [document.name for document in documents] == ["A-first.md", "z-last.md"]


def test_available_reference_documents_includes_extra_markdown_files(tmp_path) -> None:
    extra_document = tmp_path / "Conceptualization.md"
    extra_document.write_text("# Conceptualization", encoding="utf-8")

    documents = shared_views.available_reference_documents(tmp_path / "missing", extra_documents=(extra_document,))

    assert [document.name for document in documents] == ["Conceptualization.md"]


def test_reference_markdown_blocks_splits_mermaid_and_text() -> None:
    markdown_text = "# Title\n\nIntro\n\n```mermaid\nflowchart TD\n    A-->B\n```\n\nOutro"

    blocks = shared_views.reference_markdown_blocks(markdown_text)

    assert blocks == [
        ("markdown", "# Title\n\nIntro"),
        ("mermaid", "flowchart TD\n    A-->B"),
        ("markdown", "Outro"),
    ]


def test_render_reference_markdown_renders_mermaid_svg(monkeypatch) -> None:
    fake_streamlit, captured = _fake_streamlit({})

    monkeypatch.setattr(shared_views, "st", fake_streamlit)

    shared_views.render_reference_markdown(
        "# Title\n\n```mermaid\nflowchart TD\n    A-->B\n```\n\nOutro",
        mermaid_renderer=lambda diagram_source: "<svg><text>diagram</text></svg>",
    )

    assert captured["markdown"] == [
        "# Title",
        "<svg><text>diagram</text></svg>",
        "Outro",
    ]
    assert captured["warning"] == []


def test_render_reference_markdown_falls_back_to_raw_mermaid_when_svg_unavailable(monkeypatch) -> None:
    fake_streamlit, captured = _fake_streamlit({})

    monkeypatch.setattr(shared_views, "st", fake_streamlit)

    shared_views.render_reference_markdown(
        "```mermaid\nflowchart TD\n    A-->B\n```",
        mermaid_renderer=lambda diagram_source: None,
    )

    assert captured["warning"] == ["Mermaid rendering is temporarily unavailable, so the raw diagram source is shown instead."]
    assert captured["markdown"] == ["```mermaid\nflowchart TD\n    A-->B\n```"]


def test_render_sidebar_reference_uses_selected_reference_markdown(monkeypatch) -> None:
    fake_streamlit, captured = _fake_streamlit({})
    rendered_documents: list[str] = []

    reference_documents = [
        shared_views.Path("docs/reference/MAPPING_SIGNALS_AND_SCORING.md"),
        shared_views.Path("docs/reference/workflows.md"),
    ]

    monkeypatch.setattr(shared_views, "st", fake_streamlit)
    monkeypatch.setattr(shared_views, "available_reference_documents", lambda reference_dir=None: reference_documents)
    monkeypatch.setattr(shared_views, "load_reference_markdown", lambda reference_path: f"# {reference_path.name}\n\nReference")
    monkeypatch.setattr(shared_views, "render_reference_markdown", lambda markdown_text: rendered_documents.append(markdown_text))
    fake_streamlit.selectbox = lambda label, options, index=0, key=None, format_func=None: options[index]

    shared_views.render_sidebar_reference()

    assert captured["subheader"] == ["Reference"]
    assert captured["caption"] == [
        "Detailed technical references for Semantra behavior, scoring, and workflows.",
        "Showing docs/reference/MAPPING_SIGNALS_AND_SCORING.md",
    ]
    assert rendered_documents == ["# MAPPING_SIGNALS_AND_SCORING.md\n\nReference"]