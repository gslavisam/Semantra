from types import SimpleNamespace

from streamlit_ui import api as streamlit_api


def test_backend_is_reachable_retries_after_cached_failure(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "api_base_url": "http://127.0.0.1:8000",
            "backend_reachable_base_url": "http://127.0.0.1:8000",
            "backend_reachable": False,
        }
    )
    refresh_calls: list[str] = []

    def fake_refresh() -> None:
        refresh_calls.append("called")
        fake_streamlit.session_state["backend_reachable"] = True

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "refresh_backend_reachability", fake_refresh)

    assert streamlit_api.backend_is_reachable() is True
    assert refresh_calls == ["called"]


def test_backend_is_reachable_keeps_cached_success_for_same_base_url(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "api_base_url": "http://127.0.0.1:8000",
            "backend_reachable_base_url": "http://127.0.0.1:8000",
            "backend_reachable": True,
        }
    )

    def fail_refresh() -> None:
        raise AssertionError("refresh should not run for cached healthy backend state")

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "refresh_backend_reachability", fail_refresh)

    assert streamlit_api.backend_is_reachable() is True


def test_request_mapping_analysis_summary_uses_current_workspace_context(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "upload_response": {
                "mapping_mode": "canonical",
                "target_system": "canonical",
                "source": {"dataset_name": "sap_material"},
            },
            "mapping_response": {"mappings": [{"source": "matnr", "target": "material_number"}]},
            "analysis_source_system": "SAP",
            "analysis_business_domain": "materials",
            "analysis_integration_name": "material-master",
        }
    )
    captured: dict[str, object] = {}

    def fake_api_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        return {"title": "ok"}

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "api_request", fake_api_request)

    result = streamlit_api.request_mapping_analysis_summary()

    assert result == {"title": "ok"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/mapping/analysis/summary"
    payload = captured["json"]
    assert payload["workspace"] == {
        "mapping_mode": "canonical",
        "source_dataset_name": "sap_material",
        "target_dataset_name": "canonical",
        "source_system": "SAP",
        "target_system": None,
        "business_domain": "materials",
        "integration_name": "material-master",
    }
    assert payload["mapping_response"] == {"mappings": [{"source": "matnr", "target": "material_number"}]}
    assert payload["options"] == {
        "audience": "technical_implementor",
        "include_narration_seed": True,
    }


def test_request_mapping_analysis_narration_posts_current_summary(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={"mapping_analysis_summary": {"title": "summary"}})
    captured: dict[str, object] = {}

    def fake_api_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        return {"spoken_script": "ok"}

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "api_request", fake_api_request)

    result = streamlit_api.request_mapping_analysis_narration()

    assert result == {"spoken_script": "ok"}
    assert captured["method"] == "POST"
    assert captured["path"] == "/mapping/analysis/narration"
    assert captured["json"] == {"summary": {"title": "summary"}}


def test_request_mapping_analysis_audio_posts_spoken_script(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    captured: dict[str, object] = {}

    def fake_api_request_bytes(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        return b"wav", "audio/wav"

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "api_request_bytes", fake_api_request_bytes)

    result = streamlit_api.request_mapping_analysis_audio("spoken text")

    assert result == (b"wav", "audio/wav")
    assert captured["method"] == "POST"
    assert captured["path"] == "/mapping/analysis/audio"
    assert captured["json"] == {"spoken_script": "spoken text"}