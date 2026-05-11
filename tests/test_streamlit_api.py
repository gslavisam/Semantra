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