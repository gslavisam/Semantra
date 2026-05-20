"""Tests reusable Streamlit shared-view helpers and rendering support logic."""

from types import SimpleNamespace

from streamlit_ui import shared_views


def _fake_streamlit(session_state: dict[str, object]) -> tuple[SimpleNamespace, dict[str, list[str]]]:
    captured: dict[str, list[str]] = {
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
        setattr(fake_streamlit, method_name, lambda message, method_name=method_name: captured[method_name].append(message))
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