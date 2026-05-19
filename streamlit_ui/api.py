"""HTTP client helpers used by the Streamlit UI to call the Semantra API."""

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
    """Send a JSON-oriented request to the backend using the current Streamlit session settings."""

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
    """Convert a Streamlit uploaded file into the multipart tuple shape expected by httpx."""

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
    """Detect and cache likely schema-spec columns for an uploaded metadata file."""

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
    sample_values_col: str | None = None,
) -> dict:
    """Upload a source or target file and return the backend dataset-handle payload."""

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
        if sample_values_col:
            form_data["sample_values_col"] = sample_values_col
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
    sample_values_col: str | None = None,
) -> dict:
    """Attach companion schema or spec metadata to an already-uploaded dataset handle."""

    if not dataset_id:
        raise ValueError("Select and upload the dataset before applying companion metadata.")
    if uploaded_file is None:
        raise ValueError("Select a companion schema/spec file before applying metadata enrichment.")

    form_data = {"dataset_id": dataset_id}
    if name_col:
        form_data["name_col"] = name_col
    if description_col:
        form_data["description_col"] = description_col
    if type_col:
        form_data["type_col"] = type_col
    if sample_values_col:
        form_data["sample_values_col"] = sample_values_col
    return api_request(
        "POST",
        "/upload/handle/metadata",
        files=upload_file_to_request_files(uploaded_file),
        data=form_data,
    )


def api_request_content(method: str, path: str, files: dict | None = None, data: dict | None = None) -> bytes:
    """Send a request and return the raw response body for non-JSON endpoints."""

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
    """Send a request and return raw bytes together with the response content type."""

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
    """Refresh cached admin-token requirements and runtime config state from the backend."""

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
    """Return whether protected admin surfaces currently require a token."""

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
    """Probe the backend root endpoint and cache whether the API is currently reachable."""

    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{base_url}/", headers={"Accept": "application/json"})
        response.raise_for_status()
        st.session_state["backend_reachable"] = True
    except httpx.HTTPError:
        st.session_state["backend_reachable"] = False


def backend_is_reachable() -> bool:
    """Return cached backend reachability, refreshing it when the URL or cache state changes."""

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
    """Request a bounded LLM-generated transformation suggestion for one source-target pair."""

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


def request_llm_mapping_refinement(
    source: str,
    *,
    candidate_targets: list[str],
    meaning_hint: str = "",
    negative_hint: str = "",
    sample_values: list[str] | None = None,
    refinement_instruction: str = "",
) -> dict:
    """Request bounded LLM refinement for one source field against a closed candidate set."""

    upload_response = st.session_state.get("upload_response")
    if not upload_response:
        raise ValueError("Upload datasets and generate mapping results before refining a mapping.")
    if not source.strip():
        raise ValueError("Select a source field before refining a mapping.")

    mapping_mode = str(upload_response.get("mapping_mode") or "standard").strip().lower() or "standard"
    payload = {
        "source_dataset_id": upload_response["source"]["dataset_id"],
        "source_field": source,
        "candidate_targets": [str(target or "").strip() for target in candidate_targets if str(target or "").strip()],
        "use_llm": bool(st.session_state.get("use_llm_validation", True)),
        "description_priority": bool(st.session_state.get("use_description_priority", False)),
        "candidate_pool_size": (
            int(st.session_state.get("canonical_candidate_pool_size", 10))
            if mapping_mode == "canonical"
            else None
        ),
        "meaning_hint": meaning_hint,
        "negative_hint": negative_hint,
        "sample_values": list(sample_values or []),
        "refinement_instruction": refinement_instruction,
        **current_workspace_scope(),
    }
    if mapping_mode == "canonical":
        payload["target_system"] = upload_response.get("target_system", "canonical")
    else:
        payload["target_dataset_id"] = upload_response["target"]["dataset_id"]

    return api_request(
        "POST",
        "/mapping/refine",
        json=payload,
        timeout=90.0,
    )


def list_canonical_target_fields(target_system: str = "canonical") -> list[str]:
    """Load canonical target field ids for the selected virtual target system."""

    response = api_request(
        "GET",
        "/mapping/target-fields",
        params={"target_system": target_system},
    )
    return [str(item or "").strip() for item in response or [] if str(item or "").strip()]


def current_workspace_scope() -> dict[str, str | None]:
    """Return the current source-system, business-domain, and integration scope from session state."""

    return {
        "source_system": str(st.session_state.get("analysis_source_system") or "").strip() or None,
        "business_domain": str(st.session_state.get("analysis_business_domain") or "").strip() or None,
        "integration_name": str(st.session_state.get("analysis_integration_name") or "").strip() or None,
    }


def list_source_field_hints(
    *,
    source_system: str,
    business_domain: str | None = None,
    integration_name: str | None = None,
    source_field: str | None = None,
    active_only: bool = True,
) -> list[dict]:
    """List persisted source-field hints for the current workspace scope."""

    params = {"source_system": source_system}
    if business_domain:
        params["business_domain"] = business_domain
    if integration_name:
        params["integration_name"] = integration_name
    if source_field:
        params["source_field"] = source_field
    params["active_only"] = active_only
    return api_request("GET", "/mapping/source-field-hints", params=params)


def save_source_field_hint(
    *,
    source_field: str,
    source_system: str,
    meaning_hint: str,
    negative_hint: str = "",
    sample_values: list[str] | None = None,
    business_domain: str | None = None,
    integration_name: str | None = None,
    created_by: str | None = None,
) -> dict:
    """Persist one source-field hint so future mapping runs inherit the same guidance."""

    return api_request(
        "POST",
        "/mapping/source-field-hints",
        json={
            "source_field": source_field,
            "source_system": source_system,
            "business_domain": business_domain,
            "integration_name": integration_name,
            "meaning_hint": meaning_hint,
            "negative_hint": negative_hint,
            "sample_values": list(sample_values or []),
            "created_by": created_by,
        },
    )


def request_mapping_analysis_summary() -> dict:
    """Request the Mapping Analysis Overview for the current workspace state."""

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
        "source_system": current_workspace_scope().get("source_system"),
        "target_system": st.session_state.get("analysis_target_system") or None,
        "business_domain": current_workspace_scope().get("business_domain"),
        "integration_name": current_workspace_scope().get("integration_name"),
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
    """Request queue-level review guidance for the currently filtered mapping rows."""

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
    """Request a spoken narration script for the current mapping analysis summary."""

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
    """Convert a spoken narration script into downloadable audio bytes."""

    if not spoken_script.strip():
        raise ValueError("Spoken script is empty; generate narration before requesting audio.")

    return api_request_bytes(
        "POST",
        "/mapping/analysis/audio",
        json={"spoken_script": spoken_script},
        timeout=300.0,
    )


def request_transformation_templates() -> list[dict]:
    """Load and cache reusable transformation templates from the backend."""

    cached = st.session_state.get("transformation_templates")
    if cached is not None:
        return cached
    templates = api_request("GET", "/mapping/transformation/templates")
    st.session_state["transformation_templates"] = templates
    return templates


def uploaded_file_bytes(uploaded_file) -> bytes:
    """Return raw bytes for an uploaded file, or empty bytes when no file is selected."""

    return uploaded_file.getvalue() if uploaded_file is not None else b""


def sql_tables_for_upload(uploaded_file, cache_key: str) -> list[str]:
    """Inspect and cache SQL table names discovered in an uploaded schema snapshot."""

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