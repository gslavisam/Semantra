from __future__ import annotations

import httpx
import streamlit as st


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"


def api_request(
    method: str,
    path: str,
    *,
    files: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
) -> dict:
    headers = {"Accept": "application/json"}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    with httpx.Client(timeout=60.0) as client:
        response = client.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            files=files,
            data=data,
            json=json,
        )
    response.raise_for_status()
    return response.json()


def upload_file_to_request_files(uploaded_file) -> dict | None:
    if uploaded_file is None:
        return None
    return {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "text/csv",
        )
    }


def api_request_content(method: str, path: str, files: dict | None = None, data: dict | None = None) -> bytes:
    headers = {}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    with httpx.Client(timeout=60.0) as client:
        response = client.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            files=files,
            data=data,
        )
    response.raise_for_status()
    return response.content


def refresh_admin_requirement() -> None:
    headers = {"Accept": "application/json"}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token
    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(f"{base_url}/observability/config", headers=headers)
        if response.status_code == 403:
            st.session_state["admin_requirement"] = {"requires_token": True, "reachable": True}
            st.session_state.pop("runtime_config_snapshot", None)
            return
        response.raise_for_status()
        payload = response.json()
        st.session_state["runtime_config_snapshot"] = payload
        st.session_state["admin_requirement"] = {
            "requires_token": bool(payload.get("admin_api_token_configured", False)),
            "reachable": True,
        }
    except httpx.HTTPError:
        st.session_state["admin_requirement"] = {"requires_token": True, "reachable": False}
        st.session_state.pop("runtime_config_snapshot", None)


def admin_token_required() -> bool:
    current_signature = (
        st.session_state.get("api_base_url", DEFAULT_API_BASE_URL),
        st.session_state.get("admin_token", ""),
    )
    cached_signature = st.session_state.get("admin_requirement_signature")
    if cached_signature != current_signature:
        refresh_admin_requirement()
        st.session_state["admin_requirement_signature"] = current_signature
    requirement = st.session_state.get("admin_requirement", {"requires_token": True, "reachable": False})
    return bool(requirement.get("requires_token", True))


def backend_is_reachable() -> bool:
    admin_token_required()
    requirement = st.session_state.get("admin_requirement", {"reachable": False})
    return bool(requirement.get("reachable", False))


def request_llm_transformation_suggestion(source: str, target: str, instruction: str) -> dict:
    upload_response = st.session_state.get("upload_response")
    if not upload_response:
        raise ValueError("Upload source and target datasets before generating a transformation.")
    if not target:
        raise ValueError("Select a target column before generating a transformation.")
    if not instruction.strip():
        raise ValueError("Describe the desired transformation before generating code.")

    return api_request(
        "POST",
        "/mapping/transformation/generate",
        json={
            "source_dataset_id": upload_response["source"]["dataset_id"],
            "target_dataset_id": upload_response["target"]["dataset_id"],
            "source_column": source,
            "target_column": target,
            "instruction": instruction.strip(),
        },
    )


def request_transformation_templates() -> list[dict]:
    cached = st.session_state.get("transformation_templates")
    if cached is not None:
        return cached
    templates = api_request("GET", "/mapping/transformation/templates")
    st.session_state["transformation_templates"] = templates
    return templates


def uploaded_file_bytes(uploaded_file) -> bytes:
    return uploaded_file.getvalue() if uploaded_file is not None else b""


def sql_tables_for_upload(uploaded_file, cache_key: str) -> list[str]:
    if uploaded_file is None or not uploaded_file.name.lower().endswith(".sql"):
        return []

    file_bytes = uploaded_file_bytes(uploaded_file)
    signature = (uploaded_file.name, len(file_bytes))
    cached_signature = st.session_state.get(f"{cache_key}_signature")
    if cached_signature == signature:
        return st.session_state.get(f"{cache_key}_tables", [])

    payload = api_request(
        "POST",
        "/upload/sql/tables",
        files={"file": (uploaded_file.name, file_bytes, uploaded_file.type or "application/sql")},
    )
    st.session_state[f"{cache_key}_signature"] = signature
    st.session_state[f"{cache_key}_tables"] = payload["tables"]
    return payload["tables"]