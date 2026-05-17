from __future__ import annotations

import time

import httpx
import streamlit as st
from typing import Any


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
RUNTIME_CONFIG_REFRESH_SECONDS = 5.0


def api_request(
    method: str,
    path: str,
    *,
    files: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
    params: dict | None = None,
    timeout: float = 60.0,
) -> Any:
    headers = {"Accept": "application/json"}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            files=files,
            data=data,
            json=json,
            params=params,
        )
    _raise_for_status(response)
    return response.json()


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_error:
        try:
            detail = response.json().get("detail", response.text)
        except Exception:
            detail = response.text
        raise httpx.HTTPStatusError(
            f"HTTP {response.status_code}: {detail}",
            request=response.request,
            response=response,
        )


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


def detect_spec_hint_for_upload(uploaded_file, cache_key: str) -> dict | None:
    if uploaded_file is None or uploaded_file.name.lower().endswith(".sql"):
        return None

    file_bytes = uploaded_file_bytes(uploaded_file)
    signature = (uploaded_file.name, len(file_bytes), "spec-detect")
    cached_signature = st.session_state.get(f"{cache_key}_spec_signature")
    if cached_signature == signature:
        return st.session_state.get(f"{cache_key}_spec_hint")

    payload = api_request(
        "POST",
        "/upload/spec/detect",
        files={"file": (uploaded_file.name, file_bytes, uploaded_file.type or "text/csv")},
    )
    hint = payload.get("hint")
    st.session_state[f"{cache_key}_spec_signature"] = signature
    st.session_state[f"{cache_key}_spec_hint"] = hint
    return hint


def upload_dataset_handle(
    uploaded_file,
    *,
    mode: str,
    selected_table: str | None = None,
    name_col: str | None = None,
    description_col: str | None = None,
    type_col: str | None = None,
) -> dict:
    if uploaded_file is None:
        raise ValueError("Select a file before uploading.")

    request_files = upload_file_to_request_files(uploaded_file)
    if mode == "spec":
        form_data: dict[str, str] = {}
        if name_col:
            form_data["name_col"] = name_col
        if description_col:
            form_data["description_col"] = description_col
        if type_col:
            form_data["type_col"] = type_col
        return api_request("POST", "/upload/spec", files=request_files, data=form_data or None)
    return api_request(
        "POST",
        "/upload/handle",
        files=request_files,
        data={"selected_table": selected_table or ""},
    )


def enrich_dataset_metadata(
    dataset_id: str,
    uploaded_file,
    *,
    name_col: str | None = None,
    description_col: str | None = None,
    type_col: str | None = None,
) -> dict:
    if not dataset_id:
        raise ValueError("Select and upload the source dataset before applying companion metadata.")
    if uploaded_file is None:
        raise ValueError("Select a companion schema/spec file before applying metadata enrichment.")

    form_data = {"dataset_id": dataset_id}
    if name_col:
        form_data["name_col"] = name_col
    if description_col:
        form_data["description_col"] = description_col
    if type_col:
        form_data["type_col"] = type_col
    return api_request(
        "POST",
        "/upload/handle/metadata",
        files=upload_file_to_request_files(uploaded_file),
        data=form_data,
    )


def api_request_content(method: str, path: str, files: dict | None = None, data: dict | None = None) -> bytes:
    headers = {}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    with httpx.Client(timeout=60.0) as client:
        response = client.request(method, f"{base_url}{path}", headers=headers, files=files, data=data)
    response.raise_for_status()
    return response.content


def api_request_bytes(
    method: str,
    path: str,
    *,
    files: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
    timeout: float = 120.0,
) -> tuple[bytes, str]:
    headers = {}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    with httpx.Client(timeout=timeout) as client:
        response = client.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            files=files,
            data=data,
            json=json,
        )
    response.raise_for_status()
    return response.content, response.headers.get("content-type", "application/octet-stream")


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
        st.session_state["runtime_config_snapshot_refreshed_at"] = time.time()
        st.session_state["admin_requirement"] = {
            "requires_token": bool(payload.get("admin_api_token_configured", False)),
            "reachable": True,
        }
    except httpx.HTTPError:
        st.session_state["admin_requirement"] = {"requires_token": True, "reachable": False}
        st.session_state.pop("runtime_config_snapshot", None)
        st.session_state.pop("runtime_config_snapshot_refreshed_at", None)


