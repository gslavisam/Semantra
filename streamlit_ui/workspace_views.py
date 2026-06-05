"""Primary Workspace UI for upload, mapping, preview, and generation workflows."""

from __future__ import annotations

import httpx
import streamlit as st
import time

from streamlit_ui.api import current_workspace_scope, list_target_intents
from streamlit_ui.governance import api_error_message, mapping_output_block_reason
from streamlit_ui.workspace_decision_views import (
    _apply_draft_session_detail_to_workspace,
    _draft_session_identity_query_params,
    _draft_session_option_label,
    _resolve_selected_draft_session_id,
)


WORKSPACE_SECTIONS = ("Setup", "Review", "Decisions", "Output")
WORKSPACE_CODEGEN_MODES = ("pandas", "pyspark", "dbt")
WORKSPACE_COPILOT_ACTIONS = {
    "Setup": ("What unlocks Review?",),
    "Review": ("Summarize current mapping state", "Summarize Review -> Decisions risks"),
    "Decisions": ("What still needs a decision?", "Am I ready for Output?"),
    "Output": ("Why is codegen blocked?", "Explain output gating and warning priority"),
}


def _workspace_scope_caption(scope: dict[str, str | None]) -> str:
    parts = []
    if scope.get("source_system"):
        parts.append(f"source_system={scope['source_system']}")
    if scope.get("business_domain"):
        parts.append(f"business_domain={scope['business_domain']}")
    if scope.get("integration_name"):
        parts.append(f"integration_name={scope['integration_name']}")
    return " | ".join(parts)


def _render_workspace_context_panel() -> None:
    scope = current_workspace_scope()
    st.subheader("2. Workspace Context")
    st.caption(
        "Set the source scope once. Review, persistent source-field hints, and future runs reuse this workspace context."
    )
    context_columns = st.columns(3)
    context_columns[0].text_input(
        "Source system",
        key="analysis_source_system",
        placeholder="Example: SAP",
    )
    context_columns[1].text_input(
        "Business domain (optional)",
        key="analysis_business_domain",
        placeholder="Example: Procurement",
    )
    context_columns[2].text_input(
        "Integration name (optional)",
        key="analysis_integration_name",
        placeholder="Example: Vendor master",
    )
    active_scope = _workspace_scope_caption(current_workspace_scope())
    if active_scope:
        st.caption(f"Active workspace scope: {active_scope}")
    else:
        st.info(
            "Source system is optional for one-shot Review work, but required before you can save or manage persistent source-field hints."
        )


def _workspace_uploaded_file_or_none(uploaded_file):
    file_name = getattr(uploaded_file, "name", None)
    return uploaded_file if isinstance(file_name, str) and file_name.strip() else None


def _load_setup_saved_draft_sessions(api_request, *, force_refresh: bool = False) -> list[dict]:
    if not force_refresh and st.session_state.get("setup_saved_draft_sessions_loaded"):
        cached = st.session_state.get("saved_draft_sessions")
        return cached if isinstance(cached, list) else []

    try:
        saved_draft_sessions = api_request("GET", "/mapping/draft-sessions")
    except httpx.HTTPError as error:
        st.session_state["setup_saved_draft_sessions_loaded"] = True
        st.session_state["setup_saved_draft_sessions_error"] = api_error_message(
            error,
            default_prefix="Loading saved draft sessions failed",
        )
        cached = st.session_state.get("saved_draft_sessions")
        return cached if isinstance(cached, list) else []

    st.session_state["setup_saved_draft_sessions_loaded"] = True
    st.session_state["saved_draft_sessions"] = saved_draft_sessions
    st.session_state.pop("setup_saved_draft_sessions_error", None)
    return saved_draft_sessions


def _resume_setup_saved_draft(api_request, draft_session: dict) -> str:
    draft_session_id = int(draft_session.get("draft_session_id") or 0)
    if not draft_session_id:
        raise ValueError("Select a saved draft session before continuing.")

    draft_session_detail = api_request(
        "GET",
        f"/mapping/draft-sessions/{draft_session_id}",
        params=_draft_session_identity_query_params(draft_session),
    )
    restored_section = _apply_draft_session_detail_to_workspace(draft_session_detail)
    st.session_state["saved_draft_sessions"] = _load_setup_saved_draft_sessions(api_request, force_refresh=True)
    st.session_state["last_action"] = {
        "level": "success",
        "message": f"Continued draft session '{draft_session_detail['name']}' from Upload and restored Workspace {restored_section}.",
    }
    st.rerun()
    return restored_section


def _render_setup_saved_draft_panel(api_request) -> None:
    with st.expander("Continue Saved Draft", expanded=False):
        st.caption(
            "Resume a saved draft directly from Upload when you want to continue existing workspace work instead of starting a fresh upload."
        )

        refresh_column, _ = st.columns([1, 3])
        if refresh_column.button("Refresh saved drafts", key="setup_refresh_saved_drafts", width="stretch"):
            saved_draft_sessions = _load_setup_saved_draft_sessions(api_request, force_refresh=True)
        else:
            saved_draft_sessions = _load_setup_saved_draft_sessions(api_request)

        error_message = str(st.session_state.get("setup_saved_draft_sessions_error") or "").strip()
        if error_message:
            st.warning(error_message)

        if not saved_draft_sessions:
            st.info("No saved draft sessions are available yet. Save one from Decisions to continue it later from Upload.")
            return

        option_map = {
            int(item.get("draft_session_id") or 0): item
            for item in saved_draft_sessions
            if int(item.get("draft_session_id") or 0)
        }
        option_ids = list(option_map.keys())
        selected_draft_session_id = _resolve_selected_draft_session_id(
            saved_draft_sessions,
            selection_key="setup_selected_draft_session_id",
        )
        selected_draft_session_id = st.selectbox(
            "Saved draft session",
            options=option_ids,
            index=option_ids.index(selected_draft_session_id) if selected_draft_session_id in option_ids else 0,
            key="setup_selected_draft_session_id",
            format_func=lambda option_id: _draft_session_option_label(option_map[option_id]),
        )
        selected_draft_session = option_map[selected_draft_session_id]
        st.caption(
            f"Saved section: {selected_draft_session.get('active_workspace_section') or 'Decisions'} | "
            f"Source: {selected_draft_session.get('source_dataset_name') or 'n/a'}"
        )

        if st.button("Continue selected draft", key="setup_continue_selected_draft", width="stretch"):
            try:
                _resume_setup_saved_draft(api_request, selected_draft_session)
            except (KeyError, ValueError) as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Continuing saved draft failed: {error}"}
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": api_error_message(error, default_prefix="Continuing saved draft failed"),
                }
                st.rerun()


def _set_active_mapping_job(job_id: str, *, start_path: str, payload: dict) -> None:
    st.session_state["active_mapping_job"] = {
        "job_id": job_id,
        "start_path": start_path,
        "payload": dict(payload),
    }


def _clear_active_mapping_job() -> None:
    st.session_state.pop("active_mapping_job", None)


def poll_mapping_job(
    *,
    api_request,
    start_path: str,
    payload: dict,
    status,
    timeout_seconds: float = 600.0,
    existing_job_id: str | None = None,
) -> dict:
    """Start or resume an async mapping job and poll until a terminal state is reached."""

    if existing_job_id:
        job_id = existing_job_id
        _set_active_mapping_job(job_id, start_path=start_path, payload=payload)
        status.write(f"Resuming mapping job {job_id}.")
    else:
        started = api_request("POST", start_path, json=payload, timeout=30.0)
        job_id = started["job_id"]
        _set_active_mapping_job(job_id, start_path=start_path, payload=payload)
        status.write(f"Started mapping job {job_id}.")

    seen_activity_count = 0
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        job_status = api_request("GET", f"/mapping/jobs/{job_id}", timeout=30.0)
        activity = job_status.get("activity") or []
        for line in activity[seen_activity_count:]:
            status.write(line)
        seen_activity_count = len(activity)

        if job_status.get("status") == "completed":
            response = job_status.get("response")
            if not response:
                raise RuntimeError("Mapping job completed without a response payload.")
            _clear_active_mapping_job()
            return response
        if job_status.get("status") == "canceled":
            _clear_active_mapping_job()
            raise RuntimeError("Mapping job was canceled.")
        if job_status.get("status") == "failed":
            _clear_active_mapping_job()
            raise RuntimeError(job_status.get("error") or "Mapping job failed.")

        time.sleep(0.5)

    raise RuntimeError(
        f"Mapping job {job_id} did not finish before the timeout. "
        "The backend job may still be running; use Resume current mapping job to continue polling."
    )


