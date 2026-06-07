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


WORKSPACE_SECTIONS = ("Setup", "Review", "Decisions", "Output", "Modelling Overview")
WORKSPACE_CODEGEN_MODES = ("pandas", "pyspark", "dbt")
WORKSPACE_COPILOT_ACTIONS = {
    "Setup": ("What unlocks Review?",),
    "Review": ("Summarize current mapping state", "Summarize Review -> Decisions risks"),
    "Decisions": ("What still needs a decision?", "Am I ready for Output?"),
    "Output": ("Why is codegen blocked?", "Explain output gating and warning priority"),
}
WORKSPACE_MODELLING_RESOLUTION_LABELS = {
    "direct_mapping": "Direct mapping",
    "fixed_value": "Fixed value",
    "derived_value": "Derived value",
    "target_managed": "Target managed",
    "out_of_scope": "N/A",
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


def _workspace_modelling_parse_lines(value: object) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for raw_line in str(value or "").splitlines():
        item = raw_line.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _workspace_modelling_group_label(attribute_name: object) -> str:
    normalized = str(attribute_name or "").strip().lower()
    if not normalized:
        return "General"
    if any(token in normalized for token in ("id", "code", "key", "number", "identifier")):
        return "Identity"
    if any(token in normalized for token in ("status", "state", "flag", "type", "category", "segment")):
        return "Classification"
    if any(token in normalized for token in ("date", "time", "timestamp", "created", "updated")):
        return "Dates"
    if any(token in normalized for token in ("phone", "email", "address", "street", "city", "country", "contact")):
        return "Contact"
    if any(token in normalized for token in ("amount", "total", "balance", "price", "cost", "currency", "credit", "debit")):
        return "Financials"
    if any(token in normalized for token in ("parent", "child", "manager", "owner", "reference")):
        return "References"
    return "General"


def _workspace_modelling_resolution_label(value: object) -> str:
    normalized = str(value or "direct_mapping").strip().lower() or "direct_mapping"
    return WORKSPACE_MODELLING_RESOLUTION_LABELS.get(normalized, normalized.replace("_", " ").title())


def _workspace_modelling_inferred_targets(mapping_decisions: list[dict], session_state: dict) -> list[str]:
    targets: list[str] = []
    seen: set[str] = set()
    for item in mapping_decisions:
        target = str(item.get("target") or "").strip()
        if not target or target in seen:
            continue
        seen.add(target)
        targets.append(target)
    for key in session_state.keys():
        key_text = str(key)
        if not key_text.startswith("workspace_transformation_rule::"):
            continue
        target = key_text.split("::", 1)[1].strip()
        if not target or target in seen:
            continue
        seen.add(target)
        targets.append(target)
    return targets


def _workspace_modelling_object_name(upload_response: dict | None, session_state: dict) -> str:
    upload_payload = upload_response or {}
    mapping_mode = str(upload_payload.get("mapping_mode") or session_state.get("mapping_mode") or "standard").strip().lower()
    if mapping_mode == "canonical":
        canonical_target = str(
            session_state.get("canonical_target_intent")
            or session_state.get("canonical_target_profile")
            or upload_payload.get("target_intent_label")
            or upload_payload.get("target_profile")
            or ""
        ).strip()
        return canonical_target or "Canonical target model"
    target_payload = upload_payload.get("target") if isinstance(upload_payload.get("target"), dict) else {}
    for key in ("dataset_name", "name", "file_name", "filename"):
        value = str(target_payload.get(key) or "").strip()
        if value:
            return value.rsplit(".", 1)[0]
    return "Target model"


def _workspace_build_inferred_concept_model(
    mapping_decisions: list[dict],
    session_state: dict,
    upload_response: dict | None = None,
) -> dict:
    inferred_targets = _workspace_modelling_inferred_targets(mapping_decisions, session_state)
    decisions_by_target: dict[str, list[dict]] = {}
    for item in mapping_decisions:
        target = str(item.get("target") or "").strip()
        if not target:
            continue
        decisions_by_target.setdefault(target, []).append(item)

    business_rules = _workspace_modelling_parse_lines(
        "\n".join(
            value
            for value in (
                str(session_state.get("workspace_transformation_global_rules") or "").strip(),
                str(session_state.get("workspace_transformation_defaults") or "").strip(),
                str(session_state.get("workspace_transformation_examples") or "").strip(),
            )
            if value
        )
    )
    attributes: list[dict] = []
    concept_groups: list[dict] = []
    seen_groups: set[str] = set()
    for target in inferred_targets:
        target_decisions = decisions_by_target.get(target, [])
        statuses = [str(item.get("status") or "needs_review").strip().lower() or "needs_review" for item in target_decisions]
        resolution_types = [
            str(item.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
            for item in target_decisions
        ]
        resolution_type = resolution_types[0] if resolution_types else "direct_mapping"
        if "target_managed" in resolution_types:
            coverage_status = "target_managed"
        elif "out_of_scope" in resolution_types:
            coverage_status = "excluded"
        elif not target_decisions:
            coverage_status = "modeled_only"
        elif "accepted" in statuses:
            coverage_status = "mapped"
        else:
            coverage_status = "unresolved"
        group_label = _workspace_modelling_group_label(target)
        if group_label not in seen_groups:
            seen_groups.add(group_label)
            concept_groups.append({"id": group_label.lower().replace(" ", "_"), "label": group_label})
        attributes.append(
            {
                "name": target,
                "group": group_label,
                "required": False,
                "expected_resolution_type": resolution_type,
                "mapped_target": target,
                "current_mapping_status": " / ".join(sorted(set(statuses))) if statuses else "unmapped",
                "coverage_status": coverage_status,
                "origin": "inferred",
                "notes": "",
            }
        )

    return {
        "source_mode": "derived_from_workspace",
        "source_snapshot": {
            "mapping_decision_count": len(mapping_decisions),
            "transformation_spec_present": bool(str(session_state.get("workspace_transformation_target_grain") or "").strip()),
        },
        "object_name": _workspace_modelling_object_name(upload_response, session_state),
        "description": "",
        "business_purpose": "",
        "target_grain": str(session_state.get("workspace_transformation_target_grain") or "").strip(),
        "concept_groups": concept_groups,
        "attributes": attributes,
        "relationships": [],
        "business_rules": business_rules,
    }


def _workspace_seed_modelling_editor_state(concept_model: dict, session_state: dict, *, force: bool = False) -> None:
    defaults = {
        "workspace_modelling_object_name": str(concept_model.get("object_name") or "").strip(),
        "workspace_modelling_description": str(concept_model.get("description") or "").strip(),
        "workspace_modelling_business_purpose": str(concept_model.get("business_purpose") or "").strip(),
        "workspace_modelling_target_grain": str(concept_model.get("target_grain") or "").strip(),
        "workspace_modelling_additional_attributes": "",
        "workspace_modelling_required_attributes": "",
        "workspace_modelling_business_rules": "\n".join(concept_model.get("business_rules") or []),
    }
    for key, value in defaults.items():
        if force or key not in session_state:
            session_state[key] = value


def _workspace_build_concept_model(inferred_model: dict, session_state: dict) -> dict:
    concept_model = {key: value for key, value in inferred_model.items() if key != "attributes"}
    attributes = [dict(item) for item in (inferred_model.get("attributes") or []) if isinstance(item, dict)]
    required_attributes = set(_workspace_modelling_parse_lines(session_state.get("workspace_modelling_required_attributes")))
    for item in attributes:
        item["required"] = str(item.get("name") or "").strip() in required_attributes
    known_names = {str(item.get("name") or "").strip() for item in attributes}
    for attribute_name in _workspace_modelling_parse_lines(session_state.get("workspace_modelling_additional_attributes")):
        if attribute_name in known_names:
            continue
        known_names.add(attribute_name)
        attributes.append(
            {
                "name": attribute_name,
                "group": _workspace_modelling_group_label(attribute_name),
                "required": attribute_name in required_attributes,
                "expected_resolution_type": "direct_mapping",
                "mapped_target": "",
                "current_mapping_status": "unmapped",
                "coverage_status": "modeled_only",
                "origin": "user_added",
                "notes": "",
            }
        )

    concept_model.update(
        {
            "object_name": str(session_state.get("workspace_modelling_object_name") or concept_model.get("object_name") or "").strip(),
            "description": str(session_state.get("workspace_modelling_description") or concept_model.get("description") or "").strip(),
            "business_purpose": str(session_state.get("workspace_modelling_business_purpose") or concept_model.get("business_purpose") or "").strip(),
            "target_grain": str(session_state.get("workspace_modelling_target_grain") or concept_model.get("target_grain") or "").strip(),
            "attributes": attributes,
            "business_rules": _workspace_modelling_parse_lines(session_state.get("workspace_modelling_business_rules")),
        }
    )
    return concept_model


def _workspace_concept_model_drift_summary(concept_model: dict, mapping_decisions: list[dict]) -> dict:
    model_attributes = [item for item in (concept_model.get("attributes") or []) if isinstance(item, dict)]
    model_names = {str(item.get("name") or "").strip() for item in model_attributes if str(item.get("name") or "").strip()}
    active_targets = {str(item.get("target") or "").strip() for item in mapping_decisions if str(item.get("target") or "").strip()}
    resolution_by_target = {
        str(item.get("target") or "").strip(): str(item.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
        for item in mapping_decisions
        if str(item.get("target") or "").strip()
    }
    modeled_but_unmapped = sorted(name for name in model_names if name not in active_targets)
    unmodeled_targets = sorted(target for target in active_targets if target not in model_names)
    required_unresolved = sorted(
        str(item.get("name") or "").strip()
        for item in model_attributes
        if item.get("required") and str(item.get("coverage_status") or "").strip().lower() in {"modeled_only", "unresolved", "excluded"}
    )
    resolution_mismatches = sorted(
        str(item.get("name") or "").strip()
        for item in model_attributes
        if str(item.get("name") or "").strip() in resolution_by_target
        and str(item.get("expected_resolution_type") or "direct_mapping").strip().lower() != resolution_by_target[str(item.get("name") or "").strip()]
    )
    return {
        "status": "drift" if (modeled_but_unmapped or unmodeled_targets or required_unresolved or resolution_mismatches) else "in_sync",
        "modeled_but_unmapped": modeled_but_unmapped,
        "unmodeled_targets": unmodeled_targets,
        "required_unresolved": required_unresolved,
        "resolution_mismatches": resolution_mismatches,
    }


def _workspace_modelling_review_summary(concept_model: dict, mapping_decisions: list[dict], session_state: dict) -> dict:
    status_counts = {"accepted": 0, "needs_review": 0, "rejected": 0}
    resolution_counts = {
        "direct_mapping": 0,
        "fixed_value": 0,
        "derived_value": 0,
        "target_managed": 0,
        "out_of_scope": 0,
    }
    for item in mapping_decisions:
        status = str(item.get("status") or "needs_review").strip().lower() or "needs_review"
        if status in status_counts:
            status_counts[status] += 1
        resolution_type = str(item.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
        if resolution_type in resolution_counts:
            resolution_counts[resolution_type] += 1

    coverage_counts = {
        "mapped": 0,
        "unresolved": 0,
        "excluded": 0,
        "target_managed": 0,
        "modeled_only": 0,
    }
    group_counts: dict[str, int] = {}
    for item in concept_model.get("attributes") or []:
        if not isinstance(item, dict):
            continue
        coverage_status = str(item.get("coverage_status") or "").strip().lower()
        if coverage_status in coverage_counts:
            coverage_counts[coverage_status] += 1
        group_label = str(item.get("group") or "General").strip() or "General"
        group_counts[group_label] = group_counts.get(group_label, 0) + 1

    transformation_rule_count = sum(
        1 for key in session_state.keys() if str(key).startswith("workspace_transformation_rule::") and str(session_state.get(key) or "").strip()
    )
    return {
        "active_decisions": len(mapping_decisions),
        "status_counts": status_counts,
        "resolution_counts": resolution_counts,
        "coverage_counts": coverage_counts,
        "concept_group_counts": group_counts,
        "business_rule_count": len(concept_model.get("business_rules") or []),
        "transformation_rule_count": transformation_rule_count,
        "target_grain_present": bool(str(concept_model.get("target_grain") or "").strip()),
    }


def _workspace_modelling_overview_summary(
    concept_model: dict,
    mapping_decisions: list[dict],
    session_state: dict,
    *,
    upload_response: dict | None,
    mapping_response: dict | None,
    drift_summary: dict,
    workspace_scope: dict | None = None,
) -> dict:
    review_summary = _workspace_modelling_review_summary(concept_model, mapping_decisions, session_state)
    transformation_spec = _workspace_build_transformation_spec(mapping_decisions, session_state)
    transformation_status = _workspace_transformation_spec_status(transformation_spec)
    scope_caption = _workspace_scope_caption(workspace_scope or current_workspace_scope())
    target_context_message = _workspace_target_context_message(upload_response, mapping_response)
    preview_block_reason = _workspace_preview_context_block_reason(upload_response)
    preview_advisory = _workspace_preview_advisory_message(mapping_decisions)
    codegen_block_reason = _workspace_codegen_block_reason(mapping_decisions)
    excluded_output_summary = _workspace_excluded_output_summary(mapping_decisions)

    connected_results = [
        {
            "signal": "Workspace scope",
            "status": "ready" if scope_caption else "info",
            "result": scope_caption or "No explicit workspace scope yet.",
        },
        {
            "signal": "Target context",
            "status": "ready" if target_context_message else "info",
            "result": target_context_message or "Target context is not fully established yet.",
        },
        {
            "signal": "Decision closure",
            "status": "ready" if not review_summary["status_counts"]["needs_review"] and not review_summary["status_counts"]["rejected"] else "attention",
            "result": (
                f"accepted={review_summary['status_counts']['accepted']}, "
                f"needs_review={review_summary['status_counts']['needs_review']}, "
                f"rejected={review_summary['status_counts']['rejected']}"
            ),
        },
        {
            "signal": "Concept coverage",
            "status": "ready"
            if not review_summary["coverage_counts"]["unresolved"] and not review_summary["coverage_counts"]["modeled_only"]
            else "attention",
            "result": (
                f"mapped={review_summary['coverage_counts']['mapped']}, "
                f"unresolved={review_summary['coverage_counts']['unresolved']}, "
                f"modeled_only={review_summary['coverage_counts']['modeled_only']}, "
                f"excluded={review_summary['coverage_counts']['excluded']}, "
                f"target_managed={review_summary['coverage_counts']['target_managed']}"
            ),
        },
        {
            "signal": "Output contract",
            "status": "ready" if transformation_status.get("state") == "ready" else "attention",
            "result": str(transformation_status.get("message") or "No output contract summary available."),
        },
        {
            "signal": "Output gating",
            "status": "ready" if not codegen_block_reason else "attention",
            "result": codegen_block_reason or "No status-based output block is currently open.",
        },
    ]

    top_findings: list[str] = []
    if review_summary["status_counts"]["needs_review"]:
        top_findings.append(
            f"{review_summary['status_counts']['needs_review']} decision(s) still need review before the workspace result is fully closed."
        )
    if review_summary["status_counts"]["rejected"]:
        top_findings.append(
            f"{review_summary['status_counts']['rejected']} decision(s) are rejected and keep the final result open."
        )
    if drift_summary.get("required_unresolved"):
        top_findings.append(
            "Required modeled attributes are still unresolved: " + ", ".join(drift_summary["required_unresolved"])
        )
    if drift_summary.get("unmodeled_targets"):
        top_findings.append(
            "Current targets are missing from the concept model: " + ", ".join(drift_summary["unmodeled_targets"])
        )
    if transformation_status.get("state") != "ready":
        top_findings.append(str(transformation_status.get("message") or "Output contract is not ready yet."))
    if preview_block_reason:
        top_findings.append(preview_block_reason)
    elif preview_advisory:
        top_findings.append(preview_advisory)
    if excluded_output_summary:
        top_findings.append(excluded_output_summary)

    deduped_findings: list[str] = []
    seen_findings: set[str] = set()
    for finding in top_findings:
        if finding in seen_findings:
            continue
        seen_findings.add(finding)
        deduped_findings.append(finding)

    return {
        "review_summary": review_summary,
        "transformation_status": transformation_status,
        "connected_results": connected_results,
        "top_findings": deduped_findings,
        "target_context_message": target_context_message,
        "scope_caption": scope_caption,
        "excluded_output_summary": excluded_output_summary,
    }


def _workspace_modelling_graph_source_label(mapping_decision: dict) -> str:
    source_name = str(mapping_decision.get("source") or "").strip()
    if source_name:
        return source_name
    resolution_type = str(mapping_decision.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
    payload = mapping_decision.get("resolution_payload") if isinstance(mapping_decision.get("resolution_payload"), dict) else {}
    if resolution_type == "fixed_value":
        for key in ("value", "fixed_value", "literal"):
            value = str(payload.get(key) or "").strip()
            if value:
                return f"Fixed value: {value}"
        return "Fixed value"
    if resolution_type == "derived_value":
        for key in ("expression", "formula", "derivation_rule", "description"):
            value = str(payload.get(key) or "").strip()
            if value:
                return f"Derived: {value}"
        return "Derived rule"
    return _workspace_modelling_resolution_label(resolution_type)


def _workspace_modelling_graph_summary(concept_model: dict, mapping_decisions: list[dict], *, max_edges: int = 18) -> dict:
    attributes_by_name = {
        str(item.get("name") or "").strip(): item
        for item in (concept_model.get("attributes") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }
    graph_rows: list[dict] = []
    seen_rows: set[tuple[str, str, str, str]] = set()

    for item in mapping_decisions:
        target_name = str(item.get("target") or "").strip()
        if not target_name:
            continue
        attribute = attributes_by_name.get(target_name) or {}
        concept_label = f"{target_name} [{str(attribute.get('group') or _workspace_modelling_group_label(target_name)).strip() or 'General'}]"
        source_label = _workspace_modelling_graph_source_label(item)
        resolution_label = _workspace_modelling_resolution_label(item.get("resolution_type"))
        row_key = (source_label, concept_label, target_name, resolution_label)
        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)
        graph_rows.append(
            {
                "source": source_label,
                "concept": concept_label,
                "target": target_name,
                "decision_type": resolution_label,
            }
        )

    mapped_targets = {str(item.get("target") or "").strip() for item in mapping_decisions if str(item.get("target") or "").strip()}
    for attribute_name, attribute in attributes_by_name.items():
        if attribute_name in mapped_targets:
            continue
        concept_label = f"{attribute_name} [{str(attribute.get('group') or _workspace_modelling_group_label(attribute_name)).strip() or 'General'}]"
        row_key = ("Modeled only", concept_label, attribute_name, "Modeled only")
        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)
        graph_rows.append(
            {
                "source": "Modeled only",
                "concept": concept_label,
                "target": attribute_name,
                "decision_type": "Modeled only",
            }
        )

    displayed_rows = graph_rows[:max_edges]
    source_nodes: dict[str, str] = {}
    concept_nodes: dict[str, str] = {}
    target_nodes: dict[str, str] = {}
    mermaid_lines = ["flowchart LR", "    subgraph Source", "    direction TB"]

    def _node_id(prefix: str, index: int) -> str:
        return f"{prefix}_{index}"

    for row in displayed_rows:
        if row["source"] not in source_nodes:
            source_nodes[row["source"]] = _node_id("src", len(source_nodes))
    for label, node_id in source_nodes.items():
        mermaid_lines.append(f'        {node_id}["{label}"]')
    mermaid_lines.extend(["    end", "    subgraph Concept", "    direction TB"])

    for row in displayed_rows:
        if row["concept"] not in concept_nodes:
            concept_nodes[row["concept"]] = _node_id("concept", len(concept_nodes))
    for label, node_id in concept_nodes.items():
        mermaid_lines.append(f'        {node_id}["{label}"]')
    mermaid_lines.extend(["    end", "    subgraph Target", "    direction TB"])

    for row in displayed_rows:
        if row["target"] not in target_nodes:
            target_nodes[row["target"]] = _node_id("target", len(target_nodes))
    for label, node_id in target_nodes.items():
        mermaid_lines.append(f'        {node_id}["{label}"]')
    mermaid_lines.append("    end")

    for row in displayed_rows:
        mermaid_lines.append(
            f"    {source_nodes[row['source']]} -->|{row['decision_type']}| {concept_nodes[row['concept']]}"
        )
        mermaid_lines.append(f"    {concept_nodes[row['concept']]} --> {target_nodes[row['target']]}")

    return {
        "rows": graph_rows,
        "displayed_rows": displayed_rows,
        "mermaid": "\n".join(mermaid_lines),
        "truncated": len(graph_rows) > len(displayed_rows),
        "total_edges": len(graph_rows),
        "displayed_edges": len(displayed_rows),
    }


def _workspace_modelling_list_text(value: object) -> list[str]:
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        items: list[str] = []
        for entry in value:
            text = str(entry or "").strip()
            if text:
                items.append(text)
        return items
    return []


def _workspace_modelling_decision_rationale(mapping_decision: dict) -> str:
    for key in ("explanation", "reasoning"):
        values = _workspace_modelling_list_text(mapping_decision.get(key))
        if values:
            return values[0]
    for key in ("reason", "notes"):
        text = str(mapping_decision.get(key) or "").strip()
        if text:
            return text

    resolution_type = str(mapping_decision.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
    payload = mapping_decision.get("resolution_payload") if isinstance(mapping_decision.get("resolution_payload"), dict) else {}
    if resolution_type == "fixed_value":
        value = str(payload.get("value") or payload.get("fixed_value") or payload.get("literal") or "").strip()
        if value:
            return f"Uses fixed value `{value}`."
    if resolution_type == "derived_value":
        expression = str(
            payload.get("expression") or payload.get("formula") or payload.get("derivation_rule") or payload.get("description") or ""
        ).strip()
        if expression:
            return f"Derived using `{expression}`."
    if resolution_type == "target_managed":
        return "Value is expected to be managed by the target system."
    if resolution_type == "out_of_scope":
        return "Attribute is intentionally excluded from generated output."
    return ""


def _workspace_modelling_key_decision_lines(mapping_decisions: list[dict], *, active_mapping_rows: list[dict] | None = None, max_items: int | None = None) -> list[str]:
    def _priority(item: dict) -> tuple[int, int]:
        status = str(item.get("status") or "needs_review").strip().lower() or "needs_review"
        resolution_type = str(item.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
        significant = int(status != "accepted" or resolution_type != "direct_mapping")
        resolution_weight = 0 if resolution_type in {"fixed_value", "derived_value", "out_of_scope", "target_managed"} else 1
        status_weight = 0 if status != "accepted" else 1
        return (significant, -(2 - status_weight + (1 - min(resolution_weight, 1))))

    active_rows = active_mapping_rows or []
    active_lookup = {
        (str(item.get("source") or "").strip(), str(item.get("target") or "").strip()): item
        for item in active_rows
        if str(item.get("source") or "").strip() and str(item.get("target") or "").strip()
    }

    ordered = sorted(mapping_decisions, key=_priority, reverse=True)
    selected = ordered if max_items is None else ordered[:max_items]
    lines: list[str] = []
    for item in selected:
        source_name = _workspace_modelling_graph_source_label(item)
        target_name = str(item.get("target") or "unassigned").strip() or "unassigned"
        status = str(item.get("status") or "needs_review").strip().lower() or "needs_review"
        decision_type = _workspace_modelling_resolution_label(item.get("resolution_type"))
        rationale = _workspace_modelling_decision_rationale(item)
        line = f"- `{source_name} -> {target_name}` ({status}; {decision_type})"
        if rationale:
            line += f": {rationale}"
        active_row = active_lookup.get((source_name, target_name))
        signal_summary = _workspace_modelling_signal_summary_text(active_row.get("signals") if isinstance(active_row, dict) else {}) if active_row else ""
        if signal_summary:
            line += f" [{signal_summary}]"
        lines.append(line)
    return lines


def _workspace_modelling_next_steps(overview_summary: dict, drift_summary: dict) -> list[str]:
    steps: list[str] = []
    review_summary = overview_summary.get("review_summary") or {}
    transformation_status = overview_summary.get("transformation_status") or {}
    status_counts = review_summary.get("status_counts") or {}
    coverage_counts = review_summary.get("coverage_counts") or {}
    if int(status_counts.get("needs_review") or 0):
        steps.append("Return to Decisions to close the remaining open review items.")
    if int(status_counts.get("rejected") or 0):
        steps.append("Resolve rejected decisions before treating the workspace result as a stable handoff artifact.")
    if drift_summary.get("required_unresolved") or int(coverage_counts.get("modeled_only") or 0):
        steps.append("Refine the concept model and/or decisions so all required attributes are represented by a closed mapping outcome.")
    if str(transformation_status.get("state") or "") != "ready":
        steps.append("Return to Output and complete the transformation contract so preview/code generation can rely on a governed result.")
    if not steps:
        steps.append("Workspace result is coherent; the next step is export, handoff, or governance review.")
    return steps


def _workspace_modelling_conclusion(overview_summary: dict, drift_summary: dict) -> str:
    review_summary = overview_summary.get("review_summary") or {}
    status_counts = review_summary.get("status_counts") or {}
    transformation_status = overview_summary.get("transformation_status") or {}
    if (
        not int(status_counts.get("needs_review") or 0)
        and not int(status_counts.get("rejected") or 0)
        and str(transformation_status.get("state") or "") == "ready"
        and str(drift_summary.get("status") or "") == "in_sync"
    ):
        return "The workspace result is coherent across context, decisions, concept coverage, and output contract readiness."
    if int(status_counts.get("needs_review") or 0) or int(status_counts.get("rejected") or 0):
        return "The workspace result is materially defined, but decision closure is still incomplete."
    if str(transformation_status.get("state") or "") != "ready":
        return "The analytical result is present, but the output contract is not ready yet."
    return "The workspace result is useful as a review artifact, but it still has alignment gaps before it becomes a closed handoff."


def _workspace_modelling_signal_breakdown_text(signals: object) -> str:
    signal_values = signals if isinstance(signals, dict) else {}
    ordered_keys = [
        ("name", "name"),
        ("semantic", "semantic"),
        ("knowledge", "knowledge"),
        ("canonical", "canonical"),
        ("pattern", "pattern"),
        ("statistical", "stat"),
        ("overlap", "overlap"),
        ("embedding", "embedding"),
        ("correction", "correction"),
        ("llm", "llm"),
    ]
    parts: list[str] = []
    for source_key, label in ordered_keys:
        try:
            value = float(signal_values.get(source_key) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        parts.append(f"{label}={value:.2f}")
    return "Signal breakdown: " + ", ".join(parts) + "."


def _workspace_modelling_signal_summary_text(signals: object, *, max_parts: int = 3) -> str:
    signal_values = signals if isinstance(signals, dict) else {}
    numeric_values: list[tuple[str, float]] = []
    for key, label in [
        ("canonical", "canonical"),
        ("semantic", "semantic"),
        ("pattern", "pattern"),
        ("name", "name"),
        ("knowledge", "knowledge"),
        ("statistical", "stat"),
        ("overlap", "overlap"),
        ("embedding", "embedding"),
        ("correction", "correction"),
        ("llm", "llm"),
    ]:
        try:
            value = float(signal_values.get(key) or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        numeric_values.append((label, value))
    top_signals = [f"{label}={value:.2f}" for label, value in sorted(numeric_values, key=lambda item: item[1], reverse=True)[:max_parts] if value > 0.0]
    return "signals: " + ", ".join(top_signals) if top_signals else ""


def _workspace_modelling_canonical_path_text(mapping_row: dict) -> str:
    canonical_path = str(mapping_row.get("canonical_path") or "").strip()
    if canonical_path:
        return canonical_path
    canonical_details = mapping_row.get("canonical_details") if isinstance(mapping_row.get("canonical_details"), dict) else {}
    shared_concepts = canonical_details.get("shared_concepts") or []
    if shared_concepts:
        labels = [str((item or {}).get("display_name") or "").strip() for item in shared_concepts if str((item or {}).get("display_name") or "").strip()]
        if labels:
            source_name = str(mapping_row.get("source") or "").strip() or "source"
            target_name = str(mapping_row.get("target") or "").strip() or "target"
            return f"{source_name} -> {', '.join(labels)} -> {target_name}"
    return ""


def _workspace_modelling_review_conclusion_text(mapping_row: dict) -> str:
    explanation_lines = _workspace_modelling_list_text(mapping_row.get("explanation"))
    if explanation_lines:
        return " | ".join(explanation_lines)
    rationale = _workspace_modelling_decision_rationale(mapping_row)
    return rationale


def _workspace_modelling_active_mapping_rows(mapping_response: dict | None, session_state: dict) -> list[dict]:
    current_response = mapping_response or {}
    selected_rows = [item for item in (current_response.get("selected_mapping") or []) if isinstance(item, dict)]
    if selected_rows:
        return selected_rows

    mappings = [item for item in (current_response.get("mappings") or []) if isinstance(item, dict)]
    ranked_mappings = [item for item in (current_response.get("ranked_mappings") or []) if isinstance(item, dict)]
    if not ranked_mappings:
        return mappings

    try:
        from streamlit_ui.mapping_helpers import suggested_mapping_by_source

        selected_by_source = suggested_mapping_by_source(current_response)
    except Exception:
        selected_by_source = {
            str(item.get("source") or "").strip(): item
            for item in mappings
            if str(item.get("source") or "").strip()
        }

    editor_state = session_state.get("mapping_editor_state") or {}
    active_rows: list[dict] = []
    for ranked in ranked_mappings:
        source_name = str(ranked.get("source") or "").strip()
        if not source_name:
            continue
        selected_row = selected_by_source.get(source_name) or {}
        current_entry = editor_state.get(source_name) if isinstance(editor_state, dict) else {}
        if not isinstance(current_entry, dict):
            current_entry = {}
        fallback_selected = (ranked.get("selected") or {}) if isinstance(ranked.get("selected"), dict) else {}
        current_target = str(
            current_entry.get("target")
            or selected_row.get("target")
            or fallback_selected.get("target")
            or ""
        ).strip()
        if not current_target:
            continue
        selected_candidate = next(
            (
                candidate
                for candidate in (ranked.get("candidates") or [])
                if isinstance(candidate, dict) and str(candidate.get("target") or "").strip() == current_target
            ),
            None,
        )
        base_row = (
            selected_candidate
            or (selected_row if str(selected_row.get("target") or "").strip() == current_target else {})
            or (fallback_selected if str(fallback_selected.get("target") or "").strip() == current_target else {})
            or selected_row
            or fallback_selected
        )
        merged_row = dict(base_row)
        merged_row["source"] = source_name
        merged_row["target"] = current_target
        merged_row["status"] = str(
            current_entry.get("status")
            or merged_row.get("status")
            or selected_row.get("status")
            or fallback_selected.get("status")
            or "needs_review"
        ).strip() or "needs_review"
        if current_entry.get("resolution_type") and not merged_row.get("resolution_type"):
            merged_row["resolution_type"] = current_entry.get("resolution_type")
        if current_entry.get("resolution_payload") and not merged_row.get("resolution_payload"):
            merged_row["resolution_payload"] = current_entry.get("resolution_payload")
        if current_entry.get("manual_transformation_code") and not merged_row.get("transformation_code"):
            merged_row["transformation_code"] = current_entry.get("manual_transformation_code")
        active_rows.append(merged_row)
    return active_rows or mappings


def _workspace_modelling_review_evidence_sort_key(item: dict) -> tuple[int, int, float, str]:
    status = str(item.get("status") or "needs_review").strip().lower() or "needs_review"
    resolution_type = str(item.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
    unresolved = int(status != "accepted")
    direct = int(resolution_type == "direct_mapping")
    confidence = float(item.get("confidence") or 0.0)
    canonical = 0 if _workspace_modelling_canonical_path_text(item) else 1
    return (unresolved, canonical, -confidence, str(item.get("source") or ""))


def _workspace_modelling_review_evidence_rows(mapping_response: dict | None, session_state: dict, *, max_items: int | None = None) -> list[dict]:
    rows = _workspace_modelling_active_mapping_rows(mapping_response, session_state)
    ranked = sorted(rows, key=_workspace_modelling_review_evidence_sort_key)
    evidence_rows: list[dict] = []
    for item in ranked:
        evidence_rows.append(
            {
                "source": str(item.get("source") or "").strip(),
                "target": str(item.get("target") or "").strip(),
                "canonical_path": _workspace_modelling_canonical_path_text(item),
                "signal_breakdown": _workspace_modelling_signal_breakdown_text(item.get("signals")),
                "review_conclusion": _workspace_modelling_review_conclusion_text(item),
                "status": str(item.get("status") or "needs_review").strip().lower() or "needs_review",
                "confidence": float(item.get("confidence") or 0.0),
                "has_canonical": bool(_workspace_modelling_canonical_path_text(item)),
            }
        )
        if max_items is not None and len(evidence_rows) >= max_items:
            break
    return evidence_rows


def _workspace_modelling_review_evidence_metrics(mapping_response: dict | None, session_state: dict) -> list[str]:
    rows = _workspace_modelling_active_mapping_rows(mapping_response, session_state)
    total = len(rows)
    canonical_count = sum(1 for item in rows if bool(_workspace_modelling_canonical_path_text(item)))
    accepted_count = sum(1 for item in rows if str(item.get("status") or "").strip().lower() == "accepted")
    unresolved_count = sum(1 for item in rows if str(item.get("status") or "").strip().lower() != "accepted")
    high_confidence = sum(1 for item in rows if float(item.get("confidence") or 0.0) >= 0.85)
    low_confidence = sum(1 for item in rows if float(item.get("confidence") or 0.0) < 0.85)
    metrics: list[str] = []
    metrics.append(f"Evidence rows: {total}")
    metrics.append(f"Canonical path coverage: {canonical_count} / {total}")
    metrics.append(f"Accepted decisions: {accepted_count}")
    if unresolved_count:
        metrics.append(f"Open review items: {unresolved_count}")
    if total:
        metrics.append(f"Confidence profile: {high_confidence} high, {low_confidence} low")
    return metrics


def _workspace_modelling_graph_evidence_rows(
    mapping_response: dict | None,
    session_state: dict,
    graph_summary: dict,
    *,
    max_items: int = 18,
) -> list[dict]:
    selected_rows = _workspace_modelling_active_mapping_rows(mapping_response, session_state)
    if not selected_rows:
        return []

    row_lookup: dict[tuple[str, str], dict] = {}
    for row in selected_rows:
        source_name = _workspace_modelling_graph_source_label(row)
        target_name = str(row.get("target") or "").strip()
        if not target_name:
            continue
        row_lookup[(source_name, target_name)] = row

    evidence_rows: list[dict] = []
    for graph_row in (graph_summary.get("displayed_rows") or [])[:max_items]:
        source_name = str((graph_row or {}).get("source") or "").strip()
        target_name = str((graph_row or {}).get("target") or "").strip()
        mapping_row = row_lookup.get((source_name, target_name))
        if not mapping_row:
            continue
        evidence_rows.append(
            {
                "source": source_name,
                "target": target_name,
                "canonical_path": _workspace_modelling_canonical_path_text(mapping_row),
                "signal_breakdown": _workspace_modelling_signal_breakdown_text(mapping_row.get("signals")),
                "review_conclusion": _workspace_modelling_review_conclusion_text(mapping_row),
                "decision_type": _workspace_modelling_resolution_label(mapping_row.get("resolution_type")),
            }
        )
    return evidence_rows


def _workspace_modelling_business_intent_lines(
    concept_model: dict,
    session_state: dict,
    *,
    upload_response: dict | None,
    mapping_response: dict | None,
) -> list[str]:
    lines: list[str] = []
    description = str(concept_model.get("description") or "").strip()
    if description:
        lines.append(f"Object description: {description}")
    business_purpose = str(concept_model.get("business_purpose") or "").strip()
    if business_purpose:
        lines.append(f"Business purpose: {business_purpose}")
    target_context_message = _workspace_target_context_message(upload_response, mapping_response)
    if target_context_message:
        lines.append(target_context_message)
    for label, key in (
        ("Target grain assumption", "workspace_transformation_target_grain"),
        ("Default handling", "workspace_transformation_defaults"),
        ("Global rule context", "workspace_transformation_global_rules"),
        ("Examples / edge cases", "workspace_transformation_examples"),
    ):
        text = str(session_state.get(key) or "").strip()
        if text:
            lines.append(f"{label}: {text}")
    return lines


def _workspace_modelling_decision_override_lines(session_state: dict) -> list[str]:
    audit_map = session_state.get("mapping_decision_audit") or {}
    if not isinstance(audit_map, dict):
        return []
    lines: list[str] = []
    for source, metadata in audit_map.items():
        current = metadata if isinstance(metadata, dict) else {}
        origin = str(current.get("origin") or "manual_or_imported").strip() or "manual_or_imported"
        details = current.get("details") if isinstance(current.get("details"), dict) else {}
        detail_parts: list[str] = []
        for key in ("mode", "target", "status", "resolution_type", "proposal_origin"):
            text = str(details.get(key) or "").strip()
            if text:
                detail_parts.append(f"{key}={text}")
        confidence = details.get("confidence")
        if confidence not in (None, ""):
            try:
                detail_parts.append(f"confidence={float(confidence):.2f}")
            except (TypeError, ValueError):
                pass
        payload = details.get("resolution_payload") if isinstance(details.get("resolution_payload"), dict) else {}
        if payload:
            detail_parts.append("payload=" + ", ".join(f"{key}={value}" for key, value in payload.items()))
        lines.append(f"{source}: origin={origin}" + (f"; {'; '.join(detail_parts)}" if detail_parts else ""))
    return lines


def _workspace_modelling_transformation_rationale_lines(session_state: dict, mapping_decisions: list[dict], codegen_response: dict | None) -> list[str]:
    lines: list[str] = []
    editor_state = session_state.get("mapping_editor_state") or {}
    decision_target_map: dict[str, str] = {}
    for decision in mapping_decisions:
        if not isinstance(decision, dict):
            continue
        source_name = str(decision.get("source") or "").strip()
        target_name = str(decision.get("target") or "").strip()
        if source_name and target_name:
            decision_target_map[source_name] = target_name
    if isinstance(editor_state, dict):
        for source, entry in editor_state.items():
            current = entry if isinstance(entry, dict) else {}
            target = str(current.get("target") or decision_target_map.get(str(source).strip()) or "").strip()
            if not target:
                continue
            detail_parts: list[str] = []
            transform_rule = str(session_state.get(f"workspace_transformation_rule::{target}") or "").strip()
            if transform_rule:
                detail_parts.append(f"rule={transform_rule}")
            llm_instruction = str(current.get("llm_transformation_instruction") or "").strip()
            if llm_instruction:
                detail_parts.append(f"instruction={llm_instruction}")
            manual_code = str(current.get("manual_transformation_code") or "").strip()
            if manual_code:
                detail_parts.append("custom transformation present")
            reasoning = [str(item).strip() for item in (current.get("generated_transformation_reasoning") or []) if str(item).strip()]
            if reasoning:
                detail_parts.append("reasoning=" + " | ".join(reasoning))
            if detail_parts:
                lines.append(f"{source} -> {target}: " + "; ".join(detail_parts))
    codegen_reasoning = [str(item).strip() for item in ((codegen_response or {}).get("reasoning") or []) if str(item).strip()]
    if codegen_reasoning:
        lines.append("Generated artifact reasoning: " + " | ".join(codegen_reasoning))
    return lines


def _workspace_modelling_analyst_notes_lines(session_state: dict, hints: list[str]) -> list[str]:
    lines: list[str] = []
    for label, key in (
        ("Version note", "mapping_set_note"),
        ("Review note", "mapping_set_review_note"),
        ("Owner", "mapping_set_owner"),
        ("Assignee", "mapping_set_assignee"),
    ):
        text = str(session_state.get(key) or "").strip()
        if text:
            lines.append(f"{label}: {text}")
    last_action = session_state.get("last_action") if isinstance(session_state.get("last_action"), dict) else {}
    last_message = str(last_action.get("message") or "").strip()
    if last_message:
        lines.append(f"Latest workspace note: {last_message}")
    if hints:
        lines.append("Current modelling notes: " + " | ".join(hints[:5]))
    return lines


def _workspace_modelling_governance_readiness_lines(session_state: dict, overview_summary: dict, drift_summary: dict) -> list[str]:
    lines: list[str] = []
    selected_status = str(session_state.get("selected_saved_mapping_set_status") or "").strip()
    if selected_status:
        lines.append(f"Current mapping-set status shortcut: {selected_status}")
    review_summary = overview_summary.get("review_summary") or {}
    transformation_status = overview_summary.get("transformation_status") or {}
    status_counts = review_summary.get("status_counts") or {}
    if int(status_counts.get("needs_review") or 0) or int(status_counts.get("rejected") or 0):
        lines.append("Decision closure is not complete, so the result is not ready for final approval.")
    else:
        lines.append("Decision closure is complete for the current active mapping set.")
    if str(transformation_status.get("state") or "") == "ready":
        lines.append("Output contract is ready for governed handoff.")
    else:
        lines.append("Output contract is still open and should be completed before governance approval.")
    if str(drift_summary.get("status") or "") != "in_sync":
        lines.append("Concept drift is still present between the model and operational decisions.")
    else:
        lines.append("Concept model is aligned with the current operational decision state.")
    lines.append("Primary approval path remains Governance > Stewardship.")
    return lines


def _workspace_modelling_report_mapping_rows(mapping_response: dict | None, session_state: dict) -> list[dict]:
    try:
        from streamlit_ui.mapping_helpers import current_mapping_rows
        from streamlit_ui.shared_views import _workspace_copilot_validator_badge
        from streamlit_ui.workspace_review_views import _confidence_percent_label

        base_rows = current_mapping_rows(
            mapping_response or {},
            session_state or {},
            validator_badge=_workspace_copilot_validator_badge,
        )
    except Exception:
        try:
            from streamlit_ui.workspace_review_views import _selected_mapping_display_rows

            base_rows = _selected_mapping_display_rows(
                _workspace_modelling_active_mapping_rows(mapping_response, session_state),
                session_state.get("mapping_editor_state") or {},
                pending_proposals=session_state.get("llm_decision_proposals") or [],
            )
        except Exception:
            base_rows = []

    report_rows: list[dict] = []
    for row in base_rows:
        target_name = str(row.get("target") or "").strip()
        entry = (session_state.get("mapping_editor_state") or {}).get(str(row.get("source") or "").strip()) or {}
        decision_type = _workspace_modelling_resolution_label(entry.get("resolution_type"))
        transformation_rule = str(session_state.get(f"workspace_transformation_rule::{target_name}") or "").strip()
        report_rows.append(
            {
                "source": str(row.get("source") or "").strip(),
                "target": target_name,
                "confidence": _confidence_percent_label(row.get("confidence")) if row.get("confidence") not in (None, "") else str(row.get("original_confidence") or ""),
                "llm": str(row.get("llm_proposal_confidence") or ""),
                "status": str(entry.get("status") or row.get("status") or "").strip(),
                "validator": str(row.get("validator") or "").strip(),
                "source_concepts": str(row.get("source_concepts") or "").strip(),
                "target_concepts": str(row.get("target_concepts") or "").strip(),
                "canonical_path": str(row.get("canonical_path") or "").strip(),
                "decision_type": decision_type,
                "transformation_rule": transformation_rule,
                "llm_consulted": str(row.get("llm_consulted") or "").strip(),
            }
        )
    return report_rows


def _workspace_modelling_report_table_cell(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "-"
    return text.replace("|", "/").replace("\n", " ")


def _workspace_modelling_markdown_table(rows: list[dict], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return ""
    header = "| " + " | ".join(label for _key, label in columns) + " |"
    separator = "| " + " | ".join("---" for _key, _label in columns) + " |"
    lines = [header, separator]
    for row in rows:
        values = [_workspace_modelling_report_table_cell(row.get(key)) for key, _label in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _workspace_modelling_default_code_block(mapping_decisions: list[dict], session_state: dict, *, mode: str = "dbt") -> tuple[str, str, str]:
    normalized_mode = str(mode or "dbt").strip().lower() or "dbt"
    target_fields = _workspace_transformation_target_fields(mapping_decisions)
    if not target_fields:
        target_fields = [
            str(item).strip()
            for item in _workspace_modelling_parse_lines(session_state.get("workspace_modelling_required_attributes"))
            if str(item).strip()
        ]
    if normalized_mode == "pyspark":
        lines = [
            "# Suggested starter only. Generate Output to replace this with governed code.",
            "from pyspark.sql import functions as F",
            "",
            "result_df = source_df.select(",
        ]
        for field in target_fields or ["target_field"]:
            lines.append(f"    F.lit(None).alias(\"{field}\"),")
        lines.append(")")
        return ("pyspark", "python", "\n".join(lines))
    if normalized_mode == "pandas":
        lines = [
            "# Suggested starter only. Generate Output to replace this with governed code.",
            "result_df = source_df.assign(",
        ]
        for field in target_fields or ["target_field"]:
            lines.append(f"    {field}=None,")
        lines.append(")")
        return ("pandas", "python", "\n".join(lines))
    select_lines = ["-- Suggested starter only. Generate Output to replace this with governed dbt SQL.", "select"]
    if target_fields:
        for index, field in enumerate(target_fields):
            suffix = "," if index < len(target_fields) - 1 else ""
            select_lines.append(f"    cast(null as string) as {field}{suffix}")
    else:
        select_lines.append("    cast(null as string) as target_field")
    return ("dbt", "sql", "\n".join(select_lines))


def _workspace_build_mapping_report_markdown(
    concept_model: dict,
    mapping_decisions: list[dict],
    session_state: dict,
    *,
    upload_response: dict | None,
    mapping_response: dict | None,
    codegen_response: dict | None = None,
    workspace_scope: dict | None = None,
) -> str:
    drift_summary = _workspace_concept_model_drift_summary(concept_model, mapping_decisions)
    overview_summary = _workspace_modelling_overview_summary(
        concept_model,
        mapping_decisions,
        session_state,
        upload_response=upload_response,
        mapping_response=mapping_response,
        drift_summary=drift_summary,
        workspace_scope=workspace_scope,
    )
    graph_summary = _workspace_modelling_graph_summary(concept_model, mapping_decisions)
    hints = _workspace_modelling_hints(concept_model, drift_summary)
    pending_hints = [str(item).strip() for item in (session_state.get("workspace_modelling_pending_hints") or []) if str(item).strip()]
    review_summary = overview_summary["review_summary"]
    target_context = _workspace_target_context(upload_response, mapping_response) or {}
    source_snapshot = (upload_response or {}).get("source") if isinstance((upload_response or {}).get("source"), dict) else {}
    scope_caption = overview_summary.get("scope_caption") or "No explicit workspace scope yet."
    graph_note = ""
    if graph_summary["truncated"]:
        graph_note = f"Showing {graph_summary['displayed_edges']} of {graph_summary['total_edges']} paths in the graph to keep the report readable."

    required_attributes = [
        str(item.get("name") or "").strip()
        for item in (concept_model.get("attributes") or [])
        if isinstance(item, dict) and item.get("required") and str(item.get("name") or "").strip()
    ]
    concept_group_lines = [
        f"- {group}: {count}"
        for group, count in (review_summary.get("concept_group_counts") or {}).items()
    ] or ["- No concept groups are currently inferred."]
    business_rules = [str(item).strip() for item in (concept_model.get("business_rules") or []) if str(item).strip()]
    business_rule_lines = [f"- {rule}" for rule in business_rules] or ["- No explicit business rules captured yet."]
    active_mapping_rows = _workspace_modelling_active_mapping_rows(mapping_response, session_state)
    key_decision_lines = _workspace_modelling_key_decision_lines(mapping_decisions, active_mapping_rows=active_mapping_rows)
    if len(mapping_decisions) > len(key_decision_lines):
        key_decision_lines.append(f"- Additional decision rows not shown in this report summary: {len(mapping_decisions) - len(key_decision_lines)}")

    top_finding_lines = [f"- {item}" for item in (overview_summary.get("top_findings") or [])] or ["- No blocking findings are currently open."]
    next_step_lines = [f"- {item}" for item in _workspace_modelling_next_steps(overview_summary, drift_summary)]
    connected_result_lines = [
        f"- {item['signal']} ({item['status']}): {item['result']}"
        for item in (overview_summary.get("connected_results") or [])
    ]
    review_evidence_rows = _workspace_modelling_review_evidence_rows(mapping_response, session_state)
    review_evidence_metrics = _workspace_modelling_review_evidence_metrics(mapping_response, session_state)
    review_evidence_lines: list[str] = []
    for row in review_evidence_rows:
        review_evidence_lines.extend(
            [
                f"### {row['source']} -> {row['target']}",
                f"- Canonical path: {row['canonical_path'] or 'No shared canonical path.'}",
                f"- {row['signal_breakdown']}",
                f"- Review conclusion: {row['review_conclusion'] or 'No detailed review explanation is currently available.'}",
                "",
            ]
        )
    mapping_report_rows = _workspace_modelling_report_mapping_rows(mapping_response, session_state)
    mapping_report_table = _workspace_modelling_markdown_table(
        mapping_report_rows,
        [
            ("source", "Source"),
            ("target", "Target"),
            ("confidence", "Confidence"),
            ("llm", "LLM"),
            ("status", "Status"),
            ("validator", "Validator"),
            ("source_concepts", "Source concepts"),
            ("target_concepts", "Target concepts"),
            ("canonical_path", "Canonical path"),
            ("decision_type", "Decision type"),
            ("transformation_rule", "Transformation rule"),
            ("llm_consulted", "LLM consulted"),
        ],
    )
    transformation_spec = _workspace_build_transformation_spec(mapping_decisions, session_state)
    transformation_rows = [
        {
            "target_field": str((item or {}).get("target_field") or "").strip(),
            "rule": str((item or {}).get("rule") or "").strip(),
        }
        for item in (transformation_spec.get("field_rules") or [])
        if str((item or {}).get("target_field") or "").strip() or str((item or {}).get("rule") or "").strip()
    ]
    transformation_table = _workspace_modelling_markdown_table(
        transformation_rows,
        [("target_field", "Target field"), ("rule", "Transformation rule")],
    )
    business_intent_lines = _workspace_modelling_business_intent_lines(
        concept_model,
        session_state,
        upload_response=upload_response,
        mapping_response=mapping_response,
    )
    decision_override_lines = _workspace_modelling_decision_override_lines(session_state)
    transformation_rationale_lines = _workspace_modelling_transformation_rationale_lines(session_state, mapping_decisions, codegen_response)
    analyst_note_lines = _workspace_modelling_analyst_notes_lines(session_state, hints)
    governance_readiness_lines = _workspace_modelling_governance_readiness_lines(session_state, overview_summary, drift_summary)
    generated_code = str((codegen_response or {}).get("code") or "").strip()
    generated_language = str((codegen_response or {}).get("language") or "").strip()
    if generated_code:
        code_mode = "dbt" if generated_language == "sql-dbt" else "pyspark" if generated_language == "python-pyspark" else "pandas"
        code_language = _workspace_generated_artifact_code_language(generated_language)
        code_title = _workspace_generated_artifact_header(generated_language)
        code_block = generated_code
    else:
        code_mode, code_language, code_block = _workspace_modelling_default_code_block(mapping_decisions, session_state, mode="dbt")
        code_title = f"Suggested {_workspace_codegen_format_label(code_mode)}"

    report_sections = [
        "# BA Mapping Report",
        "",
        "## Executive Summary",
        _workspace_modelling_conclusion(overview_summary, drift_summary),
        "",
        f"- Target object: {concept_model.get('object_name') or 'n/a'}",
        f"- Target context: {overview_summary.get('target_context_message') or 'Not established yet.'}",
        f"- Active decisions: {review_summary.get('active_decisions')}",
        (
            f"- Coverage: mapped={review_summary['coverage_counts']['mapped']}, "
            f"unresolved={review_summary['coverage_counts']['unresolved']}, "
            f"modeled_only={review_summary['coverage_counts']['modeled_only']}, "
            f"excluded={review_summary['coverage_counts']['excluded']}, "
            f"target_managed={review_summary['coverage_counts']['target_managed']}"
        ),
        f"- Output contract: {str((overview_summary.get('transformation_status') or {}).get('message') or 'No output contract summary available.')}",
        "",
        "## Starting Point and Scope",
        f"- Workspace scope: {scope_caption}",
        f"- Mapping mode: {str(target_context.get('mapping_mode') or 'unknown')}",
        f"- Projection: {str(target_context.get('projection_label') or 'n/a')}",
        f"- Source dataset snapshot: {'loaded' if str(source_snapshot.get('dataset_id') or '').strip() else 'not loaded'}",
        "",
        "## Source and Target Landscape",
        f"- Source artifact: {str(source_snapshot.get('dataset_name') or source_snapshot.get('file_name') or source_snapshot.get('filename') or 'Current workspace source snapshot')}",
        f"- Target object: {concept_model.get('object_name') or 'n/a'}",
        f"- Target grain: {concept_model.get('target_grain') or 'Not defined yet.'}",
        f"- Target profile: {str(target_context.get('target_profile') or target_context.get('target_dataset_name') or 'n/a')}",
        "",
        "## Business Intent and Assumptions",
        *([f"- {line}" for line in business_intent_lines] or ["- No additional business intent or assumption notes are currently captured."]),
        "",
        "## Mapping Outcome Summary",
        f"- Decision closure: accepted={review_summary['status_counts']['accepted']}, needs_review={review_summary['status_counts']['needs_review']}, rejected={review_summary['status_counts']['rejected']}",
        (
            f"- Resolution types: direct={review_summary['resolution_counts']['direct_mapping']}, "
            f"fixed={review_summary['resolution_counts']['fixed_value']}, "
            f"derived={review_summary['resolution_counts']['derived_value']}, "
            f"target_managed={review_summary['resolution_counts']['target_managed']}, "
            f"n/a={review_summary['resolution_counts']['out_of_scope']}"
        ),
        *connected_result_lines,
        "",
        "## Key Decisions and Rationale",
        *(key_decision_lines or ["- No active mapping decisions are currently available."]),
        "",
        "## Review Evidence Highlights",
        *([f"- {line}" for line in review_evidence_metrics] or ["- No review evidence summary is currently available."]),
        *(review_evidence_lines or ["- No review evidence highlights are currently available.", ""]),
        "## Selected Mapping and Transformation Summary",
        *(["- The table below summarizes active selected mappings, decision status, and transformation rule guidance.", ""] if mapping_report_table else []),
        *( [mapping_report_table, ""] if mapping_report_table else ["- No selected-mapping rows are currently available.", ""] ),
        "## Decision Rationale Overrides",
        *([f"- {line}" for line in decision_override_lines] or ["- No explicit decision overrides or audit events are currently recorded."]),
        "",
        "## Transformation Rationale By Field",
        *([f"- {line}" for line in transformation_rationale_lines] or ["- No field-level transformation rationale is currently captured."]),
        "",
        "## Implementation Artifact",
        f"- Preferred code view: {code_mode}",
        f"- Artifact section: {code_title}",
        f"```{code_language}",
        code_block,
        "```",
        "",
        "## Concept Model Result",
        f"- Business object: {concept_model.get('object_name') or 'n/a'}",
        f"- Description: {concept_model.get('description') or 'n/a'}",
        f"- Business purpose: {concept_model.get('business_purpose') or 'n/a'}",
        f"- Target grain: {concept_model.get('target_grain') or 'Not defined yet.'}",
        "",
        "### Concept Groups",
        *concept_group_lines,
        "",
        "### Required Attributes",
        *([f"- {name}" for name in required_attributes] or ["- No required attributes flagged yet."]),
        "",
        "### Business Rules",
        *business_rule_lines,
        "",
        "## Source -> Concept -> Target Graph",
        graph_note,
        "```mermaid",
        graph_summary["mermaid"],
        "```",
        "## Output Contract Summary",
        f"- Contract state: {str((overview_summary.get('transformation_status') or {}).get('state') or 'n/a')}",
        f"- Contract detail: {str((overview_summary.get('transformation_status') or {}).get('message') or 'No detail available.')}",
        f"- Transformation carry-over: field_rules={review_summary['transformation_rule_count']}, business_rules={review_summary['business_rule_count']}",
        f"- Excluded output summary: {overview_summary.get('excluded_output_summary') or 'None.'}",
        "",
        "## Open Analyst Notes",
        *([f"- {line}" for line in analyst_note_lines] or ["- No additional analyst notes are currently captured."]),
        "",
        "## Approval and Governance Readiness",
        *([f"- {line}" for line in governance_readiness_lines] or ["- Governance readiness is not yet available."]),
        "",
        "## Risks, Gaps, and Open Questions",
        *top_finding_lines,
        *( [f"- Prepared decision hints: {', '.join(pending_hints)}"] if pending_hints else [] ),
        *( [f"- Additional modelling hints: {', '.join(hints)}"] if hints else [] ),
        "",
        "## Recommended Next Steps",
        *next_step_lines,
        "",
    ]
    return "\n".join(line for line in report_sections if line is not None)


def _workspace_modelling_hints(concept_model: dict, drift_summary: dict) -> list[str]:
    hints: list[str] = []
    for attribute_name in drift_summary.get("required_unresolved") or []:
        hints.append(f"Required modeled attribute still has no closed mapping: {attribute_name}.")
    for attribute_name in drift_summary.get("unmodeled_targets") or []:
        hints.append(f"Current decision target is not represented in the concept model: {attribute_name}.")
    for attribute_name in drift_summary.get("resolution_mismatches") or []:
        hints.append(f"Expected decision type differs from current decision type for: {attribute_name}.")
    for item in concept_model.get("attributes") or []:
        if not isinstance(item, dict):
            continue
        coverage_status = str(item.get("coverage_status") or "").strip().lower()
        attribute_name = str(item.get("name") or "").strip()
        if coverage_status == "target_managed":
            hints.append(f"Target-managed attribute stays outside generated output: {attribute_name}.")
        elif coverage_status == "excluded":
            hints.append(f"N/A attribute stays outside generated output: {attribute_name}.")
    deduped: list[str] = []
    seen: set[str] = set()
    for hint in hints:
        if hint in seen:
            continue
        seen.add(hint)
        deduped.append(hint)
    return deduped


def _render_workspace_modelling_section(
    *,
    session_state: dict,
    upload_response: dict | None,
    mapping_response: dict | None,
    codegen_response: dict | None,
    mapping_decisions: list[dict],
) -> None:
    inferred_targets = _workspace_modelling_inferred_targets(mapping_decisions, session_state)
    if not inferred_targets:
        st.info(
            "Generate or restore mapping state first. Modelling derives the initial concept model from current Workspace decisions and Transformation Design context."
        )
        return

    generate_col, refresh_col, apply_col, drift_col = st.columns(4)
    generated = bool(session_state.get("workspace_concept_model_generated"))
    if generate_col.button("Generate model from current workspace", key="workspace_modelling_generate", width="stretch"):
        inferred_model = _workspace_build_inferred_concept_model(mapping_decisions, session_state, upload_response)
        session_state["workspace_concept_model_inferred"] = inferred_model
        session_state["workspace_concept_model_generated"] = True
        session_state["workspace_modelling_show_drift"] = False
        _workspace_seed_modelling_editor_state(inferred_model, session_state, force=True)
        st.rerun()
    if refresh_col.button("Refresh from workspace", key="workspace_modelling_refresh", width="stretch", disabled=not generated):
        inferred_model = _workspace_build_inferred_concept_model(mapping_decisions, session_state, upload_response)
        session_state["workspace_concept_model_inferred"] = inferred_model
        session_state["workspace_concept_model_generated"] = True
        session_state["workspace_modelling_show_drift"] = True
        _workspace_seed_modelling_editor_state(inferred_model, session_state, force=False)
        st.rerun()
    if drift_col.button("Show drift", key="workspace_modelling_show_drift_button", width="stretch", disabled=not generated):
        session_state["workspace_modelling_show_drift"] = True
        st.rerun()

    if not generated:
        st.caption(
            "Use Generate model from current workspace to create the first derived conceptual model from active mapping decisions and Transformation Design context."
        )
        return

    inferred_model = session_state.get("workspace_concept_model_inferred") or _workspace_build_inferred_concept_model(
        mapping_decisions,
        session_state,
        upload_response,
    )
    _workspace_seed_modelling_editor_state(inferred_model, session_state, force=False)
    concept_model = _workspace_build_concept_model(inferred_model, session_state)
    drift_summary = _workspace_concept_model_drift_summary(concept_model, mapping_decisions)
    hints = _workspace_modelling_hints(concept_model, drift_summary)
    overview_summary = _workspace_modelling_overview_summary(
        concept_model,
        mapping_decisions,
        session_state,
        upload_response=upload_response,
        mapping_response=mapping_response,
        drift_summary=drift_summary,
    )
    report_markdown = _workspace_build_mapping_report_markdown(
        concept_model,
        mapping_decisions,
        session_state,
        upload_response=upload_response,
        mapping_response=mapping_response,
        codegen_response=codegen_response,
    )
    session_state["workspace_concept_model"] = concept_model
    session_state["workspace_concept_model_drift_summary"] = drift_summary
    session_state["workspace_mapping_report_markdown"] = report_markdown
    if apply_col.button("Apply model hints to decisions", key="workspace_modelling_apply_hints", width="stretch"):
        session_state["workspace_modelling_pending_hints"] = hints
        session_state["last_action"] = {
            "level": "info",
            "message": (
                f"Prepared {len(hints)} modelling hint(s) for Decisions. "
                "This first slice keeps them read-only and does not mutate active mapping decisions."
            ),
        }
        st.rerun()

    st.subheader("BA Mapping Report")
    st.caption(
        "Report-first overview of the current workspace result. It synthesizes signals and outcomes across Setup, Review, Decisions, Output, and the concept model into one exportable narrative artifact."
    )
    try:
        from streamlit_ui.shared_views import render_reference_markdown

        render_reference_markdown(report_markdown)
    except Exception:
        st.markdown(report_markdown)

    with st.expander("Refine concept model and inspect diagnostics", expanded=False):
        left_col, right_col = st.columns([3, 2])
        with left_col:
            st.subheader("Concept Model")
            st.caption(
                "Derived-first conceptual contract for the current workspace result. Refine it only where the inferred model is incomplete or conceptually off."
            )
            st.text_input("Target object", key="workspace_modelling_object_name", placeholder="Customer master / Vendor master / Invoice header")
            st.text_area("Description", key="workspace_modelling_description", placeholder="What business object is this workspace building?", height=88)
            st.text_area("Business purpose", key="workspace_modelling_business_purpose", placeholder="Why does this target object exist and who uses it?", height=88)
            st.text_input("Target grain", key="workspace_modelling_target_grain", placeholder="One row per customer / order / invoice line")
            st.text_area(
                "Additional modeled attributes (one per line)",
                key="workspace_modelling_additional_attributes",
                placeholder="record_source\ncustomer_segment",
                height=104,
            )
            st.text_area(
                "Required modeled attributes (one per line)",
                key="workspace_modelling_required_attributes",
                placeholder="customer_id\nrecord_source",
                height=104,
            )
            st.text_area(
                "Business rules",
                key="workspace_modelling_business_rules",
                placeholder="Keep only active customers.\nDeduplicate by customer_id and keep the newest record.",
                height=120,
            )
            st.caption("Current modeled attributes")
            st.dataframe(
                [
                    {
                        "attribute": item.get("name"),
                        "group": item.get("group"),
                        "required": bool(item.get("required")),
                        "coverage": item.get("coverage_status"),
                        "decision type": _workspace_modelling_resolution_label(item.get("expected_resolution_type")),
                        "origin": item.get("origin"),
                    }
                    for item in concept_model.get("attributes") or []
                ],
                width="stretch",
                hide_index=True,
            )

        with right_col:
            st.subheader("Working Diagnostics")
            st.caption(f"Source: {concept_model.get('source_mode') or 'derived'}")
            top_metrics = st.columns(4)
            top_metrics[0].metric("Decisions", overview_summary["review_summary"]["active_decisions"])
            top_metrics[1].metric("Open review", overview_summary["review_summary"]["status_counts"]["needs_review"])
            top_metrics[2].metric("Excluded", overview_summary["review_summary"]["coverage_counts"]["excluded"])
            top_metrics[3].metric("Target managed", overview_summary["review_summary"]["coverage_counts"]["target_managed"])
            if hints:
                st.caption("Current modelling hints")
                for hint in hints:
                    st.write(f"- {hint}")
            else:
                st.info("No modelling hints are currently open for this workspace state.")

            if session_state.get("workspace_modelling_show_drift"):
                st.caption("Drift summary")
                if drift_summary.get("status") == "in_sync":
                    st.success("Concept model is aligned with the current workspace state.")
                else:
                    if drift_summary.get("modeled_but_unmapped"):
                        st.warning("Modeled but unmapped: " + ", ".join(drift_summary["modeled_but_unmapped"]))
                    if drift_summary.get("unmodeled_targets"):
                        st.warning("Mapped but unmodeled: " + ", ".join(drift_summary["unmodeled_targets"]))
                    if drift_summary.get("required_unresolved"):
                        st.warning("Required but unresolved: " + ", ".join(drift_summary["required_unresolved"]))
                    if drift_summary.get("resolution_mismatches"):
                        st.warning("Resolution mismatches: " + ", ".join(drift_summary["resolution_mismatches"]))

            pending_hints = session_state.get("workspace_modelling_pending_hints") or []
            if pending_hints:
                st.caption("Prepared for Decisions")
                for hint in pending_hints:
                    st.write(f"- {hint}")


def _workspace_transformation_target_fields(mapping_decisions: list[dict]) -> list[str]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for item in mapping_decisions:
        resolution_type = str(item.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
        if resolution_type in {"out_of_scope", "target_managed"}:
            continue
        target = str(item.get("target") or "").strip()
        if not target or target in seen_targets:
            continue
        seen_targets.add(target)
        targets.append(target)
    return targets


def _workspace_excluded_output_summary(mapping_decisions: list[dict]) -> str:
    counts = {"out_of_scope": 0, "target_managed": 0}
    for item in mapping_decisions:
        resolution_type = str(item.get("resolution_type") or "direct_mapping").strip().lower() or "direct_mapping"
        if resolution_type in counts:
            counts[resolution_type] += 1
    parts: list[str] = []
    if counts["out_of_scope"]:
        parts.append(f"N/A={counts['out_of_scope']}")
    if counts["target_managed"]:
        parts.append(f"Target managed={counts['target_managed']}")
    if not parts:
        return ""
    return "Excluded from generated output: " + ", ".join(parts)


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

    if selected_workspace_section == "Modelling Overview":
        mapping_decisions = build_mapping_decisions() if mapping_response else []
        _render_workspace_modelling_section(
            session_state=st.session_state,
            upload_response=upload_response,
            mapping_response=mapping_response,
            codegen_response=codegen_response,
            mapping_decisions=mapping_decisions,
        )

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
            excluded_output_summary = _workspace_excluded_output_summary(mapping_decisions)
            if canonical_output_mode:
                st.caption(
                    "Canonical mode supports code generation against canonical concept IDs, but preview stays unavailable because there is no concrete target dataset to materialize against."
                )
            if excluded_output_summary:
                st.caption(excluded_output_summary)
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