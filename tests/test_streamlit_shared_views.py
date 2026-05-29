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
    assert "TTS configured: lmstudio_orpheus / orpheus-3b-0.1-ft" in captured["success"]
    assert "Version: 0.1.0" in captured["caption"]
    assert "Build: abc123def456" in captured["caption"]
    assert "Scoring profile: balanced" in captured["caption"]
    assert "LLM endpoint: http://127.0.0.1:1234/v1/chat/completions" in captured["caption"]
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
    assert brief["risks"] == ["No major blockers are visible in the current workspace snapshot."]
    assert brief["next_actions"] == ["Open Output and generate a preview or code artifact."]


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