def _workspace_codegen_action_label(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized == "pyspark":
        return "PySpark code generation"
    if normalized == "dbt":
        return "dbt model generation"
    return "Pandas code generation"


def _workspace_codegen_button_label(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized == "pyspark":
        return "Generate PySpark code"
    if normalized == "dbt":
        return "Generate dbt model"
    return "Generate Pandas code"


def _workspace_generated_artifact_header(language: str | None) -> str:
    normalized = str(language or "").strip().lower()
    if normalized == "python-pyspark":
        return "Generated PySpark Code"
    if normalized == "sql-dbt":
        return "Generated dbt Model SQL"
    return "Generated Pandas Code"


def _workspace_codegen_format_label(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized == "pyspark":
        return "PySpark starter"
    if normalized == "dbt":
        return "dbt model starter"
    return "Pandas starter"


def _workspace_generated_artifact_code_language(language: str | None) -> str:
    return "sql" if str(language or "").strip().lower() == "sql-dbt" else "python"


def _workspace_output_section_label(title: str, detail: str | None = None) -> str:
    detail_text = str(detail or "").strip()
    return f"{title} · {detail_text}" if detail_text else title


def _workspace_transformation_target_fields(mapping_decisions: list[dict]) -> list[str]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for item in mapping_decisions:
        target = str(item.get("target") or "").strip()
        if not target or target in seen_targets:
            continue
        seen_targets.add(target)
        targets.append(target)
    return targets


def _workspace_build_transformation_spec(mapping_decisions: list[dict], session_state: dict) -> dict:
    target_fields = _workspace_transformation_target_fields(mapping_decisions)
    field_rules = []
    for target_field in target_fields:
        field_rules.append(
            {
                "target_field": target_field,
                "rule": str(session_state.get(f"workspace_transformation_rule::{target_field}") or "").strip(),
            }
        )
    return {
        "target_grain": str(session_state.get("workspace_transformation_target_grain") or "").strip(),
        "global_rules": str(session_state.get("workspace_transformation_global_rules") or "").strip(),
        "defaults": str(session_state.get("workspace_transformation_defaults") or "").strip(),
        "examples": str(session_state.get("workspace_transformation_examples") or "").strip(),
        "target_fields": target_fields,
        "field_rules": field_rules,
    }


def _workspace_ready_transformation_spec(mapping_decisions: list[dict], session_state: dict) -> dict | None:
    spec = _workspace_build_transformation_spec(mapping_decisions, session_state)
    status = _workspace_transformation_spec_status(spec)
    if status["state"] != "ready":
        return None
    return {
        **spec,
        "field_rules": [
            item
            for item in spec.get("field_rules", [])
            if str((item or {}).get("target_field") or "").strip() and str((item or {}).get("rule") or "").strip()
        ],
    }


def _workspace_apply_transformation_spec_to_state(session_state: dict, spec: dict) -> None:
    session_state["workspace_transformation_target_grain"] = str(spec.get("target_grain") or "").strip()
    session_state["workspace_transformation_global_rules"] = str(spec.get("global_rules") or "").strip()
    session_state["workspace_transformation_defaults"] = str(spec.get("defaults") or "").strip()
    session_state["workspace_transformation_examples"] = str(spec.get("examples") or "").strip()
    valid_targets = {str(item).strip() for item in (spec.get("target_fields") or []) if str(item).strip()}
    for key in list(session_state.keys()):
        if str(key).startswith("workspace_transformation_rule::"):
            session_state.pop(key, None)
    for item in spec.get("field_rules") or []:
        target_field = str((item or {}).get("target_field") or "").strip()
        rule = str((item or {}).get("rule") or "").strip()
        if target_field and target_field in valid_targets:
            session_state[f"workspace_transformation_rule::{target_field}"] = rule


def _workspace_transformation_summary_caption(summary: dict | None) -> str:
    if not isinstance(summary, dict):
        return ""
    state = str(summary.get("state") or "").strip()
    described_count = int(summary.get("described_count") or 0)
    target_count = int(summary.get("target_count") or 0)
    missing_fields = [str(item) for item in (summary.get("missing_fields") or []) if str(item).strip()]
    detail = f"Spec state: {state} | described fields: {described_count}/{target_count}"
    if missing_fields:
        detail += f" | missing: {', '.join(missing_fields)}"
    return detail


def _workspace_transformation_spec_status(spec: dict) -> dict:
    target_fields = [str(item).strip() for item in (spec.get("target_fields") or []) if str(item).strip()]
    target_grain = str(spec.get("target_grain") or "").strip()
    global_rules = str(spec.get("global_rules") or "").strip()
    defaults = str(spec.get("defaults") or "").strip()
    described_fields: list[str] = []
    described_lookup: set[str] = set()
    for item in spec.get("field_rules") or []:
        target_field = str((item or {}).get("target_field") or "").strip()
        rule = str((item or {}).get("rule") or "").strip()
        if not target_field or not rule or target_field in described_lookup:
            continue
        described_lookup.add(target_field)
        described_fields.append(target_field)
    missing_fields = [target_field for target_field in target_fields if target_field not in described_lookup]

    if not target_fields:
        return {
            "state": "invalid",
            "level": "info",
            "title": "No active target fields",
            "message": "Add at least one active mapping decision before drafting a transformation spec.",
            "missing_fields": [],
            "described_count": 0,
            "target_count": 0,
        }
    if not target_grain:
        return {
            "state": "incomplete",
            "level": "warning",
            "title": "Missing target grain",
            "message": "Describe the target grain before using this transformation design as a governed output contract.",
            "missing_fields": missing_fields,
            "described_count": len(described_fields),
            "target_count": len(target_fields),
        }
    if not described_fields and not global_rules and not defaults:
        return {
            "state": "incomplete",
            "level": "warning",
            "title": "Add transformation rules",
            "message": "Define at least one field rule, global rule, or default behavior before this spec is ready.",
            "missing_fields": missing_fields,
            "described_count": 0,
            "target_count": len(target_fields),
        }
    if missing_fields and not defaults:
        return {
            "state": "incomplete",
            "level": "warning",
            "title": "Field coverage is incomplete",
            "message": "Add explicit rules for the remaining target fields or define default behavior.",
            "missing_fields": missing_fields,
            "described_count": len(described_fields),
            "target_count": len(target_fields),
        }
    return {
        "state": "ready",
        "level": "success",
        "title": "Ready for next output step",
        "message": (
            f"Structured spec covers {len(described_fields)} of {len(target_fields)} target field(s)"
            + (" with explicit defaults for the rest." if missing_fields else ".")
        ),
        "missing_fields": missing_fields,
        "described_count": len(described_fields),
        "target_count": len(target_fields),
    }


def _workspace_reset_transformation_design_state(session_state: dict) -> None:
    for key in (
        "workspace_transformation_target_grain",
        "workspace_transformation_global_rules",
        "workspace_transformation_defaults",
        "workspace_transformation_examples",
        "workspace_transformation_proposal_instruction",
        "workspace_transformation_spec_proposal",
        "workspace_transformation_spec",
        "workspace_transformation_spec_status",
        "workspace_transformation_spec_summary",
    ):
        session_state.pop(key, None)
    for key in list(session_state.keys()):
        if str(key).startswith("workspace_transformation_rule::"):
            session_state.pop(key, None)


def _render_workspace_transformation_design(mapping_decisions: list[dict], *, api_request) -> None:
    transformation_spec = _workspace_build_transformation_spec(mapping_decisions, st.session_state)
    transformation_status = _workspace_transformation_spec_status(transformation_spec)
    st.session_state["workspace_transformation_spec"] = transformation_spec
    st.session_state["workspace_transformation_spec_status"] = transformation_status["state"]
    st.session_state["workspace_transformation_spec_summary"] = transformation_status
    target_fields = transformation_spec["target_fields"]

    with st.expander(
        _workspace_output_section_label("Transformation Design", transformation_status["title"]),
        expanded=False,
    ):
        st.caption(
            "Define target grain, field-level rules, and global transformation behavior as a bounded spec before preview or code generation."
        )
        if transformation_status["level"] == "success":
            st.success(transformation_status["message"])
        elif transformation_status["level"] == "warning":
            st.warning(transformation_status["message"])
        else:
            st.info(transformation_status["message"])

        st.caption(
            "This first slice stores a reviewable structured spec in Workspace state. Preview and generated artifacts still use the current mapping/transformation contract until backend spec integration lands."
        )

        if not target_fields:
            return

        grain_col, defaults_col = st.columns(2)
        with grain_col:
            st.text_input(
                "Target grain",
                key="workspace_transformation_target_grain",
                placeholder="One row per customer / order / invoice line",
            )
        with defaults_col:
            st.text_area(
                "Defaults / fallback behavior",
                key="workspace_transformation_defaults",
                placeholder="Trim whitespace, keep unknown codes as null, cast numeric blanks to 0",
                height=104,
            )

        st.text_area(
            "Global rules",
            key="workspace_transformation_global_rules",
            placeholder="Normalize country codes to ISO alpha-2. Deduplicate by customer_id and keep the newest record.",
            height=120,
        )
        st.text_area(
            "Examples / edge cases",
            key="workspace_transformation_examples",
            placeholder="If source value is N/A -> null. If multiple addresses exist, keep the primary billing address.",
            height=104,
        )
        st.caption(f"Active target fields: {', '.join(target_fields)}")

        for target_field in target_fields:
            st.text_area(
                f"Rule for {target_field}",
                key=f"workspace_transformation_rule::{target_field}",
                placeholder=f"Describe how {target_field} is derived from source fields, defaults, or global rules.",
                height=88,
            )

        if transformation_status["missing_fields"]:
            st.caption(f"Missing explicit field rules: {', '.join(transformation_status['missing_fields'])}")

        st.text_area(
            "Natural-language spec proposal",
            key="workspace_transformation_proposal_instruction",
            placeholder="Describe the target grain, business rules, and any important field-level transformations you want proposed as a structured spec.",
            height=104,
        )
        proposal_left, proposal_right = st.columns([1, 2])
        with proposal_left:
            if st.button("Propose structured spec", key="workspace_propose_transformation_spec", width="stretch"):
                instruction = str(st.session_state.get("workspace_transformation_proposal_instruction") or "").strip()
                if not instruction:
                    st.session_state["last_action"] = {
                        "level": "warning",
                        "message": "Add natural-language transformation guidance before requesting a structured spec proposal.",
                    }
                    st.rerun()
                try:
                    st.session_state["workspace_transformation_spec_proposal"] = api_request(
                        "POST",
                        "/mapping/transformation/spec/propose",
                        json={
                            "mapping_decisions": mapping_decisions,
                            "instruction": instruction,
                            "current_spec": transformation_spec,
                        },
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": "Generated a bounded structured transformation spec proposal.",
                    }
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": api_error_message(error, default_prefix="Transformation spec proposal failed"),
                    }
                    st.rerun()
        with proposal_right:
            st.caption(
                "The proposal helper may suggest a structured spec, but it never auto-applies changes. Use Apply proposal to copy the proposal into the editable form."
            )

        proposal = st.session_state.get("workspace_transformation_spec_proposal")
        if isinstance(proposal, dict):
            proposal_summary = proposal.get("summary") or {}
            with st.expander(_workspace_output_section_label("Structured spec proposal", proposal_summary.get("title") or "Review proposal")):
                summary_caption = _workspace_transformation_summary_caption(proposal_summary)
                if summary_caption:
                    st.caption(summary_caption)
                reasoning = proposal.get("reasoning") or []
                if reasoning:
                    st.caption("Proposal reasoning")
                    for line in reasoning:
                        st.write(f"- {line}")
                warnings = proposal.get("warnings") or []
                if warnings:
                    for warning in warnings:
                        st.warning(str(warning))
                st.json(proposal.get("transformation_spec") or {})
                apply_col, discard_col = st.columns(2)
                with apply_col:
                    if st.button("Apply proposal", key="apply_transformation_spec_proposal", width="stretch"):
                        _workspace_apply_transformation_spec_to_state(
                            st.session_state,
                            proposal.get("transformation_spec") or {},
                        )
                        st.session_state.pop("workspace_transformation_spec_proposal", None)
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": "Applied the structured transformation spec proposal to the editable form.",
                        }
                        st.rerun()
                with discard_col:
                    if st.button("Discard proposal", key="discard_transformation_spec_proposal", width="stretch"):
                        st.session_state.pop("workspace_transformation_spec_proposal", None)
                        st.session_state["last_action"] = {
                            "level": "info",
                            "message": "Discarded the structured transformation spec proposal.",
                        }
                        st.rerun()

        clear_col, snapshot_col = st.columns([1, 2])
        with clear_col:
            if st.button("Clear transformation design", key="clear_transformation_design", width="stretch"):
                _workspace_reset_transformation_design_state(st.session_state)
                st.rerun()
        with snapshot_col:
            st.caption(
                f"Spec status: {transformation_status['state']} | described fields: {transformation_status['described_count']}/{transformation_status['target_count']}"
            )

        with st.expander("Structured spec snapshot"):
            st.json(transformation_spec)


def _workspace_llm_refinement_enabled() -> bool:
    config = st.session_state.get("runtime_config_snapshot") or {}
    provider = str(config.get("llm_provider", "none")).strip().lower() or "none"
    status = str(config.get("llm_status", "configured")).strip().lower() or "configured"
    return provider != "none" and status not in {"disabled", "misconfigured", "unreachable"}


def _workspace_refinement_source_response(
    codegen_response: dict | None,
    codegen_refinement_response: dict | None,
) -> dict | None:
    if isinstance(codegen_refinement_response, dict) and str(codegen_refinement_response.get("code") or "").strip():
        return codegen_refinement_response
    return codegen_response


def _workspace_codegen_block_reason(
    mapping_decisions: list[dict],
    mode: str = "pandas",
    *,
    allow_unaccepted: bool = False,
) -> str:
    if allow_unaccepted:
        blocked_statuses = sorted(
            {
                (str(item.get("status") or "").strip().lower() or "needs_review")
                for item in mapping_decisions
                if (str(item.get("status") or "").strip().lower() or "needs_review") not in {"accepted", "needs_review"}
            }
        )
        if not blocked_statuses:
            return ""
        return (
            f"{_workspace_codegen_action_label(mode)} is blocked by unsupported review statuses. "
            f"Review statuses: {', '.join(blocked_statuses)}."
        )
    return mapping_output_block_reason(
        mapping_decisions,
        action_label=_workspace_codegen_action_label(mode),
    )


def _workspace_preview_advisory_message(mapping_decisions: list[dict]) -> str:
    blocked_statuses = sorted(
        {
            (str(item.get("status") or "").strip().lower() or "needs_review")
            for item in mapping_decisions
            if (str(item.get("status") or "").strip().lower() or "needs_review") != "accepted"
        }
    )
    if not blocked_statuses:
        return ""
    return (
        "Preview is using active mapping decisions that are not fully approved yet. "
        f"Review statuses: {', '.join(blocked_statuses)}. "
        "Use it to inspect the current mapping before final approval."
    )


def _workspace_preview_context_block_reason(upload_response: dict | None) -> str:
    current_upload = upload_response if isinstance(upload_response, dict) else {}
    source_snapshot = current_upload.get("source") or {}
    if str(source_snapshot.get("dataset_id") or "").strip():
        return ""
    return (
        "Preview requires a live source dataset snapshot in Workspace. "
        "If you opened a saved reviewed artifact, load the source dataset in Setup or continue a saved draft first."
    )


def should_show_table_selector(available_tables: list[str], upload_mode: str, *, is_sql: bool) -> bool:
    """Return whether the UI should show table selection for the current upload mode."""

    return bool(available_tables) and (is_sql or upload_mode == "Row data")


def companion_enrichment_message(result: dict | None, dataset_label: str = "Source") -> str:
    """Summarize how many dataset columns were enriched by companion metadata."""

    if not result:
        return ""

    matched_columns = int(result.get("matched_columns") or 0)
    unmatched_columns = [str(item) for item in (result.get("unmatched_columns") or []) if str(item).strip()]
    if unmatched_columns:
        return (
            f"{dataset_label} companion metadata enriched {matched_columns} columns; "
            f"unmatched spec fields: {', '.join(unmatched_columns)}."
        )
    return f"{dataset_label} companion metadata enriched {matched_columns} columns; all companion fields matched."


def _workspace_target_intent_label(mapping_mode: str, target_system: str | None) -> str:
    normalized_mode = str(mapping_mode or "standard").strip().lower() or "standard"
    normalized_target_system = str(target_system or "").strip().lower() or None
    if normalized_mode != "canonical":
        return "Uploaded target dataset"
    if normalized_target_system == "sap":
        return "SAP"
    return "Canonical only"


def _workspace_projection_label(projection_mode: str | None) -> str:
    normalized = str(projection_mode or "").strip().lower()
    if normalized == "canonical_only":
        return "canonical-only"
    if normalized == "target_aware_canonical":
        return "target-aware canonical"
    return "dataset-to-dataset"


def _workspace_target_context(upload_response: dict | None, mapping_response: dict | None) -> dict | None:
    upload = upload_response or {}
    runtime = (mapping_response or {}).get("mapping_runtime") or {}
    mapping_mode = str(upload.get("mapping_mode") or "standard").strip().lower() or "standard"
    target_system = str(runtime.get("target_system") or upload.get("target_system") or "").strip().lower() or None
    projection_mode = str(runtime.get("target_projection_mode") or "").strip().lower()
    if not projection_mode:
        if mapping_mode == "canonical":
            projection_mode = "canonical_only" if target_system in {None, "canonical"} else "target_aware_canonical"
        else:
            projection_mode = "dataset_to_dataset"

    target_dataset_name = ""
    if mapping_mode != "canonical":
        target_dataset_name = str(((upload.get("target") or {}).get("dataset_name") or "")).strip()

    return {
        "mapping_mode": mapping_mode,
        "intent_label": _workspace_target_intent_label(mapping_mode, target_system),
        "target_system": target_system,
        "projection_label": _workspace_projection_label(projection_mode),
        "target_profile": str(runtime.get("target_profile") or "").strip() or None,
        "target_dataset_name": target_dataset_name,
    }


def _workspace_target_context_message(upload_response: dict | None, mapping_response: dict | None) -> str:
    context = _workspace_target_context(upload_response, mapping_response)
    if not context:
        return ""

    if context["mapping_mode"] != "canonical":
        dataset_name = context.get("target_dataset_name") or "uploaded target schema"
        return f"Target context: {context['intent_label']} ({dataset_name}) | Projection: {context['projection_label']}"

    message = f"Target context: {context['intent_label']} | Projection: {context['projection_label']}"
    if context.get("target_profile"):
        message += f" | Profile: {context['target_profile']}"
    return message


def _apply_recovery_hint_to_manual_inputs(
    *,
    cache_key: str,
    hint: dict,
    suggestion: dict | None,
    manual_name_key: str,
    manual_desc_key: str,
    manual_type_key: str,
    manual_sample_key: str,
    success_message: str,
) -> None:
    st.session_state[manual_name_key] = str(hint.get("name_col") or "")
    st.session_state[manual_desc_key] = str(hint.get("description_col") or "")
    st.session_state[manual_type_key] = str(hint.get("type_col") or "")
    st.session_state[manual_sample_key] = str(hint.get("sample_values_col") or "")
    header_row_index = int((suggestion or {}).get("header_row_index") or 1)
    st.session_state[f"{cache_key}_spec_header_row_index"] = header_row_index if header_row_index > 1 else None
    st.session_state["last_action"] = {"level": "info", "message": success_message}
    st.session_state[f"{cache_key}_spec_recovery_applied"] = True
    st.rerun()


def _render_spec_manual_inputs(
    *,
    manual_name_key: str,
    manual_desc_key: str,
    manual_type_key: str,
    manual_sample_key: str,
    name_label: str,
    description_label: str,
    type_label: str,
    sample_label: str,
) -> None:
    manual_columns = st.columns(4)
    manual_columns[0].text_input(name_label, key=manual_name_key, placeholder="e.g. Column")
    manual_columns[1].text_input(description_label, key=manual_desc_key, placeholder="e.g. Description")
    manual_columns[2].text_input(type_label, key=manual_type_key, placeholder="e.g. Type")
    manual_columns[3].text_input(sample_label, key=manual_sample_key, placeholder="e.g. Sample Values")


def _render_spec_detection_or_recovery(
    *,
    uploaded_file,
    cache_key: str,
    detected_hint: dict | None,
    recover_spec_hint_for_upload,
    manual_name_key: str,
    manual_desc_key: str,
    manual_type_key: str,
    manual_sample_key: str,
    detected_caption_prefix: str,
    missing_detection_message: str,
    apply_button_label: str,
    applied_message: str,
    name_label: str,
    description_label: str,
    type_label: str,
    sample_label: str,
) -> None:
    if uploaded_file is None:
        return

    if detected_hint:
        st.session_state.pop(f"{cache_key}_spec_header_row_index", None)
        st.caption(
            f"{detected_caption_prefix}: "
            f"name={detected_hint['name_col']}, "
            f"description={detected_hint.get('description_col') or '-'}, "
            f"type={detected_hint.get('type_col') or '-'}, "
            f"sample={detected_hint.get('sample_values_col') or '-'}"
        )
        return

    recovery_response = recover_spec_hint_for_upload(uploaded_file, cache_key)
    recovery_hint = (recovery_response or {}).get("hint") or None
    recovery_suggestion = (recovery_response or {}).get("suggestion") or {}
    recovery_warnings = [str(item) for item in ((recovery_response or {}).get("warnings") or []) if str(item).strip()]
    confidence = float(recovery_suggestion.get("confidence") or (recovery_hint or {}).get("confidence") or 0.0)

    if recovery_hint:
        header_row_index = int(recovery_suggestion.get("header_row_index") or 1)
        st.caption(
            "Auto-detection found no matching column headers. "
            "Bounded recovery suggested: "
            f"name={recovery_hint['name_col']}, "
            f"description={recovery_hint.get('description_col') or '-'}, "
            f"type={recovery_hint.get('type_col') or '-'}, "
            f"sample={recovery_hint.get('sample_values_col') or '-'} | "
            f"header_row={header_row_index} | "
            f"confidence={confidence:.2f}"
        )
        if recovery_warnings:
            st.caption("Recovery warnings: " + " | ".join(recovery_warnings))
        if st.button(apply_button_label, key=f"{cache_key}_apply_spec_recovery"):
            _apply_recovery_hint_to_manual_inputs(
                cache_key=cache_key,
                hint=recovery_hint,
                suggestion=recovery_suggestion,
                manual_name_key=manual_name_key,
                manual_desc_key=manual_desc_key,
                manual_type_key=manual_type_key,
                manual_sample_key=manual_sample_key,
                success_message=applied_message,
            )
    else:
        st.caption(missing_detection_message)
        failure_reason = str((recovery_response or {}).get("failure_reason") or "").strip()
        if failure_reason:
            st.info(f"Bounded recovery did not produce a validated suggestion: {failure_reason}")

    _render_spec_manual_inputs(
        manual_name_key=manual_name_key,
        manual_desc_key=manual_desc_key,
        manual_type_key=manual_type_key,
        manual_sample_key=manual_sample_key,
        name_label=name_label,
        description_label=description_label,
        type_label=type_label,
        sample_label=sample_label,
    )


def _reset_workspace_mapping_state(session_state: dict) -> None:
    session_state.pop("mapping_response", None)
    session_state.pop("mapping_analysis_summary", None)
    session_state.pop("mapping_analysis_error", None)
    session_state.pop("mapping_analysis_spoken_script", None)
    session_state.pop("mapping_analysis_audio_bytes", None)
    session_state.pop("mapping_analysis_audio_mime_type", None)
    session_state.pop("mapping_analysis_audio_error", None)
    session_state.pop("review_plan_summary", None)
    session_state.pop("review_plan_error", None)
    session_state.pop("canonical_gap_candidates", None)
    session_state.pop("canonical_gap_suggestions", None)
    session_state.pop("canonical_gap_triage_summary", None)
    session_state.pop("canonical_gap_triage_error", None)
    session_state.pop("preview_response", None)
    session_state.pop("codegen_response", None)
    session_state.pop("codegen_refinement_response", None)
    session_state.pop("mapping_editor_state", None)
    session_state.pop("active_draft_session", None)
    session_state.pop("workspace_copilot_result", None)


def default_llm_validation_enabled(session_state: dict | None = None) -> bool:
    """Return the persisted default for whether bounded LLM validation is enabled in the UI."""

    state = session_state or {}
    if "use_llm_validation" not in state:
        return False
    return bool(state.get("use_llm_validation"))


def resolve_active_workspace_section(session_state: dict) -> str:
    preferred = str(session_state.pop("pending_workspace_section", "") or "").strip()
    current = str(session_state.get("active_workspace_section", "") or "").strip()
    if preferred in WORKSPACE_SECTIONS:
        session_state["active_workspace_section"] = preferred
    elif current not in WORKSPACE_SECTIONS:
        session_state["active_workspace_section"] = WORKSPACE_SECTIONS[0]
    return str(session_state.get("active_workspace_section") or WORKSPACE_SECTIONS[0])


def _workspace_copilot_runtime_status(session_state: dict) -> tuple[str, str]:
    config = session_state.get("runtime_config_snapshot") or {}
    provider = str(config.get("llm_provider", "none")).strip() or "none"
    status = str(config.get("llm_status", "configured")).strip().lower() or "configured"
    resolved_model = str(config.get("llm_resolved_model", "")).strip() or str(config.get("llm_model", "")).strip() or "n/a"

    if provider.lower() == "none":
        return "unavailable", "LLM unavailable"
    if status == "reachable":
        return "ready", f"LLM ready: {provider} / {resolved_model}"
    if status == "unreachable":
        return "error", f"LLM unreachable: {provider} / {resolved_model}"
    if status == "misconfigured":
        return "error", f"LLM misconfigured: {provider} / {resolved_model}"
    if status == "disabled":
        return "unavailable", "LLM disabled"
    return "info", f"LLM configured: {provider} / {resolved_model}"


def _workspace_copilot_context(
    session_state: dict,
    *,
    selected_workspace_section: str,
    upload_response: dict | None,
    mapping_response: dict | None,
    preview_response: dict | None,
    codegen_response: dict | None,
) -> dict:
    mapping_editor_state = session_state.get("mapping_editor_state") or {}
    active_decisions = 0
    open_review_items = 0
    accepted_items = 0
    for entry in mapping_editor_state.values():
        target = str((entry or {}).get("target") or "").strip()
        if not target:
            continue
        active_decisions += 1
        status = str((entry or {}).get("status") or "needs_review").strip().lower() or "needs_review"
        if status == "accepted":
            accepted_items += 1
        else:
            open_review_items += 1

    runtime_level, runtime_message = _workspace_copilot_runtime_status(session_state)
    target_context = _workspace_target_context(upload_response, mapping_response) or {}

    return {
        "section": selected_workspace_section,
        "has_upload": bool(upload_response),
        "mapping_ready": bool(mapping_response),
        "preview_ready": bool(preview_response),
        "codegen_ready": bool(codegen_response),
        "active_decisions": active_decisions,
        "accepted_items": accepted_items,
        "open_review_items": open_review_items,
        "pending_proposals": len(session_state.get("llm_decision_proposals") or []),
        "target_intent": str(target_context.get("intent_label") or "No target context yet"),
        "projection_label": str(target_context.get("projection_label") or "n/a"),
        "runtime_level": runtime_level,
        "runtime_message": runtime_message,
    }


def _workspace_copilot_focus_message(context: dict, *, codegen_mode: str) -> str:
    section = str(context.get("section") or "Setup")
    if section == "Setup":
        if not context.get("has_upload"):
            return "Start by uploading the active dataset context so Workspace can compute a real review surface."
        if not context.get("mapping_ready"):
            return "Your upload is ready; the next meaningful step is generating mapping so Review becomes real."
        return "Setup is complete enough. Move into Review and inspect the rows that still need attention."
    if section == "Review":
        open_review_items = int(context.get("open_review_items") or 0)
        if not context.get("mapping_ready"):
            return "Review has nothing to guide yet because there is no active mapping result."
        if open_review_items:
            return f"Focus on the {open_review_items} row(s) that are not fully closed before widening into Decisions or Output."
        return "Review is clean right now; use this surface to summarize state or move forward into Decisions/Output."
    if section == "Decisions":
        pending_proposals = int(context.get("pending_proposals") or 0)
        open_review_items = int(context.get("open_review_items") or 0)
        if pending_proposals or open_review_items:
            return "This is the decision-closing step: resolve pending proposals and any still-open review outcomes before treating output as finalized."
        return "Decision state looks closed. Output is the next operational step."
    if not context.get("mapping_ready"):
        return "Output is locked because there is no active mapping state yet."
    if context.get("open_review_items"):
        return f"Output is still governance-sensitive: close remaining review statuses before relying on {_workspace_codegen_action_label(codegen_mode).lower()}."
    return f"Output is ready for {_workspace_codegen_action_label(codegen_mode).lower()} if you want to materialize the current decisions."


def _workspace_copilot_handoff(
    session_state: dict,
    *,
    target_section: str,
    message: str,
    focus_sources: list[str] | None = None,
) -> None:
    session_state["pending_top_level_area"] = "Workspace"
    session_state["pending_workspace_section"] = target_section
    if target_section == "Review" and focus_sources:
        session_state["review_focus_sources"] = list(focus_sources)
    elif target_section != "Review":
        session_state.pop("review_focus_sources", None)
    session_state["last_action"] = {
        "level": "info",
        "message": message,
    }
    st.rerun()


def _workspace_copilot_result_from_chat_response(section: str, response: dict) -> dict:
    action_map = {
        "open_setup": "Setup",
        "open_review": "Review",
        "open_review_focus": "Review",
        "open_decisions": "Decisions",
        "open_output": "Output",
    }

    handoff_actions: list[dict] = []
    action_buttons: list[dict] = []
    for action in response.get("action_buttons") or []:
        if not isinstance(action, dict):
            continue
        action_key = str(action.get("action") or "").strip().lower()
        action_buttons.append(
            {
                "label": str(action.get("label") or "Run action"),
                "action": action_key,
                "focus_sources": action.get("focus_sources"),
            }
        )
        target_section = action_map.get(action_key)
        if not target_section:
            continue
        handoff_actions.append(
            {
                "label": str(action.get("label") or f"Open {target_section}"),
                "target_section": target_section,
                "message": f"Workspace Copilot handoff -> {target_section}.",
                "focus_sources": action.get("focus_sources"),
            }
        )

    return {
        "section": section,
        "level": str(response.get("level") or "info"),
        "title": "Workspace Copilot",
        "answer": str(response.get("answer") or "").strip(),
        "why": str(response.get("why") or "").strip(),
        "next_actions": [str(item).strip() for item in (response.get("next_actions") or []) if str(item).strip()],
        "action_buttons": action_buttons,
        "handoff_actions": handoff_actions,
    }


def _workspace_copilot_chat_result(
    session_state: dict,
    *,
    section: str,
    question: str,
    request_mapping_analysis_summary,
) -> dict:
    from streamlit_ui.shared_views import workspace_copilot_chat_response

    response = workspace_copilot_chat_response(
        question,
        session_state,
        request_mapping_analysis_summary_func=request_mapping_analysis_summary,
    )
    return _workspace_copilot_result_from_chat_response(section, response)


def _workspace_copilot_setup_result(context: dict) -> dict:
    if not context["has_upload"]:
        return {
            "section": "Setup",
            "level": "info",
            "title": "Setup status",
            "answer": "Review stays locked until you upload the source dataset and establish the workspace context.",
            "why": "There is no active upload payload yet, so Semantra has nothing to map or review.",
            "next_actions": ["Upload and profile the current dataset pair or canonical source.", "Generate mapping results from Setup."],
        }
    if not context["mapping_ready"]:
        return {
            "section": "Setup",
            "level": "info",
            "title": "Setup status",
            "answer": "Review unlocks after you generate mapping results from the current upload context.",
            "why": "The upload exists, but there is no active mapping response yet.",
            "next_actions": ["Confirm LLM validation preference if needed.", "Run Generate mapping or Generate canonical mapping."],
        }
    return {
        "section": "Setup",
        "level": "success",
        "title": "Setup status",
        "answer": "Setup is complete enough for review.",
        "why": "The workspace already has an active mapping response bound to the current upload context.",
        "next_actions": ["Switch to Review to inspect trust evidence and row-level candidates."],
        "handoff_actions": [
            {
                "label": "Open Review",
                "target_section": "Review",
                "message": "Workspace Copilot handoff -> Review.",
            }
        ],
    }


def _workspace_copilot_decisions_result(context: dict) -> dict:
    pending_proposals = int(context.get("pending_proposals") or 0)
    open_review_items = int(context.get("open_review_items") or 0)
    if not context["mapping_ready"]:
        return {
            "section": "Decisions",
            "level": "info",
            "title": "Decision status",
            "answer": "There are no active decisions yet because mapping has not been generated.",
            "why": "Decisions depends on the current mapping state.",
            "next_actions": ["Generate mapping from Setup first."],
            "handoff_actions": [
                {
                    "label": "Return to Setup",
                    "target_section": "Setup",
                    "message": "Workspace Copilot handoff -> Setup.",
                }
            ],
        }
    if open_review_items == 0 and pending_proposals == 0:
        return {
            "section": "Decisions",
            "level": "success",
            "title": "Decision status",
            "answer": "No open decision blockers are visible right now.",
            "why": "All active mapping decisions are already accepted and there are no pending LLM proposals.",
            "next_actions": ["Move to Output for preview or code generation."],
            "handoff_actions": [
                {
                    "label": "Open Output",
                    "target_section": "Output",
                    "message": "Workspace Copilot handoff -> Output.",
                }
            ],
        }
    next_actions = []
    handoff_actions = []
    if open_review_items:
        next_actions.append(f"Close {open_review_items} review item(s) before treating output as fully approved.")
        handoff_actions.append(
            {
                "label": "Open Review",
                "target_section": "Review",
                "message": "Workspace Copilot handoff -> Review.",
            }
        )
    if pending_proposals:
        next_actions.append(f"Inspect {pending_proposals} pending LLM proposal(s) in Decisions.")
    return {
        "section": "Decisions",
        "level": "warning",
        "title": "Decision status",
        "answer": f"{open_review_items} review item(s) and {pending_proposals} pending proposal(s) still need decision attention.",
        "why": "Workspace decisions are not fully closed yet.",
        "next_actions": next_actions,
        "handoff_actions": handoff_actions,
    }


def _workspace_copilot_output_result(context: dict, mapping_decisions: list[dict], codegen_mode: str) -> dict:
    if not context["mapping_ready"]:
        return {
            "section": "Output",
            "level": "info",
            "title": "Output status",
            "answer": "Code generation is unavailable until mapping exists.",
            "why": "Output depends on the active mapping decisions.",
            "next_actions": ["Generate mapping from Setup first."],
            "handoff_actions": [
                {
                    "label": "Return to Setup",
                    "target_section": "Setup",
                    "message": "Workspace Copilot handoff -> Setup.",
                }
            ],
        }

    codegen_block_reason = _workspace_codegen_block_reason(mapping_decisions, codegen_mode)
    preview_advisory_message = _workspace_preview_advisory_message(mapping_decisions)
    if codegen_block_reason:
        next_actions = ["Accept or close remaining review statuses before generating code."]
        if preview_advisory_message:
            next_actions.append("Use preview only as an inspection aid until those review statuses are closed.")
        return {
            "section": "Output",
            "level": "warning",
            "title": "Output status",
            "answer": codegen_block_reason,
            "why": preview_advisory_message or "Output gating follows active review status governance.",
            "next_actions": next_actions,
            "handoff_actions": [
                {
                    "label": "Open Decisions",
                    "target_section": "Decisions",
                    "message": "Workspace Copilot handoff -> Decisions.",
                }
            ],
        }

    return {
        "section": "Output",
        "level": "success",
        "title": "Output status",
        "answer": f"{_workspace_codegen_action_label(codegen_mode)} is currently unblocked.",
        "why": "All active mapping decisions are in a codegen-compatible state.",
        "next_actions": [f"Run {_workspace_codegen_button_label(codegen_mode)} when you are ready."],
        "handoff_actions": [],
    }


def _workspace_copilot_review_result(session_state: dict, request_mapping_analysis_summary) -> dict:
    if not session_state.get("mapping_response"):
        return {
            "section": "Review",
            "level": "info",
            "title": "Review status",
            "answer": "Review summary is unavailable until mapping exists.",
            "why": "The analysis summary reuses the current mapping response.",
            "next_actions": ["Generate mapping from Setup first."],
            "handoff_actions": [
                {
                    "label": "Return to Setup",
                    "target_section": "Setup",
                    "message": "Workspace Copilot handoff -> Setup.",
                }
            ],
        }
    try:
        summary = request_mapping_analysis_summary()
    except (ValueError, httpx.HTTPError) as error:
        return {
            "section": "Review",
            "level": "error",
            "title": "Review status",
            "answer": f"Mapping overview failed: {error}",
            "why": "The bounded review summary request did not complete successfully.",
            "next_actions": ["Check runtime availability and retry from Review."],
            "handoff_actions": [],
        }

    session_state["mapping_analysis_summary"] = summary
    session_state.pop("mapping_analysis_error", None)
    health = summary.get("overall_mapping_health") or {}
    accepted_count = int(health.get("accepted_count") or 0)
    needs_review_count = int(health.get("needs_review_count") or 0)
    unmatched_count = int(health.get("unmatched_count") or 0)
    answer = str(health.get("summary") or "Generated a read-only summary of the current mapping state.")
    next_actions = []
    if needs_review_count:
        next_actions.append(f"Review {needs_review_count} field(s) still marked for attention.")
    if unmatched_count:
        next_actions.append(f"Resolve {unmatched_count} unmatched field(s) before final output.")
    handoff_actions = []
    if not next_actions:
        next_actions.append("Use Decisions or Output for the next bounded step.")
        handoff_actions.append(
            {
                "label": "Open Decisions",
                "target_section": "Decisions",
                "message": "Workspace Copilot handoff -> Decisions.",
            }
        )
    return {
        "section": "Review",
        "level": "success",
        "title": "Review status",
        "answer": answer,
        "why": f"Accepted: {accepted_count} | Needs review: {needs_review_count} | Unmatched: {unmatched_count}",
        "next_actions": next_actions,
        "handoff_actions": handoff_actions,
    }


def _render_workspace_copilot_result(result: dict | None) -> None:
    if not result:
        return

    level = str(result.get("level") or "info").strip().lower() or "info"
    answer = str(result.get("answer") or "").strip()
    why = str(result.get("why") or "").strip()
    next_actions = [str(item).strip() for item in (result.get("next_actions") or []) if str(item).strip()]
    action_buttons = [item for item in (result.get("action_buttons") or []) if isinstance(item, dict)]
    handoff_actions = [item for item in (result.get("handoff_actions") or []) if isinstance(item, dict)]

    if not action_buttons and handoff_actions:
        for action in handoff_actions:
            target_section = str(action.get("target_section") or "Setup").strip()
            focus_sources = action.get("focus_sources")
            action_key = (
                "open_review_focus"
                if target_section == "Review" and focus_sources
                else f"open_{target_section.lower()}"
            )
            action_buttons.append(
                {
                    "label": str(action.get("label") or f"Open {target_section}"),
                    "action": action_key,
                    "focus_sources": focus_sources,
                }
            )

    if level == "error":
        st.error(answer)
    elif level == "warning":
        st.warning(answer)
    elif level == "success":
        st.success(answer)
    else:
        st.info(answer)

    if why:
        st.caption(why)
    if next_actions:
        st.caption("Next actions")
        for item in next_actions:
            st.write(f"- {item}")

    if action_buttons:
        st.caption("Do this now")
        action_columns = st.columns(len(action_buttons))
        for idx, action in enumerate(action_buttons):
            if action_columns[idx].button(
                str(action.get("label") or "Run action"),
                key=f"workspace_copilot_handoff_{idx}_{str(action.get('action') or 'workspace').lower()}",
                width="stretch",
            ):
                _workspace_copilot_execute_action_button(st.session_state, action, result)


def _workspace_copilot_execute_action_button(session_state: dict, action: dict, result: dict | None = None) -> None:
    from streamlit_ui.shared_views import _workspace_apply_safe_proposals, _workspace_run_action

    action_key = str(action.get("action") or "").strip().lower()
    focus_sources = [str(item).strip() for item in (action.get("focus_sources") or []) if str(item).strip()]
    if _workspace_run_action(session_state, action_key, focus_sources=focus_sources, origin="Workspace Copilot"):
        return

    if action_key == "apply_safe_proposals":
        applied_count, applied_sources = _workspace_apply_safe_proposals(session_state)
        current_section = str((result or {}).get("section") or session_state.get("active_workspace_section") or "Decisions").strip() or "Decisions"
        if applied_count:
            session_state["workspace_copilot_result"] = {
                "section": current_section,
                "level": "success",
                "title": "Workspace Copilot",
                "answer": f"Applied {applied_count} safe proposal(s).",
                "why": f"Applied sources: {', '.join(applied_sources)}.",
                "next_actions": ["Review remaining proposals or move into Output if decision state is now closed."],
                "action_buttons": [{"label": "Open Decisions", "action": "open_decisions"}],
                "handoff_actions": [],
            }
            session_state["last_action"] = {
                "level": "success",
                "message": f"Applied {applied_count} safe LLM proposal(s): {', '.join(applied_sources)}.",
            }
        else:
            session_state["workspace_copilot_result"] = {
                "section": current_section,
                "level": "warning",
                "title": "Workspace Copilot",
                "answer": "No safe proposals were applied.",
                "why": "The workspace state may have changed since the proposals were prepared.",
                "next_actions": ["Regenerate proposals from Review if needed."],
                "action_buttons": [{"label": "Open Review", "action": "open_review"}],
                "handoff_actions": [],
            }
        st.rerun()


def _render_workspace_copilot_shell(
    *,
    session_state: dict,
    selected_workspace_section: str,
    upload_response: dict | None,
    mapping_response: dict | None,
    preview_response: dict | None,
    codegen_response: dict | None,
    build_mapping_decisions,
    request_mapping_analysis_summary,
) -> None:
    context = _workspace_copilot_context(
        session_state,
        selected_workspace_section=selected_workspace_section,
        upload_response=upload_response,
        mapping_response=mapping_response,
        preview_response=preview_response,
        codegen_response=codegen_response,
    )
    mapping_decisions = build_mapping_decisions() if mapping_response else []
    codegen_mode = str(session_state.get("output_codegen_mode", "pandas") or "pandas")
    focus_message = _workspace_copilot_focus_message(context, codegen_mode=codegen_mode)
    result = session_state.get("workspace_copilot_result")
    if isinstance(result, dict) and str(result.get("section") or "").strip() != selected_workspace_section:
        result = None

    with st.container():
        title_col, signal_col = st.columns([3, 2])
        with title_col:
            st.subheader("Workspace Copilot")
            st.caption("Bounded, workflow-aware guidance for the current Workspace state.")
        with signal_col:
            st.caption(
                f"Section: {context['section']} | Decisions: {int(context['active_decisions'])} | Open review: {int(context['open_review_items'])} | Proposals: {int(context['pending_proposals'])}"
            )
            st.caption(f"Target: {context['target_intent']} | {context['runtime_message']}")

        st.info(focus_message)

        action_labels = WORKSPACE_COPILOT_ACTIONS.get(selected_workspace_section, ())
        if action_labels:
            action_columns = st.columns(len(action_labels))
            for idx, action_label in enumerate(action_labels):
                if action_columns[idx].button(action_label, key=f"workspace_copilot_action_{selected_workspace_section}_{idx}", width="stretch"):
                    if selected_workspace_section == "Setup":
                        session_state["workspace_copilot_result"] = _workspace_copilot_setup_result(context)
                    elif selected_workspace_section == "Review":
                        session_state["workspace_copilot_result"] = _workspace_copilot_chat_result(
                            session_state,
                            section="Review",
                            question=action_label,
                            request_mapping_analysis_summary=request_mapping_analysis_summary,
                        )
                    elif selected_workspace_section == "Decisions":
                        session_state["workspace_copilot_result"] = _workspace_copilot_chat_result(
                            session_state,
                            section="Decisions",
                            question=action_label,
                            request_mapping_analysis_summary=request_mapping_analysis_summary,
                        )
                    elif selected_workspace_section == "Output":
                        session_state["workspace_copilot_result"] = _workspace_copilot_chat_result(
                            session_state,
                            section="Output",
                            question=action_label,
                            request_mapping_analysis_summary=request_mapping_analysis_summary,
                        )
                    result = session_state.get("workspace_copilot_result")

        if result:
            st.caption("Latest answer")
            _render_workspace_copilot_result(result)
        else:
            st.caption("Latest answer")
            st.write("No action has been run yet for this section.")


def _render_workspace_section_content(
    *,
    selected_workspace_section: str,
    all_upload_types,
    detect_spec_hint_for_upload,
    recover_spec_hint_for_upload,
    api_request,
    upload_dataset_handle,
    enrich_dataset_metadata,
    render_dataset_summary,
    initialize_mapping_editor_state,
    render_mapping_analysis_panel,
    display_trust_layer,
    render_mapping_review,
    render_mapping_editor,
    render_canonical_gap_assistant,
    render_canonical_concept_summary,
    render_active_draft_review_state_panel,
    render_active_draft_decision_state_panel,
    render_manual_mapping_panel,
    render_mapping_decision_summary,
    render_mapping_io_panel,
    render_mapping_set_versions_panel,
    render_correction_panel,
    build_mapping_decisions,
    source_file,
    target_file,
    source_tables: list[str],
    target_tables: list[str],
    source_spec_hint,
    target_spec_hint,
    inspection_error: str | None,
    upload_response: dict | None,
    mapping_response: dict | None,
    preview_response: dict | None,
    codegen_response: dict | None,
    codegen_refinement_response: dict | None,
) -> None:
    if selected_workspace_section == "Setup":
        st.subheader("1. Upload")
        st.caption("Any row-based format can map to any other row-based format across CSV, JSON, XML, and XLSX.")
        mapping_mode = st.radio(
            "Mapping mode",
            options=["Standard", "Canonical"],
            horizontal=True,
            key="mapping_mode",
        )
        canonical_mode = mapping_mode == "Canonical"
        if canonical_mode:
            st.info(
                "Canonical mode uploads only the source file and maps it to the canonical glossary without requiring a target upload."
            )
        source_file = st.file_uploader("Source file", type=all_upload_types, key="source_file")
        if canonical_mode:
            try:
                target_intent_options = list_target_intents()
            except httpx.HTTPError as error:
                target_intent_options = [
                    {
                        "target_system": "canonical",
                        "label": "Canonical only",
                        "description": "Canonical-first mapping with no system-specific projection bias.",
                        "target_profile": "canonical_core",
                        "projection_mode": "canonical_only",
                    }
                ]
                st.warning(f"Target intent options could not be loaded from the backend. Falling back to Canonical only. Details: {error}")

            target_intent_map = {
                option["target_system"]: option
                for option in target_intent_options
                if option.get("target_system")
            }
            if not target_intent_map:
                target_intent_map = {
                    "canonical": {
                        "target_system": "canonical",
                        "label": "Canonical only",
                        "description": "Canonical-first mapping with no system-specific projection bias.",
                        "target_profile": "canonical_core",
                        "projection_mode": "canonical_only",
                    }
                }
            target_intent_keys = list(target_intent_map.keys())
            current_target_intent = str(st.session_state.get("canonical_target_system") or "canonical").strip().lower() or "canonical"
            if current_target_intent not in target_intent_map:
                st.session_state["canonical_target_system"] = target_intent_keys[0]
            st.selectbox(
                "Canonical target intent",
                options=target_intent_keys,
                key="canonical_target_system",
                format_func=lambda option_key: target_intent_map[option_key]["label"],
                help="Canonical-first mapping keeps the canonical layer as source of truth, while target intent adds system-aware projection hints.",
            )
            selected_target_intent = target_intent_map.get(
                str(st.session_state.get("canonical_target_system") or "canonical").strip().lower() or "canonical",
                target_intent_map[target_intent_keys[0]],
            )
            st.caption(
                f"{selected_target_intent['description']} Profile: {selected_target_intent.get('target_profile') or '-'} | Projection: {selected_target_intent.get('projection_mode') or '-'}"
            )
            target_file = None
        else:
            target_file = st.file_uploader("Target file", type=all_upload_types, key="target_file")

        _render_workspace_context_panel()

        st.subheader("3. Interpret Files")
        source_is_sql = bool(source_file and source_file.name.lower().endswith(".sql"))
        target_is_sql = bool(target_file and target_file.name.lower().endswith(".sql"))

        source_mode = "data"
        if source_file is not None:
            if source_is_sql:
                st.info("Source .sql upload is always treated as a schema snapshot.")
            else:
                source_mode = st.radio(
                    "Source mode",
                    options=["Row data", "Schema spec"],
                    index=1 if source_spec_hint else 0,
                    horizontal=True,
                    key="source_upload_mode",
                )
                if source_spec_hint:
                    _render_spec_detection_or_recovery(
                        uploaded_file=source_file,
                        cache_key="source",
                        detected_hint=source_spec_hint,
                        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                        manual_name_key="source_spec_manual_name_col",
                        manual_desc_key="source_spec_manual_desc_col",
                        manual_type_key="source_spec_manual_type_col",
                        manual_sample_key="source_spec_manual_sample_col",
                        detected_caption_prefix="Source file looks like a field specification",
                        missing_detection_message="Auto-detection found no matching column headers. Enter the column names from your spec file manually.",
                        apply_button_label="Use suggested source spec headers",
                        applied_message="Applied suggested source spec headers. Review or override them before uploading.",
                        name_label="Name column",
                        description_label="Description column",
                        type_label="Type column",
                        sample_label="Sample values column",
                    )
                elif source_mode == "Schema spec":
                    _render_spec_detection_or_recovery(
                        uploaded_file=source_file,
                        cache_key="source",
                        detected_hint=None,
                        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                        manual_name_key="source_spec_manual_name_col",
                        manual_desc_key="source_spec_manual_desc_col",
                        manual_type_key="source_spec_manual_type_col",
                        manual_sample_key="source_spec_manual_sample_col",
                        detected_caption_prefix="Source file looks like a field specification",
                        missing_detection_message="Auto-detection found no matching column headers. Enter the column names from your spec file manually.",
                        apply_button_label="Use suggested source spec headers",
                        applied_message="Applied suggested source spec headers. Review or override them before uploading.",
                        name_label="Name column",
                        description_label="Description column",
                        type_label="Type column",
                        sample_label="Sample values column",
                    )

        target_mode = "data"
        if target_file is not None:
            if target_is_sql:
                st.info("Target .sql upload is always treated as a schema snapshot.")
            else:
                target_mode = st.radio(
                    "Target mode",
                    options=["Row data", "Schema spec"],
                    index=1 if target_spec_hint else 0,
                    horizontal=True,
                    key="target_upload_mode",
                )
                if target_spec_hint:
                    _render_spec_detection_or_recovery(
                        uploaded_file=target_file,
                        cache_key="target",
                        detected_hint=target_spec_hint,
                        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                        manual_name_key="target_spec_manual_name_col",
                        manual_desc_key="target_spec_manual_desc_col",
                        manual_type_key="target_spec_manual_type_col",
                        manual_sample_key="target_spec_manual_sample_col",
                        detected_caption_prefix="Target file looks like a field specification",
                        missing_detection_message="Auto-detection found no matching column headers. Enter the column names from your spec file manually.",
                        apply_button_label="Use suggested target spec headers",
                        applied_message="Applied suggested target spec headers. Review or override them before uploading.",
                        name_label="Name column",
                        description_label="Description column",
                        type_label="Type column",
                        sample_label="Sample values column",
                    )
                elif target_mode == "Schema spec":
                    _render_spec_detection_or_recovery(
                        uploaded_file=target_file,
                        cache_key="target",
                        detected_hint=None,
                        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                        manual_name_key="target_spec_manual_name_col",
                        manual_desc_key="target_spec_manual_desc_col",
                        manual_type_key="target_spec_manual_type_col",
                        manual_sample_key="target_spec_manual_sample_col",
                        detected_caption_prefix="Target file looks like a field specification",
                        missing_detection_message="Auto-detection found no matching column headers. Enter the column names from your spec file manually.",
                        apply_button_label="Use suggested target spec headers",
                        applied_message="Applied suggested target spec headers. Review or override them before uploading.",
                        name_label="Name column",
                        description_label="Description column",
                        type_label="Type column",
                        sample_label="Sample values column",
                    )

        st.subheader("4. Select Tables")
        if inspection_error:
            st.error(f"Upload inspection failed: {inspection_error}")

        source_table = None
        if should_show_table_selector(source_tables, source_mode, is_sql=source_is_sql):
            source_table = st.selectbox("Source table", source_tables, key="source_table")
        elif source_mode == "Schema spec":
            st.info("Source upload will be parsed as a field-per-row schema specification.")
        else:
            st.info("Source upload is row-based (CSV/JSON/XML/XLSX) or single-table SQL.")

        target_table = None
        if canonical_mode:
            active_target_intent = str(st.session_state.get("canonical_target_system") or "canonical").strip().lower() or "canonical"
            if active_target_intent == "canonical":
                st.info("Canonical mode builds a virtual target from canonical_glossary.csv when you generate mapping.")
            else:
                st.info(
                    f"Canonical mode builds a target-aware canonical projection for {active_target_intent.upper()} when you generate mapping. The canonical layer remains the source of truth."
                )
        elif should_show_table_selector(target_tables, target_mode, is_sql=target_is_sql):
            target_table = st.selectbox("Target table", target_tables, key="target_table")
        elif target_mode == "Schema spec":
            st.info("Target upload will be parsed as a field-per-row schema specification.")
        else:
            st.info("Target upload is row-based (CSV/JSON/XML/XLSX) or single-table SQL.")

        upload_disabled = source_file is None or (not canonical_mode and target_file is None)
        if st.button("Upload and profile", type="primary", disabled=upload_disabled):
            try:
                payload = {
                    "mapping_mode": "canonical" if canonical_mode else "standard",
                    "source": upload_dataset_handle(
                        source_file,
                        mode="spec" if source_mode == "Schema spec" else "data",
                        selected_table=source_table,
                        header_row_index=st.session_state.get("source_spec_header_row_index"),
                        name_col=source_spec_hint.get("name_col") if source_spec_hint else (st.session_state.get("source_spec_manual_name_col") or None),
                        description_col=source_spec_hint.get("description_col") if source_spec_hint else (st.session_state.get("source_spec_manual_desc_col") or None),
                        type_col=source_spec_hint.get("type_col") if source_spec_hint else (st.session_state.get("source_spec_manual_type_col") or None),
                        sample_values_col=source_spec_hint.get("sample_values_col") if source_spec_hint else (st.session_state.get("source_spec_manual_sample_col") or None),
                    ),
                }
                if canonical_mode:
                    payload["target_system"] = st.session_state.get("canonical_target_system", "canonical")
                else:
                    payload["target"] = upload_dataset_handle(
                        target_file,
                        mode="spec" if target_mode == "Schema spec" else "data",
                        selected_table=target_table,
                        header_row_index=st.session_state.get("target_spec_header_row_index"),
                        name_col=target_spec_hint.get("name_col") if target_spec_hint else (st.session_state.get("target_spec_manual_name_col") or None),
                        description_col=target_spec_hint.get("description_col") if target_spec_hint else (st.session_state.get("target_spec_manual_desc_col") or None),
                        type_col=target_spec_hint.get("type_col") if target_spec_hint else (st.session_state.get("target_spec_manual_type_col") or None),
                        sample_values_col=target_spec_hint.get("sample_values_col") if target_spec_hint else (st.session_state.get("target_spec_manual_sample_col") or None),
                    )
                st.session_state["upload_response"] = payload
                st.session_state.pop("source_companion_metadata_result", None)
                st.session_state.pop("target_companion_metadata_result", None)
                _reset_workspace_mapping_state(st.session_state)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": (
                        f"Uploaded source file and prepared canonical mapping context for {str(payload.get('target_system') or 'canonical').strip()}."
                        if canonical_mode
                        else "Uploaded files and built source/target schema profiles."
                    ),
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Upload failed: {error}"}
                st.rerun()

        _render_setup_saved_draft_panel(api_request)

        if upload_response:
            upload_mode = upload_response.get("mapping_mode", "standard")
            if upload_mode == "canonical":
                render_dataset_summary("Source", upload_response["source"])
                st.info("Canonical target is virtual and will be synthesized from canonical_glossary.csv during mapping generation.")
            else:
                left, right = st.columns(2)
                with left:
                    render_dataset_summary("Source", upload_response["source"])
                with right:
                    render_dataset_summary("Target", upload_response["target"])
            st.caption(_workspace_target_context_message(upload_response, mapping_response))

            st.subheader("5. Source Companion Metadata")
            st.caption(
                "Optionally attach a source-side schema/spec file to enrich the uploaded source dataset with descriptions and declared types by column name."
            )
            st.caption(
                "Expected mainly when the source was uploaded as row data and you have a separate schema/spec, "
                "or when the source was uploaded from SQL DDL and you want descriptions or sample values that are not present in the DDL."
            )
            companion_result = st.session_state.get("source_companion_metadata_result")
            if companion_result:
                st.info(companion_enrichment_message(companion_result, "Source"))

            source_companion_file = st.file_uploader(
                "Source companion schema/spec",
                type=all_upload_types,
                key="source_companion_file",
                help="Use a field-per-row schema/spec file whose column names match the uploaded source dataset.",
            )
            source_companion_hint = detect_spec_hint_for_upload(source_companion_file, "source_companion")
            if source_companion_file is not None and source_companion_hint:
                _render_spec_detection_or_recovery(
                    uploaded_file=source_companion_file,
                    cache_key="source_companion",
                    detected_hint=source_companion_hint,
                    recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                    manual_name_key="source_companion_manual_name_col",
                    manual_desc_key="source_companion_manual_desc_col",
                    manual_type_key="source_companion_manual_type_col",
                    manual_sample_key="source_companion_manual_sample_col",
                    detected_caption_prefix="Companion file looks like a field specification",
                    missing_detection_message="Auto-detection found no matching column headers in the companion file. Enter the spec header names manually.",
                    apply_button_label="Use suggested source companion headers",
                    applied_message="Applied suggested source companion spec headers. Review or override them before applying metadata.",
                    name_label="Companion name column",
                    description_label="Companion description column",
                    type_label="Companion type column",
                    sample_label="Companion sample values column",
                )
            elif source_companion_file is not None:
                _render_spec_detection_or_recovery(
                    uploaded_file=source_companion_file,
                    cache_key="source_companion",
                    detected_hint=None,
                    recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                    manual_name_key="source_companion_manual_name_col",
                    manual_desc_key="source_companion_manual_desc_col",
                    manual_type_key="source_companion_manual_type_col",
                    manual_sample_key="source_companion_manual_sample_col",
                    detected_caption_prefix="Companion file looks like a field specification",
                    missing_detection_message="Auto-detection found no matching column headers in the companion file. Enter the spec header names manually.",
                    apply_button_label="Use suggested source companion headers",
                    applied_message="Applied suggested source companion spec headers. Review or override them before applying metadata.",
                    name_label="Companion name column",
                    description_label="Companion description column",
                    type_label="Companion type column",
                    sample_label="Companion sample values column",
                )

            if st.button("Apply source companion metadata", key="apply_source_companion_metadata"):
                try:
                    enrichment_result = enrich_dataset_metadata(
                        upload_response["source"]["dataset_id"],
                        source_companion_file,
                        header_row_index=st.session_state.get("source_companion_spec_header_row_index"),
                        name_col=(source_companion_hint.get("name_col") if source_companion_hint else (st.session_state.get("source_companion_manual_name_col") or None)),
                        description_col=(source_companion_hint.get("description_col") if source_companion_hint else (st.session_state.get("source_companion_manual_desc_col") or None)),
                        type_col=(source_companion_hint.get("type_col") if source_companion_hint else (st.session_state.get("source_companion_manual_type_col") or None)),
                        sample_values_col=(source_companion_hint.get("sample_values_col") if source_companion_hint else (st.session_state.get("source_companion_manual_sample_col") or None)),
                    )
                    st.session_state["upload_response"]["source"] = enrichment_result["dataset"]
                    st.session_state["source_companion_metadata_result"] = {
                        "matched_columns": enrichment_result.get("matched_columns", 0),
                        "unmatched_columns": enrichment_result.get("unmatched_columns", []),
                    }
                    _reset_workspace_mapping_state(st.session_state)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": companion_enrichment_message(st.session_state["source_companion_metadata_result"], "Source")
                        + " Re-run mapping to use the enriched source metadata.",
                    }
                    st.rerun()
                except (ValueError, httpx.HTTPError) as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Source companion metadata failed: {error}",
                    }
                    st.rerun()

            if upload_mode != "canonical":
                st.subheader("6. Target Companion Metadata")
                st.caption(
                    "Optionally attach a target-side schema/spec file to enrich the uploaded target dataset with descriptions and declared types by column name."
                )
                st.caption(
                    "Use this when both source and target were uploaded as row data and the target meanings live in a separate schema/spec, "
                    "or when the target came from SQL DDL and you want richer business descriptions than the DDL contains."
                )
                target_companion_result = st.session_state.get("target_companion_metadata_result")
                if target_companion_result:
                    st.info(companion_enrichment_message(target_companion_result, "Target"))

                target_companion_file = st.file_uploader(
                    "Target companion schema/spec",
                    type=all_upload_types,
                    key="target_companion_file",
                    help="Use a field-per-row schema/spec file whose column names match the uploaded target dataset.",
                )
                target_companion_hint = detect_spec_hint_for_upload(target_companion_file, "target_companion")
                if target_companion_file is not None and target_companion_hint:
                    _render_spec_detection_or_recovery(
                        uploaded_file=target_companion_file,
                        cache_key="target_companion",
                        detected_hint=target_companion_hint,
                        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                        manual_name_key="target_companion_manual_name_col",
                        manual_desc_key="target_companion_manual_desc_col",
                        manual_type_key="target_companion_manual_type_col",
                        manual_sample_key="target_companion_manual_sample_col",
                        detected_caption_prefix="Companion file looks like a field specification",
                        missing_detection_message="Auto-detection found no matching column headers in the companion file. Enter the spec header names manually.",
                        apply_button_label="Use suggested target companion headers",
                        applied_message="Applied suggested target companion spec headers. Review or override them before applying metadata.",
                        name_label="Target companion name column",
                        description_label="Target companion description column",
                        type_label="Target companion type column",
                        sample_label="Target companion sample values column",
                    )
                elif target_companion_file is not None:
                    _render_spec_detection_or_recovery(
                        uploaded_file=target_companion_file,
                        cache_key="target_companion",
                        detected_hint=None,
                        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
                        manual_name_key="target_companion_manual_name_col",
                        manual_desc_key="target_companion_manual_desc_col",
                        manual_type_key="target_companion_manual_type_col",
                        manual_sample_key="target_companion_manual_sample_col",
                        detected_caption_prefix="Companion file looks like a field specification",
                        missing_detection_message="Auto-detection found no matching column headers in the companion file. Enter the spec header names manually.",
                        apply_button_label="Use suggested target companion headers",
                        applied_message="Applied suggested target companion spec headers. Review or override them before applying metadata.",
                        name_label="Target companion name column",
                        description_label="Target companion description column",
                        type_label="Target companion type column",
                        sample_label="Target companion sample values column",
                    )

                if st.button("Apply target companion metadata", key="apply_target_companion_metadata"):
                    try:
                        enrichment_result = enrich_dataset_metadata(
                            upload_response["target"]["dataset_id"],
                            target_companion_file,
                            header_row_index=st.session_state.get("target_companion_spec_header_row_index"),
                            name_col=(target_companion_hint.get("name_col") if target_companion_hint else (st.session_state.get("target_companion_manual_name_col") or None)),
                            description_col=(target_companion_hint.get("description_col") if target_companion_hint else (st.session_state.get("target_companion_manual_desc_col") or None)),
                            type_col=(target_companion_hint.get("type_col") if target_companion_hint else (st.session_state.get("target_companion_manual_type_col") or None)),
                            sample_values_col=(target_companion_hint.get("sample_values_col") if target_companion_hint else (st.session_state.get("target_companion_manual_sample_col") or None)),
                        )
                        st.session_state["upload_response"]["target"] = enrichment_result["dataset"]
                        st.session_state["target_companion_metadata_result"] = {
                            "matched_columns": enrichment_result.get("matched_columns", 0),
                            "unmatched_columns": enrichment_result.get("unmatched_columns", []),
                        }
                        _reset_workspace_mapping_state(st.session_state)
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": companion_enrichment_message(st.session_state["target_companion_metadata_result"], "Target")
                            + " Re-run mapping to use the enriched target metadata.",
                        }
                        st.rerun()
                    except (ValueError, httpx.HTTPError) as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Target companion metadata failed: {error}",
                        }
                        st.rerun()

            st.subheader("7. Review Mapping")
            use_llm = st.checkbox(
                "Use LLM validation",
                value=default_llm_validation_enabled(st.session_state),
                key="use_llm_validation",
                help=(
                    "When enabled, Semantra calls the configured LLM provider for fields in the ambiguity band. "
                    "Disable this if no LLM is running locally to avoid timeouts."
                ),
            )
            description_priority = st.checkbox(
                "Prioritize source descriptions",
                value=bool(st.session_state.get("use_description_priority", False)),
                key="use_description_priority",
                help=(
                    "When enabled, Semantra gives extra weight to source description/type metadata during heuristic "
                    "matching. Useful for unfamiliar systems with technical field names."
                ),
            )
            canonical_candidate_pool_size = None
            if upload_mode == "canonical":
                canonical_candidate_pool_size = int(
                    st.number_input(
                        "Canonical candidate pool size",
                        min_value=1,
                        max_value=25,
                        value=int(st.session_state.get("canonical_candidate_pool_size", 10)),
                        step=1,
                        key="canonical_candidate_pool_size",
                        help=(
                            "Shortlists the most likely canonical concepts per source field before full scoring. "
                            "Lower values run faster but can miss edge-case matches."
                        ),
                    )
                )
            button_label = "Generate canonical mapping" if upload_mode == "canonical" else "Generate mapping"
            button_key = "generate_canonical_mapping" if upload_mode == "canonical" else "generate_mapping"
            activity_label = "Canonical mapping activity" if upload_mode == "canonical" else "Mapping activity"
            activity_placeholder = st.empty()

            def _apply_mapping_response(mapping_response_payload: dict) -> None:
                st.session_state["mapping_response"] = mapping_response_payload
                st.session_state.pop("mapping_analysis_summary", None)
                st.session_state.pop("mapping_analysis_error", None)
                st.session_state.pop("mapping_analysis_spoken_script", None)
                st.session_state.pop("mapping_analysis_audio_bytes", None)
                st.session_state.pop("mapping_analysis_audio_mime_type", None)
                st.session_state.pop("mapping_analysis_audio_error", None)
                st.session_state.pop("review_plan_summary", None)
                st.session_state.pop("review_plan_error", None)
                st.session_state.pop("canonical_gap_candidates", None)
                st.session_state.pop("canonical_gap_suggestions", None)
                st.session_state.pop("canonical_gap_triage_summary", None)
                st.session_state.pop("canonical_gap_triage_error", None)
                initialize_mapping_editor_state(mapping_response_payload)
                st.session_state.pop("preview_response", None)
                st.session_state.pop("codegen_response", None)
                st.session_state.pop("codegen_refinement_response", None)
                _workspace_reset_transformation_design_state(st.session_state)
                _clear_active_mapping_job()

            active_mapping_job = st.session_state.get("active_mapping_job") or {}
            active_job_id = str(active_mapping_job.get("job_id") or "").strip()
            if active_job_id:
                st.caption(f"Tracked background mapping job: {active_job_id}")
                if st.button("Resume current mapping job", key="resume_mapping_job", width="stretch"):
                    try:
                        with activity_placeholder.container():
                            with st.status(activity_label, expanded=True) as status:
                                status.write("Re-attaching to existing mapping job.")
                                mapping_response = poll_mapping_job(
                                    api_request=api_request,
                                    start_path=str(active_mapping_job.get("start_path") or ""),
                                    payload=active_mapping_job.get("payload") or {},
                                    status=status,
                                    existing_job_id=active_job_id,
                                )
                                status.write("Initializing review state.")
                                _apply_mapping_response(mapping_response)
                                st.session_state["last_action"] = {
                                    "level": "success",
                                    "message": "Recovered mapping results from the active background job.",
                                }
                                status.write("Mapping results are ready for review.")
                                status.update(label=f"{activity_label} complete", state="complete", expanded=True)
                    except (httpx.HTTPError, RuntimeError) as error:
                        with activity_placeholder.container():
                            with st.status(activity_label, expanded=True) as status:
                                status.write("Re-attaching to existing mapping job.")
                                status.write(f"Request failed: {error}")
                                status.update(label=f"{activity_label} failed", state="error", expanded=True)
                        st.session_state["last_action"] = {"level": "error", "message": f"Mapping failed: {error}"}

            if st.button(button_label, type="primary", key=button_key):
                try:
                    with activity_placeholder.container():
                        with st.status(activity_label, expanded=True) as status:
                            status.write("Preparing mapping request.")
                            if upload_mode == "canonical":
                                status.write("Starting /mapping/canonical job.")
                                mapping_response = poll_mapping_job(
                                    api_request=api_request,
                                    start_path="/mapping/canonical/jobs",
                                    payload={
                                        "source_dataset_id": upload_response["source"]["dataset_id"],
                                        "target_system": upload_response.get("target_system", "canonical"),
                                        "use_llm": use_llm,
                                        "description_priority": description_priority,
                                        "candidate_pool_size": canonical_candidate_pool_size,
                                        **current_workspace_scope(),
                                    },
                                    status=status,
                                )
                            else:
                                status.write("Starting /mapping/auto job.")
                                mapping_response = poll_mapping_job(
                                    api_request=api_request,
                                    start_path="/mapping/auto/jobs",
                                    payload={
                                        "source_dataset_id": upload_response["source"]["dataset_id"],
                                        "target_dataset_id": upload_response["target"]["dataset_id"],
                                        "use_llm": use_llm,
                                        "description_priority": description_priority,
                                        **current_workspace_scope(),
                                    },
                                    status=status,
                                )
                            status.write("Initializing review state.")
                            _apply_mapping_response(mapping_response)
                            st.session_state["last_action"] = {
                                "level": "success",
                                "message": (
                                    "Generated canonical mapping candidates from the current source dataset."
                                    if upload_mode == "canonical"
                                    else "Generated ranked mapping candidates from the current datasets."
                                ),
                            }
                            status.write("Mapping results are ready for review.")
                            status.update(label=f"{activity_label} complete", state="complete", expanded=True)
                except (httpx.HTTPError, RuntimeError) as error:
                    with activity_placeholder.container():
                        with st.status(activity_label, expanded=True) as status:
                            status.write("Preparing mapping request.")
                            status.write(f"Request failed: {error}")
                            status.update(label=f"{activity_label} failed", state="error", expanded=True)
                    st.session_state["last_action"] = {"level": "error", "message": f"Mapping failed: {error}"}

            if mapping_response:
                st.success(
                    "\u2705 Mapping is ready \u2013 switch to the **Review** tab to inspect trust scores and candidates, "
                    "or **Decisions** to manage overrides and export."
                )
                runtime = mapping_response.get("mapping_runtime") or {}
                if runtime.get("code_fingerprint"):
                    st.info(
                        "Mapping runtime: "
                        f"build={runtime.get('code_fingerprint')} | "
                        f"profile={runtime.get('scoring_profile') or 'n/a'} | "
                        f"description_priority={'on' if runtime.get('description_priority') else 'off'}"
                    )
                    st.caption(_workspace_target_context_message(upload_response, mapping_response))
                else:
                    st.warning(
                        "This mapping result does not include a runtime fingerprint. "
                        "Generate a fresh mapping result after restarting the backend; resuming an older job or reviewing an older cached result will not show build=."
                    )
        else:
            if canonical_mode:
                st.info("Upload and profile the source dataset to unlock canonical review and decision export.")
            else:
                st.info("Upload and profile both datasets to unlock review, decision, and output sections.")

    if selected_workspace_section == "Review":
        if mapping_response:
            st.caption(_workspace_target_context_message(upload_response, mapping_response))
            if (upload_response or {}).get("mapping_mode") == "canonical":
                st.caption("Canonical-only review treats canonical concept IDs as virtual targets built from the glossary.")
            display_trust_layer(mapping_response)
            render_mapping_analysis_panel(mapping_response)
            render_mapping_review(mapping_response)
            render_active_draft_review_state_panel()
            render_mapping_editor(mapping_response)
            render_canonical_gap_assistant(mapping_response)
            render_canonical_concept_summary(mapping_response)
        else:
            if (upload_response or {}).get("mapping_mode") == "canonical":
                st.info("Generate canonical mapping in Setup to populate trust, candidate review, and manual review controls.")
            else:
                st.info("Generate mapping in Setup to populate trust, candidate review, and manual review controls.")

    if selected_workspace_section == "Decisions":
        if mapping_response:
            st.caption(_workspace_target_context_message(upload_response, mapping_response))
            render_mapping_decision_summary()
            render_manual_mapping_panel(mapping_response)
            render_active_draft_decision_state_panel()
            render_mapping_io_panel()
            render_mapping_set_versions_panel()
            if (upload_response or {}).get("mapping_mode") != "canonical":
                render_correction_panel()
            else:
                st.info(
                    "Canonical-only mode still keeps correction workflows disabled until a real target dataset exists, "
                    "but manual source-to-canonical overrides are available here."
                )
        else:
            st.info("Generate mapping in Setup before managing manual overrides, imports, mapping sets, or corrections.")

    if selected_workspace_section == "Output":
        if mapping_response:
            st.caption(_workspace_target_context_message(upload_response, mapping_response))
            canonical_output_mode = (upload_response or {}).get("mapping_mode") == "canonical"
            mapping_decisions = build_mapping_decisions()
            preview_context_block_reason = _workspace_preview_context_block_reason(upload_response)
            if canonical_output_mode:
                st.caption(
                    "Canonical mode supports code generation against canonical concept IDs, but preview stays unavailable because there is no concrete target dataset to materialize against."
                )
            _render_workspace_transformation_design(mapping_decisions, api_request=api_request)
            st.subheader("Artifact Generation")
            codegen_mode = st.radio(
                "Artifact format",
                options=list(WORKSPACE_CODEGEN_MODES),
                index=(
                    WORKSPACE_CODEGEN_MODES.index(st.session_state.get("output_codegen_mode", "pandas"))
                    if st.session_state.get("output_codegen_mode", "pandas") in WORKSPACE_CODEGEN_MODES
                    else 0
                ),
                key="output_codegen_mode",
                horizontal=True,
                format_func=_workspace_codegen_format_label,
            )
            codegen_block_reason = _workspace_codegen_block_reason(
                mapping_decisions,
                codegen_mode,
                allow_unaccepted=canonical_output_mode,
            )
            preview_advisory_message = _workspace_preview_advisory_message(mapping_decisions)
            actions_left, actions_right = st.columns(2)
            with actions_left:
                if canonical_output_mode:
                    st.info(
                        "Preview is unavailable in canonical mode. Use code generation to produce Pandas, PySpark, or dbt scaffolding against canonical targets."
                    )
                else:
                    if st.button("Generate preview", disabled=bool(preview_context_block_reason)):
                        if not mapping_decisions:
                            st.session_state["last_action"] = {
                                "level": "warning",
                                "message": "Add at least one active mapping before generating preview.",
                            }
                            st.rerun()
                        try:
                            ready_transformation_spec = _workspace_ready_transformation_spec(mapping_decisions, st.session_state)
                            st.session_state["preview_response"] = api_request(
                                "POST",
                                "/mapping/preview",
                                json={
                                    "source_dataset_id": st.session_state["upload_response"]["source"]["dataset_id"],
                                    "source_preview_rows": list(
                                        st.session_state["upload_response"]["source"].get("preview_rows") or []
                                    ),
                                    "mapping_decisions": mapping_decisions,
                                    "transformation_spec": ready_transformation_spec,
                                },
                            )
                            st.session_state["last_action"] = {
                                "level": "success",
                                "message": "Generated preview rows for the active mapping decisions.",
                            }
                            st.rerun()
                        except httpx.HTTPError as error:
                            st.session_state["last_action"] = {
                                "level": "error",
                                "message": api_error_message(error, default_prefix="Preview failed"),
                            }
                            st.rerun()
                    if preview_context_block_reason:
                        st.caption(preview_context_block_reason)
                    elif preview_advisory_message:
                        st.caption(preview_advisory_message)
            with actions_right:
                if st.button(_workspace_codegen_button_label(codegen_mode), disabled=bool(codegen_block_reason)):
                    if not mapping_decisions:
                        st.session_state["last_action"] = {
                            "level": "warning",
                            "message": "Add at least one active mapping before generating code.",
                        }
                        st.rerun()
                    try:
                        ready_transformation_spec = _workspace_ready_transformation_spec(mapping_decisions, st.session_state)
                        st.session_state["codegen_response"] = api_request(
                            "POST",
                            "/mapping/codegen",
                            json={
                                "mapping_decisions": mapping_decisions,
                                "mode": codegen_mode,
                                "allow_unaccepted": canonical_output_mode,
                                "transformation_spec": ready_transformation_spec,
                            },
                        )
                        st.session_state.pop("codegen_refinement_response", None)
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Generated {_workspace_codegen_action_label(codegen_mode).lower()} from the active mapping decisions.",
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": api_error_message(error, default_prefix="Code generation failed"),
                        }
                        st.rerun()
                if codegen_block_reason:
                    st.caption(codegen_block_reason)
        else:
            st.info("Generate mapping in Setup before preview or code generation.")

        if preview_response is not None:
            preview_rows = [row["values"] for row in preview_response["preview"]]
            unresolved_targets = preview_response.get("unresolved_targets") or []
            transformation_previews = preview_response.get("transformation_previews") or []
            preview_detail = f"{len(preview_rows)} rows"
            if unresolved_targets:
                preview_detail += f", {len(unresolved_targets)} unresolved"
            with st.expander(_workspace_output_section_label("Preview Result", preview_detail), expanded=True):
                preview_spec_summary = preview_response.get("transformation_spec_summary") or {}
                preview_spec_caption = _workspace_transformation_summary_caption(preview_spec_summary)
                if preview_spec_caption:
                    st.caption(preview_spec_caption)
                if preview_rows:
                    st.dataframe(preview_rows, width="stretch", hide_index=True)
                else:
                    st.info("Preview is empty. This is expected for schema-only SQL uploads.")
                if unresolved_targets:
                    st.warning(f"Needs review: {', '.join(unresolved_targets)}")
                if transformation_previews:
                    st.caption("Transformation validation")
                    st.dataframe(
                        [
                            {
                                "source": item.get("source"),
                                "target": item.get("target"),
                                "classification": item.get("classification"),
                                "mode": item.get("mode"),
                                "status": item.get("status"),
                                "warning_codes": " | ".join(warning.get("code", "") for warning in item.get("warnings", [])),
                                "warning_count": len(item.get("warnings", [])),
                            }
                            for item in transformation_previews
                        ],
                        width="stretch",
                        hide_index=True,
                    )
                    for item in transformation_previews:
                        with st.expander(f"Transformation details: {item.get('source')} -> {item.get('target')}"):
                            st.caption(
                                f"Classification: {item.get('classification')} | Mode: {item.get('mode')} | Status: {item.get('status')}"
                            )
                            st.write("Before samples:", item.get("before_samples", []))
                            st.write("After samples:", item.get("after_samples", []))
                            warnings = item.get("warnings", [])
                            if warnings:
                                for warning in warnings:
                                    st.warning(f"{warning.get('code')}: {warning.get('message')}")

        if codegen_response is not None:
            warnings = codegen_response.get("warnings") or []
            artifact_header = _workspace_generated_artifact_header(codegen_response.get("language"))
            artifact_detail = codegen_response.get("language") or "python"
            if warnings:
                artifact_detail = f"{artifact_detail}, {len(warnings)} warnings"
            if codegen_refinement_response is not None:
                artifact_detail = f"{artifact_detail}, refinement pending"
            with st.expander(_workspace_output_section_label(artifact_header, artifact_detail), expanded=True):
                codegen_spec_summary = codegen_response.get("transformation_spec_summary") or {}
                codegen_spec_caption = _workspace_transformation_summary_caption(codegen_spec_summary)
                if codegen_spec_caption:
                    st.caption(codegen_spec_caption)
                original_col, refined_col = st.columns(2)
                with original_col:
                    st.caption("Original generated code")
                    st.code(
                        codegen_response["code"],
                        language=_workspace_generated_artifact_code_language(codegen_response.get("language")),
                    )
                    if warnings:
                        for warning in warnings:
                            if isinstance(warning, dict):
                                prefix = warning.get("code") or "warning"
                                details = warning.get("details") or {}
                                suffix = ""
                                if details.get("line") is not None and details.get("column") is not None:
                                    suffix = f" (line {details['line']}, col {details['column']})"
                                st.warning(f"{prefix}: {warning.get('message', '')}{suffix}")
                            else:
                                st.warning(str(warning))
                with refined_col:
                    st.caption("Refined code")
                    if codegen_refinement_response is not None:
                        st.code(
                            codegen_refinement_response["code"],
                            language=_workspace_generated_artifact_code_language(codegen_refinement_response.get("language")),
                        )
                        reasoning = codegen_refinement_response.get("reasoning") or []
                        if reasoning:
                            st.caption("Refinement reasoning")
                            for line in reasoning:
                                st.write(f"- {line}")
                        refinement_warnings = codegen_refinement_response.get("warnings") or []
                        if refinement_warnings:
                            for warning in refinement_warnings:
                                if isinstance(warning, dict):
                                    prefix = warning.get("code") or "warning"
                                    details = warning.get("details") or {}
                                    suffix = ""
                                    if details.get("line") is not None and details.get("column") is not None:
                                        suffix = f" (line {details['line']}, col {details['column']})"
                                    st.warning(f"{prefix}: {warning.get('message', '')}{suffix}")
                                else:
                                    st.warning(str(warning))
                    else:
                        st.info("Refined version will appear here after you run Refine with LLM.")

                if codegen_refinement_response is not None:
                    accept_col, discard_col = st.columns(2)
                    with accept_col:
                        if st.button("Accept refined version", key="output_accept_refinement"):
                            st.session_state["codegen_response"] = codegen_refinement_response
                            st.session_state.pop("codegen_refinement_response", None)
                            st.session_state["last_action"] = {
                                "level": "success",
                                "message": "Accepted the refined artifact as the current generated code.",
                            }
                            st.rerun()
                    with discard_col:
                        if st.button("Discard refinement", key="output_discard_refinement"):
                            st.session_state.pop("codegen_refinement_response", None)
                            st.session_state["last_action"] = {
                                "level": "success",
                                "message": "Discarded the pending refinement and kept the original generated code.",
                            }
                            st.rerun()

                st.divider()
                st.caption("Refine generated code")
                refinement_instruction = st.text_area(
                    "What should change?",
                    key="output_refinement_instruction",
                    placeholder="Example: Preserve the current scaffold, but normalize phone_number, trim emails, and keep null-safe behavior.",
                )
                refinement_edge_cases = st.text_area(
                    "Business rules / edge cases",
                    key="output_refinement_edge_cases",
                    placeholder="Example: Empty strings should stay null; phone values may start with +381 or 06; emails should be lowercase.",
                )
                refinement_reference = st.text_area(
                    "Reference excerpt",
                    key="output_refinement_reference",
                    placeholder="Paste a short excerpt from a spec, mapping note, or business rule document.",
                )
                if st.button(
                    "Refine with LLM",
                    key="output_refine_codegen",
                    disabled=(not _workspace_llm_refinement_enabled())
                    or (
                        not str((_workspace_refinement_source_response(codegen_response, codegen_refinement_response) or {}).get("code", "")).strip()
                    ),
                ):
                    if not refinement_instruction.strip():
                        st.session_state["last_action"] = {
                            "level": "warning",
                            "message": "Describe what should change before refining the generated artifact.",
                        }
                        st.rerun()
                    try:
                        refinement_source = _workspace_refinement_source_response(codegen_response, codegen_refinement_response) or {}
                        st.session_state["codegen_refinement_response"] = api_request(
                            "POST",
                            "/mapping/codegen/refine",
                            json={
                                "mapping_decisions": build_mapping_decisions(),
                                "mode": "pyspark" if refinement_source.get("language") == "python-pyspark" else "dbt" if refinement_source.get("language") == "sql-dbt" else "pandas",
                                "allow_unaccepted": canonical_output_mode,
                                "current_code": refinement_source["code"],
                                "instruction": refinement_instruction.strip(),
                                "edge_cases": refinement_edge_cases.strip(),
                                "reference_excerpt": refinement_reference.strip(),
                            },
                            timeout=90.0,
                        )
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": "Generated a refinement candidate from the provided instructions.",
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": api_error_message(error, default_prefix="Artifact refinement failed"),
                        }
                        st.rerun()
                if not _workspace_llm_refinement_enabled():
                    st.caption("LLM refinement is unavailable until a reachable runtime provider is configured.")


