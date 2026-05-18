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


def test_current_workspace_scope_reads_source_scope_from_session(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "analysis_source_system": "Senior HR",
            "analysis_business_domain": "HR",
            "analysis_integration_name": "employee-import",
        }
    )
    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)

    assert streamlit_api.current_workspace_scope() == {
        "source_system": "Senior HR",
        "business_domain": "HR",
        "integration_name": "employee-import",
    }


def test_save_source_field_hint_posts_expected_payload(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    captured: dict[str, object] = {}

    def fake_api_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        return {"hint_id": 1}

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "api_request", fake_api_request)

    result = streamlit_api.save_source_field_hint(
        source_field="tipOpe",
        source_system="Senior HR",
        business_domain="HR",
        integration_name="employee-import",
        meaning_hint="Operation type",
        negative_hint="Not contact name",
        sample_values=["SALE", "RETURN"],
    )

    assert result == {"hint_id": 1}
    assert captured["method"] == "POST"
    assert captured["path"] == "/mapping/source-field-hints"
    assert captured["json"] == {
        "source_field": "tipOpe",
        "source_system": "Senior HR",
        "business_domain": "HR",
        "integration_name": "employee-import",
        "meaning_hint": "Operation type",
        "negative_hint": "Not contact name",
        "sample_values": ["SALE", "RETURN"],
        "created_by": None,
    }


def test_list_source_field_hints_can_request_inactive_rows(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(session_state={})
    captured: dict[str, object] = {}

    def fake_api_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = kwargs.get("params")
        return [{"hint_id": 1}]

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "api_request", fake_api_request)

    result = streamlit_api.list_source_field_hints(
        source_system="Senior HR",
        active_only=False,
    )

    assert result == [{"hint_id": 1}]
    assert captured["method"] == "GET"
    assert captured["path"] == "/mapping/source-field-hints"
    assert captured["params"] == {
        "source_system": "Senior HR",
        "active_only": False,
    }


def test_request_llm_mapping_refinement_posts_expected_payload(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "upload_response": {
                "mapping_mode": "canonical",
                "source": {"dataset_id": "src-1"},
                "target_system": "canonical",
            },
            "use_llm_validation": True,
            "use_description_priority": True,
            "canonical_candidate_pool_size": 5,
            "analysis_source_system": "Senior HR",
            "analysis_business_domain": "HR",
            "analysis_integration_name": "employee-import",
        }
    )
    captured: dict[str, object] = {}

    def fake_api_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["json"] = kwargs.get("json")
        captured["timeout"] = kwargs.get("timeout")
        return {"selected": {"target": "employee_type"}}

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "api_request", fake_api_request)

    result = streamlit_api.request_llm_mapping_refinement(
        "tipOpe",
        candidate_targets=["employee_type", "employee_name"],
        meaning_hint="Operation type",
        negative_hint="Not employee name",
        sample_values=["SALE", "RETURN"],
        refinement_instruction="Prefer transaction type semantics.",
    )

    assert result == {"selected": {"target": "employee_type"}}
    assert captured["method"] == "POST"
    assert captured["path"] == "/mapping/refine"
    assert captured["timeout"] == 90.0
    assert captured["json"] == {
        "source_dataset_id": "src-1",
        "source_field": "tipOpe",
        "candidate_targets": ["employee_type", "employee_name"],
        "use_llm": True,
        "description_priority": True,
        "candidate_pool_size": 5,
        "meaning_hint": "Operation type",
        "negative_hint": "Not employee name",
        "sample_values": ["SALE", "RETURN"],
        "refinement_instruction": "Prefer transaction type semantics.",
        "source_system": "Senior HR",
        "business_domain": "HR",
        "integration_name": "employee-import",
        "target_system": "canonical",
    }


def test_request_llm_mapping_refinement_defaults_canonical_candidate_pool_size_to_10(monkeypatch) -> None:
    fake_streamlit = SimpleNamespace(
        session_state={
            "upload_response": {
                "mapping_mode": "canonical",
                "source": {"dataset_id": "src-1"},
                "target_system": "canonical",
            },
        }
    )
    captured: dict[str, object] = {}

    def fake_api_request(method: str, path: str, **kwargs):
        captured["json"] = kwargs.get("json")
        return {"selected": {"target": "employee_type"}}

    monkeypatch.setattr(streamlit_api, "st", fake_streamlit)
    monkeypatch.setattr(streamlit_api, "api_request", fake_api_request)

    streamlit_api.request_llm_mapping_refinement("tipOpe", candidate_targets=["employee_type"])

    assert captured["json"]["candidate_pool_size"] == 10


def test_list_canonical_target_fields_requests_mapping_target_options(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_api_request(method: str, path: str, **kwargs):
        captured["method"] = method
        captured["path"] = path
        captured["params"] = kwargs.get("params")
        return ["customer.id", "customer.name"]

    monkeypatch.setattr(streamlit_api, "api_request", fake_api_request)

    result = streamlit_api.list_canonical_target_fields("canonical")

    assert result == ["customer.id", "customer.name"]
    assert captured["method"] == "GET"
    assert captured["path"] == "/mapping/target-fields"
    assert captured["params"] == {"target_system": "canonical"}


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