def admin_token_required() -> bool:
    current_signature = (
        st.session_state.get("api_base_url", DEFAULT_API_BASE_URL),
        st.session_state.get("admin_token", ""),
    )
    cached_signature = st.session_state.get("admin_requirement_signature")
    requirement = st.session_state.get("admin_requirement", {"requires_token": True, "reachable": False})
    last_refreshed_at = float(st.session_state.get("runtime_config_snapshot_refreshed_at", 0.0) or 0.0)
    snapshot_stale = (time.time() - last_refreshed_at) >= RUNTIME_CONFIG_REFRESH_SECONDS
    if cached_signature != current_signature or not requirement.get("reachable", False) or snapshot_stale:
        refresh_admin_requirement()
        st.session_state["admin_requirement_signature"] = current_signature
    requirement = st.session_state.get("admin_requirement", {"requires_token": True, "reachable": False})
    return bool(requirement.get("requires_token", True))


def refresh_backend_reachability() -> None:
    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{base_url}/", headers={"Accept": "application/json"})
        response.raise_for_status()
        st.session_state["backend_reachable"] = True
    except httpx.HTTPError:
        st.session_state["backend_reachable"] = False


def backend_is_reachable() -> bool:
    current_base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL)
    cached_base_url = st.session_state.get("backend_reachable_base_url")
    if (
        cached_base_url != current_base_url
        or "backend_reachable" not in st.session_state
        or not bool(st.session_state.get("backend_reachable", False))
    ):
        refresh_backend_reachability()
        st.session_state["backend_reachable_base_url"] = current_base_url
    return bool(st.session_state.get("backend_reachable", False))


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


def request_mapping_analysis_summary() -> dict:
    upload_response = st.session_state.get("upload_response")
    mapping_response = st.session_state.get("mapping_response")
    if not upload_response or not mapping_response:
        raise ValueError("Generate mapping results before requesting an analysis overview.")

    mapping_mode = str(upload_response.get("mapping_mode") or "standard").strip().lower() or "standard"
    source_handle = upload_response.get("source") or {}
    target_handle = upload_response.get("target") or {}
    workspace_payload = {
        "mapping_mode": mapping_mode,
        "source_dataset_name": source_handle.get("dataset_name") or "Source dataset",
        "target_dataset_name": (
            upload_response.get("target_system")
            if mapping_mode == "canonical"
            else (target_handle.get("dataset_name") or "Target dataset")
        )
        or "Target dataset",
        "source_system": st.session_state.get("analysis_source_system") or None,
        "target_system": st.session_state.get("analysis_target_system") or None,
        "business_domain": st.session_state.get("analysis_business_domain") or None,
        "integration_name": st.session_state.get("analysis_integration_name") or None,
    }
    return api_request(
        "POST",
        "/mapping/analysis/summary",
        json={
            "mapping_response": mapping_response,
            "workspace": workspace_payload,
            "options": {
                "audience": "technical_implementor",
                "include_narration_seed": True,
            },
        },
        timeout=90.0,
    )


def request_review_plan_summary(
    filtered_rows: list[dict],
    attention_summary_rows: list[dict],
    *,
    status_filter: str,
    confidence_filter: str,
    source_filter: str,
) -> dict:
    mapping_response = st.session_state.get("mapping_response")
    if not mapping_response:
        raise ValueError("Generate mapping results before requesting a review plan.")

    return api_request(
        "POST",
        "/mapping/review-plan",
        json={
            "filtered_rows": filtered_rows,
            "attention_summary_rows": attention_summary_rows,
            "filters": {
                "status": status_filter,
                "confidence_label": confidence_filter,
                "source": source_filter,
            },
        },
        timeout=90.0,
    )


def request_mapping_analysis_narration() -> dict:
    summary = st.session_state.get("mapping_analysis_summary")
    if not summary:
        raise ValueError("Generate the mapping analysis overview before requesting narration.")

    return api_request(
        "POST",
        "/mapping/analysis/narration",
        json={"summary": summary},
        timeout=90.0,
    )


def request_mapping_analysis_audio(spoken_script: str) -> tuple[bytes, str]:
    if not spoken_script.strip():
        raise ValueError("Spoken script is empty; generate narration before requesting audio.")

    return api_request_bytes(
        "POST",
        "/mapping/analysis/audio",
        json={"spoken_script": spoken_script},
        timeout=300.0,
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