def render_workspace_tab(
    *,
    all_upload_types,
    detect_spec_hint_for_upload,
    recover_spec_hint_for_upload,
    sql_tables_for_upload,
    api_request,
    upload_dataset_handle,
    enrich_dataset_metadata,
    uploaded_file_bytes,
    render_dataset_summary,
    initialize_mapping_editor_state,
    render_mapping_analysis_panel,
    display_trust_layer,
    render_mapping_review,
    render_mapping_editor,
    render_canonical_gap_assistant,
    render_canonical_concept_summary,
    render_active_draft_review_state_panel,
    render_active_draft_decision_state_panel,
    render_manual_mapping_panel,
    render_mapping_decision_summary,
    render_mapping_io_panel,
    render_mapping_set_versions_panel,
    render_correction_panel,
    build_mapping_decisions,
    request_mapping_analysis_summary,
) -> None:
    """Render the full Workspace surface from setup through review, decisions, and output."""

    resolve_active_workspace_section(st.session_state)
    selected_workspace_section = st.radio(
        "Workspace section",
        WORKSPACE_SECTIONS,
        key="active_workspace_section",
        horizontal=True,
        label_visibility="collapsed",
    )

    active_mapping_mode = st.session_state.get("mapping_mode", "Standard")
    source_file = _workspace_uploaded_file_or_none(st.session_state.get("source_file"))
    target_file = _workspace_uploaded_file_or_none(st.session_state.get("target_file")) if active_mapping_mode == "Standard" else None
    source_tables: list[str] = []
    target_tables: list[str] = []
    source_spec_hint = None
    target_spec_hint = None
    inspection_error = None
    if source_file is not None or target_file is not None:
        try:
            source_tables = sql_tables_for_upload(source_file, "source")
            target_tables = sql_tables_for_upload(target_file, "target")
            source_spec_hint = detect_spec_hint_for_upload(source_file, "source")
            target_spec_hint = detect_spec_hint_for_upload(target_file, "target")
        except httpx.HTTPError as error:
            inspection_error = str(error)

    upload_response = st.session_state.get("upload_response")
    mapping_response = st.session_state.get("mapping_response")
    preview_response = st.session_state.get("preview_response")
    codegen_response = st.session_state.get("codegen_response")
    codegen_refinement_response = st.session_state.get("codegen_refinement_response")
    _render_workspace_section_content(
        selected_workspace_section=selected_workspace_section,
        all_upload_types=all_upload_types,
        detect_spec_hint_for_upload=detect_spec_hint_for_upload,
        recover_spec_hint_for_upload=recover_spec_hint_for_upload,
        api_request=api_request,
        upload_dataset_handle=upload_dataset_handle,
        enrich_dataset_metadata=enrich_dataset_metadata,
        render_dataset_summary=render_dataset_summary,
        initialize_mapping_editor_state=initialize_mapping_editor_state,
        render_mapping_analysis_panel=render_mapping_analysis_panel,
        display_trust_layer=display_trust_layer,
        render_mapping_review=render_mapping_review,
        render_mapping_editor=render_mapping_editor,
        render_canonical_gap_assistant=render_canonical_gap_assistant,
        render_canonical_concept_summary=render_canonical_concept_summary,
        render_active_draft_review_state_panel=render_active_draft_review_state_panel,
        render_active_draft_decision_state_panel=render_active_draft_decision_state_panel,
        render_manual_mapping_panel=render_manual_mapping_panel,
        render_mapping_decision_summary=render_mapping_decision_summary,
        render_mapping_io_panel=render_mapping_io_panel,
        render_mapping_set_versions_panel=render_mapping_set_versions_panel,
        render_correction_panel=render_correction_panel,
        build_mapping_decisions=build_mapping_decisions,
        source_file=source_file,
        target_file=target_file,
        source_tables=source_tables,
        target_tables=target_tables,
        source_spec_hint=source_spec_hint,
        target_spec_hint=target_spec_hint,
        inspection_error=inspection_error,
        upload_response=upload_response,
        mapping_response=mapping_response,
        preview_response=preview_response,
        codegen_response=codegen_response,
        codegen_refinement_response=codegen_refinement_response,
    )