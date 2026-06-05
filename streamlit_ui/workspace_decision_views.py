"""Workspace decision and governance UI for durable mapping outcomes."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import streamlit as st

from streamlit_ui.governance import api_error_message, mapping_set_workspace_block_reason
from streamlit_ui.shared_views import render_status_badge_legend


def _saved_mapping_set_apply_block_reason(saved_mapping_set: dict) -> str:
    return mapping_set_workspace_block_reason(
        saved_mapping_set.get("status"),
        action_label="applied back into Workspace",
    )


def _mapping_set_status_guidance(status: str | None) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in {"approved", "archived"}:
        return (
            "Approved and archived are governance outcomes. This status control remains available here as a direct shortcut, "
            "but the primary home for approval is Governance > Stewardship."
        )
    return (
        "Draft and review are working states in Decisions. When the mapping set is ready for sign-off, continue in "
        "Governance > Stewardship for approval."
    )


def _open_mapping_set_governance_handoff(mapping_set: dict | None) -> None:
    current = mapping_set if isinstance(mapping_set, dict) else {}
    name = str(current.get("name") or "mapping set").strip() or "mapping set"
    version = int(current.get("version") or 0)
    status = str(current.get("status") or "draft").strip() or "draft"
    st.session_state["pending_top_level_area"] = "Governance"
    st.session_state["pending_governance_section"] = "Stewardship"
    st.session_state["last_action"] = {
        "level": "info",
        "message": (
            f"Opened Governance > Stewardship for '{name}'"
            f" version {version if version else '?'} (current status: {status}). "
            "Use that surface as the main approval path."
        ),
    }
    st.rerun()


def _section_label(title: str, detail: str | None = None) -> str:
    detail_text = str(detail or "").strip()
    return f"{title} · {detail_text}" if detail_text else title


def _draft_session_restore_section(section: str | None, draft_session_detail: dict | None = None) -> str:
    normalized = str(section or "").strip()
    if normalized == "Review":
        runtime = (draft_session_detail or {}).get("mapping_runtime") or {}
        if runtime:
            return "Review"
    if normalized == "Output":
        return "Output"
    if normalized == "Decisions":
        return "Decisions"
    return "Decisions"


def _normalized_api_base_url(value: str | None) -> str:
    return str(value or "").strip().rstrip("/")


def _active_draft_session() -> dict:
    current = st.session_state.get("active_draft_session") or {}
    return current if isinstance(current, dict) else {}


def _set_active_draft_session(draft_session: dict | None) -> None:
    current = dict(draft_session or {})
    draft_session_id = int(current.get("draft_session_id") or 0)
    if not draft_session_id:
        st.session_state.pop("active_draft_session", None)
        return
    st.session_state["active_draft_session"] = {
        "draft_session_id": draft_session_id,
        "name": str(current.get("name") or "draft-session").strip() or "draft-session",
        "created_by": current.get("created_by"),
        "workspace_id": current.get("workspace_id"),
        "version": int(current.get("version") or 1),
        "last_writer": current.get("last_writer"),
        "updated_at": current.get("updated_at"),
        "active_workspace_section": current.get("active_workspace_section") or "Decisions",
    }


def _draft_session_option_label(draft_session: dict) -> str:
    return (
        f"#{draft_session['draft_session_id']} | {draft_session['name']} | "
        f"{draft_session['active_workspace_section']} | {draft_session['source_dataset_name']}"
    )


def _resolve_selected_draft_session_id(
    saved_draft_sessions: list[dict],
    *,
    selection_key: str = "selected_draft_session_id",
) -> int:
    option_ids = [int(item.get("draft_session_id") or 0) for item in saved_draft_sessions if int(item.get("draft_session_id") or 0)]
    if not option_ids:
        return 0

    current_selected_id = int(st.session_state.get(selection_key) or 0)
    if current_selected_id in option_ids:
        return current_selected_id

    active_draft_id = int((_active_draft_session().get("draft_session_id") or 0))
    if active_draft_id in option_ids:
        st.session_state[selection_key] = active_draft_id
        return active_draft_id

    st.session_state[selection_key] = option_ids[0]
    return option_ids[0]


def _serialized_mapping_editor_state() -> dict[str, dict]:
    editor_state = st.session_state.get("mapping_editor_state") or {}
    return {
        str(source): {
            "target": str(entry.get("target") or ""),
            "status": str(entry.get("status") or "needs_review"),
            "suggested_target": str(entry.get("suggested_target") or ""),
            "suggested_transformation_code": str(entry.get("suggested_transformation_code") or ""),
            "manual_transformation_code": str(entry.get("manual_transformation_code") or ""),
            "llm_transformation_instruction": str(entry.get("llm_transformation_instruction") or ""),
            "manual_apply_transformation": bool(entry.get("manual_apply_transformation", False)),
            "manual": bool(entry.get("manual", False)),
            "llm_proposal_confidence": float(entry.get("llm_proposal_confidence", 0.0) or 0.0),
            "llm_proposal_origin": str(entry.get("llm_proposal_origin") or ""),
            "llm_proposal_target": str(entry.get("llm_proposal_target") or ""),
            "llm_proposal_status": str(entry.get("llm_proposal_status") or ""),
        }
        for source, entry in editor_state.items()
        if str(source or "").strip()
    }


def _current_review_state() -> dict:
    return {
        "status_filter": str(st.session_state.get("filter_status") or "All").strip() or "All",
        "confidence_filter": str(st.session_state.get("filter_confidence") or "All").strip() or "All",
        "source_filter": str(st.session_state.get("filter_source") or "All").strip() or "All",
        "canonical_concept_filter": str(st.session_state.get("filter_canonical_concept") or "All").strip() or "All",
    }


def _workspace_transformation_spec_has_content(spec: dict | None) -> bool:
    current_spec = spec if isinstance(spec, dict) else {}
    if any(str(current_spec.get(key) or "").strip() for key in ("target_grain", "global_rules", "defaults", "examples")):
        return True
    return any(str((item or {}).get("rule") or "").strip() for item in (current_spec.get("field_rules") or []))


def _workspace_transformation_spec_summary(spec: dict | None) -> dict:
    current_spec = spec if isinstance(spec, dict) else {}
    target_fields = [str(item).strip() for item in (current_spec.get("target_fields") or []) if str(item).strip()]
    target_grain = str(current_spec.get("target_grain") or "").strip()
    global_rules = str(current_spec.get("global_rules") or "").strip()
    defaults = str(current_spec.get("defaults") or "").strip()
    described_lookup = {
        str((item or {}).get("target_field") or "").strip()
        for item in (current_spec.get("field_rules") or [])
        if str((item or {}).get("target_field") or "").strip() and str((item or {}).get("rule") or "").strip()
    }
    missing_fields = [target_field for target_field in target_fields if target_field not in described_lookup]

    if not target_fields:
        return {
            "state": "invalid",
            "title": "No active target fields",
            "message": "Add at least one active mapping decision before drafting a transformation spec.",
            "missing_fields": [],
            "described_count": 0,
            "target_count": 0,
        }
    if not target_grain:
        return {
            "state": "incomplete",
            "title": "Missing target grain",
            "message": "Describe the target grain before using this transformation design as a governed output contract.",
            "missing_fields": missing_fields,
            "described_count": len(described_lookup),
            "target_count": len(target_fields),
        }
    if not described_lookup and not global_rules and not defaults:
        return {
            "state": "incomplete",
            "title": "Add transformation rules",
            "message": "Define at least one field rule, global rule, or default behavior before this spec is ready.",
            "missing_fields": missing_fields,
            "described_count": 0,
            "target_count": len(target_fields),
        }
    if missing_fields and not defaults:
        return {
            "state": "incomplete",
            "title": "Field coverage is incomplete",
            "message": "Add explicit rules for the remaining target fields or define default behavior.",
            "missing_fields": missing_fields,
            "described_count": len(described_lookup),
            "target_count": len(target_fields),
        }
    return {
        "state": "ready",
        "title": "Ready for next output step",
        "message": (
            f"Structured spec covers {len(described_lookup)} of {len(target_fields)} target field(s)"
            + (" with explicit defaults for the rest." if missing_fields else ".")
        ),
        "missing_fields": missing_fields,
        "described_count": len(described_lookup),
        "target_count": len(target_fields),
    }


def _draft_session_resume_transformation_message(draft_session_detail: dict) -> str:
    transformation_spec = dict(draft_session_detail.get("transformation_spec") or {})
    if not _workspace_transformation_spec_has_content(transformation_spec):
        return ""
    summary = _workspace_transformation_spec_summary(transformation_spec)
    title = str(summary.get("title") or "Transformation Design restored").strip()
    message = str(summary.get("message") or "").strip()
    return f" Transformation Design restored: {title}. {message}".rstrip()


def _draft_session_resume_output_message(draft_session_detail: dict) -> str:
    output_state = dict(draft_session_detail.get("output_state") or {})
    restored_labels: list[str] = []
    if isinstance(output_state.get("preview_response"), dict) and output_state.get("preview_response"):
        restored_labels.append("preview snapshot")
    if isinstance(output_state.get("codegen_refinement_response"), dict) and output_state.get("codegen_refinement_response"):
        restored_labels.append("refined artifact")
    elif isinstance(output_state.get("codegen_response"), dict) and output_state.get("codegen_response"):
        restored_labels.append("generated artifact")
    if isinstance(output_state.get("mapping_analysis_summary"), dict) and output_state.get("mapping_analysis_summary"):
        restored_labels.append("mapping analysis")
    if str(output_state.get("mapping_analysis_spoken_script") or "").strip():
        restored_labels.append("narration script")
    if not restored_labels:
        return ""
    return f" Output snapshot restored: {', '.join(restored_labels)}."


def _serialized_draft_session_output_state() -> dict:
    output_state: dict[str, object] = {}

    preview_response = st.session_state.get("preview_response")
    if isinstance(preview_response, dict) and preview_response:
        output_state["preview_response"] = dict(preview_response)

    codegen_response = st.session_state.get("codegen_response")
    if isinstance(codegen_response, dict) and codegen_response:
        output_state["codegen_response"] = dict(codegen_response)

    codegen_refinement_response = st.session_state.get("codegen_refinement_response")
    if isinstance(codegen_refinement_response, dict) and codegen_refinement_response:
        output_state["codegen_refinement_response"] = dict(codegen_refinement_response)

    mapping_analysis_summary = st.session_state.get("mapping_analysis_summary")
    if isinstance(mapping_analysis_summary, dict) and mapping_analysis_summary:
        output_state["mapping_analysis_summary"] = dict(mapping_analysis_summary)

    mapping_analysis_spoken_script = str(st.session_state.get("mapping_analysis_spoken_script") or "").strip()
    if mapping_analysis_spoken_script:
        output_state["mapping_analysis_spoken_script"] = mapping_analysis_spoken_script

    return output_state


def _serialized_workspace_transformation_spec() -> dict:
    current_spec = st.session_state.get("workspace_transformation_spec") or {}
    if not isinstance(current_spec, dict) or not _workspace_transformation_spec_has_content(current_spec):
        return {}
    return {
        "target_grain": str(current_spec.get("target_grain") or "").strip(),
        "global_rules": str(current_spec.get("global_rules") or "").strip(),
        "defaults": str(current_spec.get("defaults") or "").strip(),
        "examples": str(current_spec.get("examples") or "").strip(),
        "target_fields": [
            str(item).strip()
            for item in (current_spec.get("target_fields") or [])
            if str(item).strip()
        ],
        "field_rules": [
            {
                "target_field": str((item or {}).get("target_field") or "").strip(),
                "rule": str((item or {}).get("rule") or "").strip(),
            }
            for item in (current_spec.get("field_rules") or [])
            if str((item or {}).get("target_field") or "").strip() and str((item or {}).get("rule") or "").strip()
        ],
    }


def _apply_draft_session_transformation_spec(draft_session_detail: dict) -> None:
    transformation_spec = dict(draft_session_detail.get("transformation_spec") or {})
    if not _workspace_transformation_spec_has_content(transformation_spec):
        return

    st.session_state["workspace_transformation_target_grain"] = str(transformation_spec.get("target_grain") or "").strip()
    st.session_state["workspace_transformation_global_rules"] = str(transformation_spec.get("global_rules") or "").strip()
    st.session_state["workspace_transformation_defaults"] = str(transformation_spec.get("defaults") or "").strip()
    st.session_state["workspace_transformation_examples"] = str(transformation_spec.get("examples") or "").strip()
    for key in list(st.session_state.keys()):
        if str(key).startswith("workspace_transformation_rule::"):
            st.session_state.pop(key, None)
    for item in transformation_spec.get("field_rules") or []:
        target_field = str((item or {}).get("target_field") or "").strip()
        rule = str((item or {}).get("rule") or "").strip()
        if target_field and rule:
            st.session_state[f"workspace_transformation_rule::{target_field}"] = rule
    st.session_state["workspace_transformation_spec"] = transformation_spec
    summary = _workspace_transformation_spec_summary(transformation_spec)
    st.session_state["workspace_transformation_spec_status"] = str(summary.get("state") or "").strip()
    st.session_state["workspace_transformation_spec_summary"] = summary


def _workspace_target_context_for_save(upload_response: dict, mapping_response: dict, mapping_mode: str) -> dict:
    runtime = dict(mapping_response.get("mapping_runtime") or {})
    target_system = str(upload_response.get("target_system") or runtime.get("target_system") or "").strip().lower() or None
    if mapping_mode == "canonical" and not target_system:
        target_system = "canonical"

    target_projection_mode = str(runtime.get("target_projection_mode") or "").strip() or "dataset_to_dataset"
    if mapping_mode == "canonical" and target_projection_mode == "dataset_to_dataset":
        target_projection_mode = "canonical_only" if target_system == "canonical" else "target_aware_canonical"

    return {
        "target_system": target_system,
        "target_profile": str(runtime.get("target_profile") or "").strip() or None,
        "target_projection_mode": target_projection_mode,
        "artifact_type": "canonical-only" if mapping_mode == "canonical" else "standard",
    }


def _draft_session_target_context(draft_session_detail: dict) -> dict:
    saved_context = dict(draft_session_detail.get("workspace_target_context") or {})
    runtime = dict(draft_session_detail.get("mapping_runtime") or {})
    target_system = (
        str(
            saved_context.get("target_system")
            or draft_session_detail.get("canonical_target_system")
            or runtime.get("target_system")
            or ""
        ).strip().lower()
        or None
    )
    target_projection_mode = str(
        saved_context.get("target_projection_mode") or runtime.get("target_projection_mode") or ""
    ).strip() or "dataset_to_dataset"
    if str(draft_session_detail.get("mapping_mode") or "standard").strip().lower() == "canonical" and target_projection_mode == "dataset_to_dataset":
        target_projection_mode = "canonical_only" if target_system in (None, "canonical") else "target_aware_canonical"

    return {
        "target_system": target_system,
        "target_profile": str(saved_context.get("target_profile") or runtime.get("target_profile") or "").strip() or None,
        "target_projection_mode": target_projection_mode,
        "artifact_type": str(saved_context.get("artifact_type") or ("canonical-only" if target_system else "standard")).strip() or "standard",
    }


def _draft_session_identity_query_params(draft_session: dict | None = None) -> dict[str, str]:
    current = draft_session or _active_draft_session()
    params: dict[str, str] = {}
    if str(current.get("created_by") or "").strip():
        params["created_by"] = str(current.get("created_by")).strip()
    if str(current.get("workspace_id") or "").strip():
        params["workspace_id"] = str(current.get("workspace_id")).strip()
    return params


def _draft_session_stale_write_detail(error: httpx.HTTPError) -> dict | None:
    response = getattr(error, "response", None)
    if response is None or response.status_code != 409:
        return None
    try:
        detail = response.json().get("detail")
    except Exception:
        return None
    return detail if isinstance(detail, dict) and detail.get("detail_code") == "stale_write" else None


def _active_draft_session_caption() -> str:
    active_draft = _active_draft_session()
    if not active_draft:
        return "No active draft session. Save or resume a draft session first to persist shared review/decision state."
    return (
        f"Active draft session: #{active_draft['draft_session_id']} | {active_draft['name']} | "
        f"v{active_draft['version']} | last_writer={active_draft.get('last_writer') or 'n/a'}"
    )


def _reload_active_draft_after_stale(api_request, *, stale_detail: dict | None) -> tuple[dict, str]:
    active_draft = _active_draft_session()
    draft_session_id = int(active_draft.get("draft_session_id") or 0)
    if not draft_session_id:
        raise ValueError("No active draft session is selected for stale reload.")

    latest_detail = api_request(
        "GET",
        f"/mapping/draft-sessions/{draft_session_id}",
        params=_draft_session_identity_query_params(active_draft),
    )
    restored_section = _apply_draft_session_detail_to_workspace(latest_detail)
    _set_active_draft_session(latest_detail)
    st.session_state["saved_draft_sessions"] = api_request("GET", "/mapping/draft-sessions")
    st.session_state["last_action"] = {
        "level": "warning",
        "message": (
            f"Draft session '{latest_detail['name']}' changed on the backend "
            f"(expected v{(stale_detail or {}).get('expected_version') or active_draft.get('version')}, "
            f"current v{latest_detail.get('version')}). Reloaded latest backend state into Workspace {restored_section}; "
            "re-apply your local changes before saving again."
        ),
    }
    return latest_detail, restored_section


def _schema_column_names_from_handle(handle: dict | None) -> list[str]:
    return [
        str((column or {}).get("name") or "").strip()
        for column in ((handle or {}).get("schema_profile") or {}).get("columns", [])
        if str((column or {}).get("name") or "").strip()
    ]


def _draft_session_restore_conflict_reason(draft_session_detail: dict) -> str:
    saved_base_url = _normalized_api_base_url(draft_session_detail.get("api_base_url"))
    current_base_url = _normalized_api_base_url(
        st.session_state.get("api_base_url") or st.session_state.get("active_api_base_url")
    )
    if saved_base_url and current_base_url and saved_base_url != current_base_url:
        return (
            f"Draft session targets API base URL {saved_base_url}, but the active workspace uses {current_base_url}. "
            "Switch API Base URL first, then retry resume."
        )

    current_upload = st.session_state.get("upload_response") or {}
    if not current_upload:
        return ""

    saved_mode = str(draft_session_detail.get("mapping_mode") or "standard").strip().lower() or "standard"
    current_mode = str(current_upload.get("mapping_mode") or "standard").strip().lower() or "standard"
    if saved_mode != current_mode:
        return (
            f"Draft session was saved in {saved_mode} mode, but the active workspace is in {current_mode} mode. "
            "Clear the current workspace context before resuming this draft."
        )

    current_source_columns = _schema_column_names_from_handle(current_upload.get("source"))
    saved_source_columns = _schema_column_names_from_handle(draft_session_detail.get("source_handle"))
    if current_source_columns and saved_source_columns and current_source_columns != saved_source_columns:
        return "Draft session source schema does not match the active workspace source schema. Clear the current workspace before resuming this draft."

    if saved_mode == "canonical":
        current_target_system = str(current_upload.get("target_system") or "canonical").strip().lower() or "canonical"
        saved_target_system = _draft_session_target_context(draft_session_detail).get("target_system") or "canonical"
        if current_target_system != saved_target_system:
            return (
                f"Draft session targets canonical system {saved_target_system}, but the active workspace uses {current_target_system}. "
                "Clear the current workspace before resuming this draft."
            )
        return ""

    current_target_columns = _schema_column_names_from_handle(current_upload.get("target"))
    saved_target_columns = _schema_column_names_from_handle(draft_session_detail.get("target_handle"))
    if current_target_columns and saved_target_columns and current_target_columns != saved_target_columns:
        return "Draft session target schema does not match the active workspace target schema. Clear the current workspace before resuming this draft."
    return ""


def _draft_session_confidence_label(confidence: float) -> str:
    if confidence >= 0.85:
        return "high_confidence"
    if confidence >= 0.65:
        return "medium_confidence"
    return "low_confidence"


def _build_draft_session_request_payload(name: str) -> dict:
    upload_response = st.session_state.get("upload_response")
    if not upload_response:
        raise ValueError("Load a workspace dataset context before saving a draft session.")

    editor_state = st.session_state.get("mapping_editor_state") or {}
    if not editor_state:
        raise ValueError("Draft session save requires an active mapping editor state.")

    mapping_mode = str(upload_response.get("mapping_mode") or "standard").strip().lower() or "standard"
    target_handle = upload_response.get("target") if mapping_mode != "canonical" else None
    mapping_response = st.session_state.get("mapping_response") or {}
    return {
        "name": name,
        "api_base_url": _normalized_api_base_url(
            st.session_state.get("api_base_url") or st.session_state.get("active_api_base_url")
        ),
        "mapping_mode": mapping_mode,
        "active_workspace_section": str(st.session_state.get("active_workspace_section") or "Decisions").strip() or "Decisions",
        "source_handle": upload_response["source"],
        "target_handle": target_handle,
        "canonical_target_system": upload_response.get("target_system") if mapping_mode == "canonical" else None,
        "workspace_target_context": _workspace_target_context_for_save(upload_response, mapping_response, mapping_mode),
        "review_state": _current_review_state(),
        "mapping_runtime": dict(mapping_response.get("mapping_runtime") or {}),
        "mapping_editor_state": _serialized_mapping_editor_state(),
        "mapping_decision_audit": _decision_audit_map(),
        "transformation_spec": _serialized_workspace_transformation_spec(),
        "output_state": _serialized_draft_session_output_state(),
    }


def _build_draft_session_mapping_response(draft_session_detail: dict) -> dict:
    source_handle = draft_session_detail.get("source_handle") or {}
    target_handle = draft_session_detail.get("target_handle") or {}
    mapping_mode = str(draft_session_detail.get("mapping_mode") or "standard").strip().lower() or "standard"
    editor_state = draft_session_detail.get("mapping_editor_state") or {}
    mapping_runtime = dict(draft_session_detail.get("mapping_runtime") or {})
    target_context = _draft_session_target_context(draft_session_detail)
    if target_context.get("target_system") and not mapping_runtime.get("target_system"):
        mapping_runtime["target_system"] = target_context["target_system"]
    if target_context.get("target_profile") and not mapping_runtime.get("target_profile"):
        mapping_runtime["target_profile"] = target_context["target_profile"]
    if target_context.get("target_projection_mode") and not mapping_runtime.get("target_projection_mode"):
        mapping_runtime["target_projection_mode"] = target_context["target_projection_mode"]

    mappings: list[dict] = []
    ranked_mappings: list[dict] = []
    matched_sources = 0
    canonical_concepts: list[str] = []

    for column in (source_handle.get("schema_profile") or {}).get("columns", []):
        source = str((column or {}).get("name") or "").strip()
        if not source:
            continue
        entry = editor_state.get(source) or {}
        target = str(entry.get("target") or "").strip()
        status = str(entry.get("status") or "needs_review").strip() or "needs_review"
        transformation_code = str(entry.get("manual_transformation_code") or "").strip()
        confidence = 0.95 if target and status == "accepted" else 0.7 if target else 0.35
        selected = {
            "target": target,
            "status": status,
            "confidence": confidence,
            "confidence_label": _draft_session_confidence_label(confidence),
            "method": "draft_restore",
            "explanation": [f"Restored from draft session '{draft_session_detail.get('name') or 'draft-session'}'."],
            "signals": {
                "name": 0.0,
                "semantic": 0.0,
                "knowledge": 0.0,
                "canonical": 1.0 if mapping_mode == "canonical" and target else 0.0,
                "pattern": 0.0,
                "statistical": 0.0,
                "overlap": 0.0,
                "embedding": 0.0,
                "correction": 0.0,
                "llm": 0.0,
            },
            "canonical_details": {"source_concepts": [], "target_concepts": [], "shared_concepts": []},
        }
        if transformation_code:
            selected["transformation_code"] = transformation_code
        if target:
            matched_sources += 1
            if mapping_mode == "canonical" and target not in canonical_concepts:
                canonical_concepts.append(target)
        ranked_mappings.append(
            {
                "source": source,
                "selected": selected if target else {},
                "candidates": [selected] if target else [],
            }
        )
        if target:
            mappings.append({**selected, "source": source})

    target_columns = ((target_handle.get("schema_profile") or {}).get("columns") or []) if mapping_mode != "canonical" else []
    target_total = len(target_columns) if mapping_mode != "canonical" else len(canonical_concepts)
    source_total = len((source_handle.get("schema_profile") or {}).get("columns") or [])
    source_ratio = (matched_sources / source_total) if source_total else 0.0
    distinct_targets = len({item.get("target") for item in mappings if item.get("target")})
    target_ratio = (distinct_targets / target_total) if target_total else 0.0

    return {
        "mappings": mappings,
        "ranked_mappings": ranked_mappings,
        "mapping_runtime": mapping_runtime,
        "canonical_coverage": {
            "source": {
                "coverage_ratio": source_ratio,
                "matched_columns": matched_sources,
                "total_columns": source_total,
                "unmatched_columns": [
                    ranked["source"] for ranked in ranked_mappings if not (ranked.get("selected") or {}).get("target")
                ],
            },
            "target": {
                "coverage_ratio": target_ratio,
                "matched_columns": distinct_targets,
                "total_columns": target_total,
            },
            "project": {
                "coverage_ratio": 1.0 if canonical_concepts else target_ratio,
                "matched_columns": len(canonical_concepts) if canonical_concepts else distinct_targets,
                "total_columns": len(canonical_concepts) if canonical_concepts else target_total,
                "concept_count": len(canonical_concepts),
                "shared_concept_count": len(canonical_concepts),
                "concepts": canonical_concepts,
            },
        },
    }


def _reset_draft_session_transient_outputs() -> None:
    for key in (
        "preview_response",
        "codegen_response",
        "codegen_refinement_response",
        "mapping_analysis_summary",
        "mapping_analysis_error",
        "mapping_analysis_spoken_script",
        "mapping_analysis_audio_bytes",
        "mapping_analysis_audio_mime_type",
        "mapping_analysis_audio_error",
        "review_plan_summary",
        "review_plan_error",
        "canonical_gap_candidates",
        "canonical_gap_suggestions",
        "canonical_gap_triage_summary",
        "canonical_gap_triage_error",
        "llm_decision_proposals",
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
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith("workspace_transformation_rule::"):
            st.session_state.pop(key, None)


def _apply_draft_session_output_state(draft_session_detail: dict) -> None:
    output_state = dict(draft_session_detail.get("output_state") or {})

    preview_response = output_state.get("preview_response")
    if isinstance(preview_response, dict) and preview_response:
        st.session_state["preview_response"] = dict(preview_response)

    codegen_response = output_state.get("codegen_response")
    if isinstance(codegen_response, dict) and codegen_response:
        st.session_state["codegen_response"] = dict(codegen_response)

    codegen_refinement_response = output_state.get("codegen_refinement_response")
    if isinstance(codegen_refinement_response, dict) and codegen_refinement_response:
        st.session_state["codegen_refinement_response"] = dict(codegen_refinement_response)

    mapping_analysis_summary = output_state.get("mapping_analysis_summary")
    if isinstance(mapping_analysis_summary, dict) and mapping_analysis_summary:
        st.session_state["mapping_analysis_summary"] = dict(mapping_analysis_summary)

    mapping_analysis_spoken_script = str(output_state.get("mapping_analysis_spoken_script") or "").strip()
    if mapping_analysis_spoken_script:
        st.session_state["mapping_analysis_spoken_script"] = mapping_analysis_spoken_script


def _apply_draft_session_review_state(draft_session_detail: dict) -> None:
    review_state = dict(draft_session_detail.get("review_state") or {})
    st.session_state["filter_status"] = str(review_state.get("status_filter") or "All").strip() or "All"
    st.session_state["filter_confidence"] = str(review_state.get("confidence_filter") or "All").strip() or "All"
    st.session_state["filter_source"] = str(review_state.get("source_filter") or "All").strip() or "All"
    st.session_state["filter_canonical_concept"] = str(review_state.get("canonical_concept_filter") or "All").strip() or "All"


def _apply_draft_session_detail_to_workspace(draft_session_detail: dict) -> str:
    conflict_reason = _draft_session_restore_conflict_reason(draft_session_detail)
    if conflict_reason:
        raise ValueError(conflict_reason)

    mapping_mode = str(draft_session_detail.get("mapping_mode") or "standard").strip().lower() or "standard"
    source_handle = draft_session_detail.get("source_handle")
    if not source_handle:
        raise KeyError("Draft session is missing source_handle.")

    upload_response = {
        "source": source_handle,
        "mapping_mode": mapping_mode,
    }
    if mapping_mode == "canonical":
        upload_response["target_system"] = _draft_session_target_context(draft_session_detail).get("target_system") or "canonical"
    else:
        target_handle = draft_session_detail.get("target_handle")
        if not target_handle:
            raise KeyError("Standard draft session is missing target_handle.")
        upload_response["target"] = target_handle

    st.session_state["upload_response"] = upload_response
    st.session_state["mapping_mode"] = "Canonical" if mapping_mode == "canonical" else "Standard"
    if mapping_mode == "canonical":
        st.session_state["canonical_target_system"] = upload_response["target_system"]
    st.session_state["mapping_response"] = _build_draft_session_mapping_response(draft_session_detail)
    st.session_state["mapping_editor_state"] = dict(draft_session_detail.get("mapping_editor_state") or {})
    st.session_state["mapping_decision_audit"] = dict(draft_session_detail.get("mapping_decision_audit") or {})
    _apply_draft_session_review_state(draft_session_detail)
    _set_active_draft_session(draft_session_detail)
    restore_section = _draft_session_restore_section(
        draft_session_detail.get("active_workspace_section"),
        draft_session_detail,
    )
    st.session_state["pending_top_level_area"] = "Workspace"
    st.session_state["pending_workspace_section"] = restore_section
    _reset_draft_session_transient_outputs()
    _apply_draft_session_transformation_spec(draft_session_detail)
    _apply_draft_session_output_state(draft_session_detail)
    return restore_section


def _decision_audit_map() -> dict[str, dict]:
    current = st.session_state.get("mapping_decision_audit") or {}
    if isinstance(current, dict):
        return current
    return {}


def _record_decision_audit(source: str, *, origin: str, details: dict | None = None) -> None:
    source_name = str(source or "").strip()
    if not source_name:
        return
    audit_map = _decision_audit_map()
    audit_map[source_name] = {
        "origin": str(origin or "manual").strip() or "manual",
        "applied_at": datetime.now(UTC).isoformat(),
        "details": dict(details or {}),
    }
    st.session_state["mapping_decision_audit"] = audit_map


def _build_draft_session_decision_state_payload() -> dict:
    active_draft = _active_draft_session()
    if not active_draft:
        raise ValueError("Save or resume a draft session before persisting decisions.")
    return {
        "created_by": active_draft.get("created_by"),
        "workspace_id": active_draft.get("workspace_id"),
        "expected_version": int(active_draft.get("version") or 1),
        "last_writer": active_draft.get("created_by") or active_draft.get("last_writer"),
        "active_workspace_section": str(st.session_state.get("active_workspace_section") or "Decisions").strip() or "Decisions",
        "mapping_editor_state": _serialized_mapping_editor_state(),
        "mapping_decision_audit": _decision_audit_map(),
        "transformation_spec": _serialized_workspace_transformation_spec(),
        "output_state": _serialized_draft_session_output_state(),
    }


def _build_draft_session_review_state_payload() -> dict:
    active_draft = _active_draft_session()
    if not active_draft:
        raise ValueError("Save or resume a draft session before persisting review state.")
    return {
        "created_by": active_draft.get("created_by"),
        "workspace_id": active_draft.get("workspace_id"),
        "expected_version": int(active_draft.get("version") or 1),
        "last_writer": active_draft.get("created_by") or active_draft.get("last_writer"),
        "active_workspace_section": "Review",
        "review_state": _current_review_state(),
    }


def render_active_draft_review_state_panel(*, api_request) -> None:
    with st.expander(_section_label("Draft Review State", "shared persistence"), expanded=False):
        st.caption(_active_draft_session_caption())
        active_draft = _active_draft_session()
        if not active_draft:
            st.info("Create or resume a draft session in Decisions before saving review filters and section context.")
            return
        if st.button("Save review state to active draft", width="stretch", key="save_review_state_to_active_draft"):
            try:
                updated_detail = api_request(
                    "PUT",
                    f"/mapping/draft-sessions/{active_draft['draft_session_id']}/review-state",
                    json=_build_draft_session_review_state_payload(),
                )
                _set_active_draft_session(updated_detail)
                st.session_state["saved_draft_sessions"] = api_request("GET", "/mapping/draft-sessions")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": (
                        f"Saved review state to draft session '{updated_detail['name']}' "
                        f"(v{updated_detail['version']})."
                    ),
                }
                st.rerun()
            except ValueError as error:
                st.session_state["last_action"] = {"level": "error", "message": str(error)}
                st.rerun()
            except httpx.HTTPError as error:
                stale_detail = _draft_session_stale_write_detail(error)
                if stale_detail:
                    try:
                        _reload_active_draft_after_stale(api_request, stale_detail=stale_detail)
                    except (ValueError, httpx.HTTPError) as reload_error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": api_error_message(reload_error, default_prefix="Reloading stale draft session failed"),
                        }
                    st.rerun()
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": api_error_message(error, default_prefix="Saving review state failed"),
                }
                st.rerun()


def render_active_draft_decision_state_panel(*, api_request) -> None:
    with st.expander(_section_label("Draft Decision State", "shared persistence"), expanded=False):
        st.caption(_active_draft_session_caption())
        active_draft = _active_draft_session()
        if not active_draft:
            st.info("Create or resume a draft session below before saving active decisions back to the backend.")
            return
        if st.button("Save decisions to active draft", width="stretch", key="save_decisions_to_active_draft"):
            try:
                updated_detail = api_request(
                    "PUT",
                    f"/mapping/draft-sessions/{active_draft['draft_session_id']}/decision-state",
                    json=_build_draft_session_decision_state_payload(),
                )
                _set_active_draft_session(updated_detail)
                st.session_state["saved_draft_sessions"] = api_request("GET", "/mapping/draft-sessions")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": (
                        f"Saved active decisions to draft session '{updated_detail['name']}' "
                        f"(v{updated_detail['version']})."
                    ),
                }
                st.rerun()
            except ValueError as error:
                st.session_state["last_action"] = {"level": "error", "message": str(error)}
                st.rerun()
            except httpx.HTTPError as error:
                stale_detail = _draft_session_stale_write_detail(error)
                if stale_detail:
                    try:
                        _reload_active_draft_after_stale(api_request, stale_detail=stale_detail)
                    except (ValueError, httpx.HTTPError) as reload_error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": api_error_message(reload_error, default_prefix="Reloading stale draft session failed"),
                        }
                    st.rerun()
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": api_error_message(error, default_prefix="Saving decision state failed"),
                }
                st.rerun()


def _active_decision_rows_with_audit(decisions: list[dict]) -> list[dict]:
    audit_map = _decision_audit_map()
    rows: list[dict] = []
    for decision in decisions:
        source = str(decision.get("source") or "").strip()
        audit = audit_map.get(source) or {}
        row = dict(decision)
        row["decision_origin"] = str(audit.get("origin") or "manual_or_imported")
        row["decision_origin_at"] = str(audit.get("applied_at") or "")
        rows.append(row)
    return rows


def _apply_llm_decision_proposal(editor_state: dict, proposal: dict) -> bool:
    source = str(proposal.get("source") or "").strip()
    if not source:
        return False

    current_entry = editor_state.setdefault(source, {})
    expected_target = str(proposal.get("current_target") or "").strip()
    expected_status = str(proposal.get("current_status") or "needs_review").strip().lower() or "needs_review"
    actual_target = str(current_entry.get("target") or "").strip()
    actual_status = str(current_entry.get("status") or "needs_review").strip().lower() or "needs_review"
    if actual_target and expected_target and actual_target != expected_target:
        return False
    if actual_status != expected_status:
        return False

    proposal_type = str(proposal.get("proposal_type") or "").strip()
    proposal_confidence = float(proposal.get("confidence", 0.0) or 0.0)
    proposal_origin = str(proposal.get("origin") or "llm_proposal")
    if proposal_type == "switch_target":
        current_entry["target"] = str(proposal.get("proposed_target") or "").strip()
        current_entry["status"] = "accepted"
        current_entry["llm_proposal_confidence"] = proposal_confidence
        current_entry["llm_proposal_origin"] = proposal_origin
        current_entry["llm_proposal_target"] = current_entry["target"]
        current_entry["llm_proposal_status"] = current_entry["status"]
        _record_decision_audit(
            source,
            origin="llm_proposal",
            details={
                "mode": "switch_target",
                "proposal_origin": proposal_origin,
                "confidence": proposal_confidence,
            },
        )
        return bool(current_entry.get("target"))
    if proposal_type == "accept_current":
        if not actual_target and expected_target:
            current_entry["target"] = expected_target
        current_entry["status"] = "accepted"
        current_entry["llm_proposal_confidence"] = proposal_confidence
        current_entry["llm_proposal_origin"] = proposal_origin
        current_entry["llm_proposal_target"] = str(current_entry.get("target") or "")
        current_entry["llm_proposal_status"] = current_entry["status"]
        _record_decision_audit(
            source,
            origin="llm_proposal",
            details={
                "mode": "accept_current",
                "proposal_origin": proposal_origin,
                "confidence": proposal_confidence,
            },
        )
        return bool(current_entry.get("target"))
    if proposal_type == "reject":
        if not actual_target and expected_target:
            current_entry["target"] = expected_target
        current_entry["status"] = "rejected"
        current_entry["llm_proposal_confidence"] = proposal_confidence
        current_entry["llm_proposal_origin"] = proposal_origin
        current_entry["llm_proposal_target"] = str(current_entry.get("target") or "")
        current_entry["llm_proposal_status"] = current_entry["status"]
        _record_decision_audit(
            source,
            origin="llm_proposal",
            details={
                "mode": "reject",
                "proposal_origin": proposal_origin,
                "confidence": proposal_confidence,
            },
        )
        return True
    return False


def _render_llm_decision_proposals_panel() -> None:
    proposals = st.session_state.get("llm_decision_proposals") or []
    with st.expander(
        _section_label("LLM Decision Proposals", f"{len(proposals)} pending" if proposals else None),
        expanded=bool(proposals),
    ):
        st.caption(
            "These proposals are advisory outputs derived from the current bounded LLM validation/refine evidence for `needs_review` rows. "
            "Applying a proposal updates the active review state and removes the cached proposal."
        )
        if not proposals:
            st.info("No pending decision proposals. Generate them from the Review tab for the current needs-review slice.")
            return

        st.dataframe(
            [
                {
                    "source": proposal.get("source"),
                    "current_target": proposal.get("current_target") or "unmapped",
                    "action": proposal.get("proposal_type"),
                    "proposed_target": proposal.get("proposed_target") or "unmapped",
                    "confidence": round(float(proposal.get("confidence", 0.0) or 0.0) * 100),
                    "origin": proposal.get("origin"),
                    "safe_to_apply": "yes" if proposal.get("safe_to_apply") else "no",
                }
                for proposal in proposals
            ],
            width="stretch",
            hide_index=True,
        )

        safe_proposals = [proposal for proposal in proposals if proposal.get("safe_to_apply")]
        if st.button(
            "Apply safe proposals",
            key="apply_safe_llm_decision_proposals",
            width="stretch",
            disabled=not safe_proposals,
        ):
            editor_state = st.session_state.setdefault("mapping_editor_state", {})
            applied_sources: list[str] = []
            remaining_proposals: list[dict] = []
            for proposal in proposals:
                if proposal.get("safe_to_apply") and _apply_llm_decision_proposal(editor_state, proposal):
                    applied_sources.append(str(proposal.get("source") or ""))
                    continue
                remaining_proposals.append(proposal)
            st.session_state["mapping_editor_state"] = editor_state
            st.session_state["llm_decision_proposals"] = remaining_proposals
            if applied_sources:
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Applied {len(applied_sources)} safe LLM proposal(s): {', '.join(applied_sources)}.",
                }
            else:
                st.session_state["last_action"] = {
                    "level": "warning",
                    "message": "No safe LLM proposals were applied. The workspace state may have changed; regenerate proposals from Review.",
                }
            st.rerun()

        proposal_sources = [str(proposal.get("source") or "") for proposal in proposals]
        selected_source = st.selectbox("Proposal source", proposal_sources, key="llm_decision_proposal_source")
        selected_proposal = next((proposal for proposal in proposals if proposal.get("source") == selected_source), None) or {}
        if selected_proposal:
            st.write(f"**Summary:** {selected_proposal.get('summary') or 'LLM proposed a follow-up decision for this review item.'}")
            st.caption(
                f"Action: {selected_proposal.get('proposal_type')} | "
                f"Current target: {selected_proposal.get('current_target') or 'unmapped'} | "
                f"Proposed target: {selected_proposal.get('proposed_target') or 'unmapped'} | "
                f"Confidence: {round(float(selected_proposal.get('confidence', 0.0) or 0.0) * 100)}%"
            )
            st.caption(selected_proposal.get("safe_reason") or "")
            for line in selected_proposal.get("reasoning") or []:
                st.write(f"- {line}")

            action_columns = st.columns(2)
            if action_columns[0].button("Apply selected proposal", key="apply_selected_llm_decision_proposal", width="stretch"):
                editor_state = st.session_state.setdefault("mapping_editor_state", {})
                if _apply_llm_decision_proposal(editor_state, selected_proposal):
                    st.session_state["mapping_editor_state"] = editor_state
                    st.session_state["llm_decision_proposals"] = [
                        proposal for proposal in proposals if proposal.get("source") != selected_source
                    ]
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Applied the LLM decision proposal for {selected_source}.",
                    }
                else:
                    st.session_state["last_action"] = {
                        "level": "warning",
                        "message": f"Could not apply the LLM proposal for {selected_source}. Regenerate proposals from Review because the row changed.",
                    }
                st.rerun()
            if action_columns[1].button("Dismiss selected proposal", key="dismiss_selected_llm_decision_proposal", width="stretch"):
                st.session_state["llm_decision_proposals"] = [
                    proposal for proposal in proposals if proposal.get("source") != selected_source
                ]
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": f"Dismissed the cached LLM decision proposal for {selected_source}.",
                }
                st.rerun()


def render_manual_mapping_panel(
    mapping_response: dict,
    *,
    schema_column_names,
    build_mapping_decisions,
    upsert_manual_mapping,
    manual_mapping_rows,
    remove_manual_mapping,
    list_canonical_target_fields,
) -> None:
    """Render manual mapping add/remove controls on top of the current mapping response."""

    upload_response = st.session_state.get("upload_response")
    if not upload_response:
        return

    mapping_mode = str(upload_response.get("mapping_mode") or "standard").strip().lower() or "standard"
    source_columns = schema_column_names(upload_response["source"])
    if mapping_mode == "canonical":
        try:
            target_columns = list_canonical_target_fields(upload_response.get("target_system", "canonical"))
        except httpx.HTTPError as error:
            st.warning(api_error_message(error, default_prefix="Canonical target options are unavailable right now"))
            return
    else:
        target_columns = schema_column_names(upload_response["target"])
    active_sources = {decision["source"] for decision in build_mapping_decisions()}
    preferred_sources = [source for source in source_columns if source not in active_sources]
    source_options = preferred_sources or source_columns
    manual_rows = manual_mapping_rows(mapping_response)

    with st.expander(
        _section_label("Manual Mapping", f"{len(manual_rows)} overrides" if manual_rows else "add or override"),
        expanded=True,
    ):
        st.caption(
            "Add or override a source-to-target pair even when the auto-mapper did not propose it. "
            "In canonical mode, targets are canonical concept IDs from the virtual glossary target."
        )

        form_columns = st.columns([2, 2, 1, 1])
        selected_source = form_columns[0].selectbox(
            "Manual source column",
            source_options,
            key="manual_mapping_source",
        )
        selected_target = form_columns[1].selectbox(
            "Manual target column",
            target_columns,
            key="manual_mapping_target",
        )
        selected_status = form_columns[2].selectbox(
            "Manual status",
            ["accepted", "needs_review"],
            key="manual_mapping_status",
        )
        if form_columns[3].button("Add mapping", width="stretch", key="manual_mapping_add"):
            upsert_manual_mapping(selected_source, selected_target, selected_status)
            _record_decision_audit(
                selected_source,
                origin="manual_mapping",
                details={"mode": "add_mapping", "status": selected_status, "target": selected_target},
            )
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Added manual mapping {selected_source} -> {selected_target}.",
            }
            st.rerun()

        if manual_rows:
            st.caption("Manual additions and overrides")
            st.dataframe(manual_rows, width="stretch", hide_index=True)
            removable_sources = [row["source"] for row in manual_rows]
            remove_columns = st.columns([3, 1])
            source_to_remove = remove_columns[0].selectbox(
                "Remove manual mapping",
                removable_sources,
                key="manual_mapping_remove_source",
            )
            if remove_columns[1].button("Remove", width="stretch", key="manual_mapping_remove"):
                remove_manual_mapping(source_to_remove, mapping_response)
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": f"Removed manual mapping for {source_to_remove}.",
                }
                st.rerun()
        else:
            st.info("No manual additions yet. Use this section when you already know a source-to-target pair that should exist.")


def render_mapping_decision_summary(*, build_mapping_decisions) -> None:
    """Render the currently active mapping decisions selected in the editor."""

    render_status_badge_legend(title="Decision Status Legend")
    _render_llm_decision_proposals_panel()
    decisions = build_mapping_decisions()
    if not decisions:
        st.warning("No active mapping decisions. Accept or mark at least one candidate as needs review.")
        return
    st.subheader(_section_label("Active Decisions", f"{len(decisions)} active"))
    st.dataframe(_active_decision_rows_with_audit(decisions), width="stretch", hide_index=True)


def render_mapping_io_panel(
    *,
    build_mapping_decisions,
    export_mapping_payload,
    export_mapping_excel_bytes,
    apply_imported_mapping_payload,
    api_request,
    build_mapping_set_payload,
) -> None:
    """Render import and export controls for mapping decisions."""

    decisions = build_mapping_decisions()
    export_disabled = not decisions

    with st.expander("Export / Import Decisions", expanded=False):
        export_columns = st.columns(2)
        export_columns[0].download_button(
            "Download mapping JSON",
            data=export_mapping_payload(),
            file_name="semantra_mapping_decisions.json",
            mime="application/json",
            disabled=export_disabled,
            width="stretch",
        )
        export_columns[1].download_button(
            "Download mapping Excel",
            data=export_mapping_excel_bytes(),
            file_name="semantra_mapping_decisions.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=export_disabled,
            width="stretch",
        )
        imported_file = st.file_uploader(
            "Import mapping JSON",
            type=["json"],
            key="mapping_import_file",
            help="Imports mapping_decisions and applies them to the current review state.",
        )
        if imported_file is not None and st.button("Apply imported mapping", width="stretch"):
            try:
                apply_imported_mapping_payload(imported_file.getvalue())
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Imported mapping decisions into the current review state.",
                }
                st.rerun()
            except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Import failed: {error}",
                }
                st.rerun()


def render_mapping_set_versions_panel(
    *,
    build_mapping_decisions,
    apply_imported_mapping_payload,
    api_request,
    build_mapping_set_payload,
) -> None:
    """Render mapping-set save, load, apply, audit, and diff workflows."""

    decisions = build_mapping_decisions()
    saved_mapping_sets = st.session_state.get("saved_mapping_sets")

    with st.expander(
        _section_label("Mapping Set Versions", f"{len(saved_mapping_sets)} loaded" if saved_mapping_sets else None),
        expanded=False,
    ):
        st.caption(
            "Save and reload durable mapping sets here. Final approval belongs in Governance > Stewardship, even though "
            "status shortcuts remain available in this panel during the current pilot/dev flow."
        )
        mapping_set_columns = st.columns([2, 2])
        mapping_set_name = mapping_set_columns[0].text_input(
            "Mapping set name",
            value="",
            key="mapping_set_name",
            placeholder="Example: customer-master-v1",
        )
        mapping_set_created_by = mapping_set_columns[1].text_input(
            "Mapping set created by",
            value="",
            key="mapping_set_created_by",
            placeholder="Example: ba-team",
        )
        metadata_columns = st.columns(2)
        mapping_set_owner = metadata_columns[0].text_input(
            "Mapping set owner",
            value="",
            key="mapping_set_owner",
            placeholder="Example: data-governance",
        )
        mapping_set_assignee = metadata_columns[1].text_input(
            "Mapping set assignee",
            value="",
            key="mapping_set_assignee",
            placeholder="Example: analyst-on-duty",
        )
        mapping_set_note = st.text_input(
            "Version note",
            value="",
            key="mapping_set_note",
            placeholder="Optional note for this saved version",
        )
        mapping_set_review_note = st.text_input(
            "Review note",
            value="",
            key="mapping_set_review_note",
            placeholder="Optional governance/review note for this version",
        )
        mapping_set_actions = st.columns(2)
        if mapping_set_actions[0].button(
            "Save mapping set version",
            width="stretch",
            key="save_mapping_set_version",
            disabled=(not decisions) or (not mapping_set_name.strip()),
        ):
            try:
                saved_mapping_set = api_request(
                    "POST",
                    "/mapping/sets",
                    json=build_mapping_set_payload(
                        mapping_set_name,
                        mapping_set_created_by,
                        mapping_set_note,
                        mapping_set_owner,
                        mapping_set_assignee,
                        mapping_set_review_note,
                    ),
                )
                st.session_state["saved_mapping_set_record"] = saved_mapping_set
                st.session_state["saved_mapping_sets"] = api_request("GET", "/mapping/sets")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Saved mapping set '{saved_mapping_set['name']}' version {saved_mapping_set['version']}.",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Saving mapping set failed: {error}",
                }
                st.rerun()

        if mapping_set_actions[1].button(
            "Load saved mapping sets",
            width="stretch",
            key="load_saved_mapping_sets",
        ):
            try:
                st.session_state["saved_mapping_sets"] = api_request("GET", "/mapping/sets")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Loaded saved mapping set versions.",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading mapping sets failed: {error}",
                }
                st.rerun()

        saved_mapping_sets = st.session_state.get("saved_mapping_sets")
        if saved_mapping_sets:
            st.caption("Saved mapping sets")
            st.dataframe(saved_mapping_sets, width="stretch", hide_index=True)
            mapping_set_labels = [
                f"#{item['mapping_set_id']} | {item['name']} | v{item['version']} | {item['status']}"
                for item in saved_mapping_sets
            ]
            selected_mapping_set_label = st.selectbox(
                "Select saved mapping set",
                mapping_set_labels,
                key="selected_saved_mapping_set_label",
            )
            selected_mapping_set = saved_mapping_sets[mapping_set_labels.index(selected_mapping_set_label)]
            selected_mapping_set_id = selected_mapping_set["mapping_set_id"]
            apply_block_reason = _saved_mapping_set_apply_block_reason(selected_mapping_set)
            saved_mapping_set_actions = st.columns([2, 2])
            if saved_mapping_set_actions[0].button(
                "Apply saved mapping set",
                width="stretch",
                key="apply_saved_mapping_set",
                disabled=bool(apply_block_reason),
            ):
                try:
                    mapping_set_detail = api_request(
                        "POST",
                        f"/mapping/sets/{selected_mapping_set_id}/apply",
                        json={
                            "changed_by": (mapping_set_created_by or "").strip() or None,
                            "note": (mapping_set_review_note or mapping_set_note or "").strip() or None,
                        },
                    )
                    apply_imported_mapping_payload(
                        json.dumps(
                            {
                                "source_dataset_id": mapping_set_detail.get("source_dataset_id"),
                                "target_dataset_id": mapping_set_detail.get("target_dataset_id"),
                                "mapping_decisions": mapping_set_detail.get("mapping_decisions", []),
                            },
                            ensure_ascii=True,
                        ).encode("utf-8")
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Applied saved mapping set '{mapping_set_detail['name']}' version {mapping_set_detail['version']}.",
                    }
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": api_error_message(error, default_prefix="Applying saved mapping set failed"),
                    }
                    st.rerun()
                except (json.JSONDecodeError, KeyError, UnicodeDecodeError) as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Applying saved mapping set failed: {error}",
                    }
                    st.rerun()
            if apply_block_reason:
                st.caption(apply_block_reason)

            if saved_mapping_set_actions[1].button(
                "Open Governance Stewardship",
                width="stretch",
                key="open_mapping_set_governance_handoff",
            ):
                _open_mapping_set_governance_handoff(selected_mapping_set)

            target_status = st.selectbox(
                "Saved mapping set status shortcut",
                ["draft", "review", "approved", "archived"],
                index=["draft", "review", "approved", "archived"].index(selected_mapping_set.get("status", "draft")),
                key="selected_saved_mapping_set_status",
            )
            st.caption(_mapping_set_status_guidance(target_status))
            if st.button(
                "Update saved mapping set status",
                width="stretch",
                key="update_saved_mapping_set_status",
            ):
                try:
                    updated = api_request(
                        "POST",
                        f"/mapping/sets/{selected_mapping_set_id}/status",
                        json={
                            "status": target_status,
                            "changed_by": (mapping_set_created_by or "").strip() or None,
                            "note": (mapping_set_note or "").strip() or None,
                            "owner": (mapping_set_owner or "").strip() or None,
                            "assignee": (mapping_set_assignee or "").strip() or None,
                            "review_note": (mapping_set_review_note or "").strip() or None,
                        },
                    )
                    st.session_state["saved_mapping_sets"] = api_request("GET", "/mapping/sets")
                    st.session_state["selected_mapping_set_audit"] = api_request(
                        "GET",
                        f"/mapping/sets/{selected_mapping_set_id}/audit",
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Updated mapping set '{updated['name']}' to status {updated['status']}.",
                    }
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Updating mapping set status failed: {error}",
                    }
                    st.rerun()

            if st.button(
                "Load selected mapping set audit",
                width="stretch",
                key="load_selected_mapping_set_audit",
            ):
                try:
                    st.session_state["selected_mapping_set_audit"] = api_request(
                        "GET",
                        f"/mapping/sets/{selected_mapping_set_id}/audit",
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Loaded audit for mapping set #{selected_mapping_set_id}.",
                    }
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Loading mapping set audit failed: {error}",
                    }
                    st.rerun()

            comparison_candidates = [
                item
                for item in saved_mapping_sets
                if item.get("name") == selected_mapping_set.get("name")
                and item.get("mapping_set_id") != selected_mapping_set_id
            ]
            if comparison_candidates:
                comparison_labels = [
                    f"#{item['mapping_set_id']} | {item['name']} | v{item['version']} | {item['status']}"
                    for item in comparison_candidates
                ]
                selected_comparison_label = st.selectbox(
                    "Compare against version",
                    comparison_labels,
                    key="selected_mapping_set_diff_label",
                )
                comparison_mapping_set = comparison_candidates[comparison_labels.index(selected_comparison_label)]
                if st.button(
                    "Load mapping set diff",
                    width="stretch",
                    key="load_selected_mapping_set_diff",
                ):
                    try:
                        st.session_state["selected_mapping_set_diff"] = api_request(
                            "GET",
                            f"/mapping/sets/{selected_mapping_set_id}/diff?against_id={comparison_mapping_set['mapping_set_id']}",
                        )
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": (
                                f"Loaded diff for mapping set #{selected_mapping_set_id} against "
                                f"version {comparison_mapping_set['version']}."
                            ),
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Loading mapping set diff failed: {error}",
                        }
                        st.rerun()

        selected_mapping_set_audit = st.session_state.get("selected_mapping_set_audit")
        if selected_mapping_set_audit:
            st.caption("Selected mapping set audit")
            st.dataframe(selected_mapping_set_audit, width="stretch", hide_index=True)

        selected_mapping_set_diff = st.session_state.get("selected_mapping_set_diff")
        if selected_mapping_set_diff:
            st.caption(
                "Selected mapping set diff: "
                f"v{selected_mapping_set_diff.get('current_version')} vs v{selected_mapping_set_diff.get('against_version')}"
            )
            summary_columns = st.columns(3)
            summary_columns[0].metric("Added", selected_mapping_set_diff.get("added_count", 0))
            summary_columns[1].metric("Removed", selected_mapping_set_diff.get("removed_count", 0))
            summary_columns[2].metric("Changed", selected_mapping_set_diff.get("changed_count", 0))
            changes = selected_mapping_set_diff.get("changes", [])
            if changes:
                st.dataframe(changes, width="stretch", hide_index=True)
            else:
                st.info("No decision changes between the selected mapping set versions.")

        st.divider()
        saved_draft_sessions = st.session_state.get("saved_draft_sessions")
        st.caption("Draft sessions resume the active Decisions workspace without entering governance/versioning flow.")
        draft_session_name = st.text_input(
            "Draft session name",
            value="",
            key="draft_session_name",
            placeholder="Example: customer-master-review-wip",
        )
        draft_session_actions = st.columns(2)
        if draft_session_actions[0].button(
            "Save draft session",
            width="stretch",
            key="save_draft_session",
            disabled=(not decisions) or (not draft_session_name.strip()),
        ):
            try:
                saved_draft_session = api_request(
                    "POST",
                    "/mapping/draft-sessions",
                    json=_build_draft_session_request_payload(draft_session_name),
                )
                _set_active_draft_session(saved_draft_session)
                st.session_state["saved_draft_sessions"] = api_request("GET", "/mapping/draft-sessions")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": (
                        f"Saved draft session '{saved_draft_session['name']}' "
                        f"for {saved_draft_session['active_workspace_section']}."
                    ),
                }
                st.rerun()
            except (ValueError, KeyError) as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Saving draft session failed: {error}",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": api_error_message(error, default_prefix="Saving draft session failed"),
                }
                st.rerun()

        if draft_session_actions[1].button(
            "Load draft sessions",
            width="stretch",
            key="load_draft_sessions",
        ):
            try:
                st.session_state["saved_draft_sessions"] = api_request("GET", "/mapping/draft-sessions")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Loaded saved draft sessions.",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": api_error_message(error, default_prefix="Loading draft sessions failed"),
                }
                st.rerun()

        saved_draft_sessions = st.session_state.get("saved_draft_sessions")
        if saved_draft_sessions:
            st.caption("Saved draft sessions")
            st.dataframe(saved_draft_sessions, width="stretch", hide_index=True)
            draft_session_by_id = {
                int(item["draft_session_id"]): item
                for item in saved_draft_sessions
                if int(item.get("draft_session_id") or 0)
            }
            selected_draft_session_id = _resolve_selected_draft_session_id(saved_draft_sessions)
            selected_draft_session_id = st.selectbox(
                "Select draft session",
                options=list(draft_session_by_id),
                key="selected_draft_session_id",
                index=list(draft_session_by_id).index(selected_draft_session_id),
                format_func=lambda draft_session_id: _draft_session_option_label(draft_session_by_id[draft_session_id]),
            )
            selected_draft_session = draft_session_by_id[selected_draft_session_id]
            if st.button(
                "Resume draft session",
                width="stretch",
                key="resume_draft_session",
            ):
                try:
                    draft_session_detail = api_request(
                        "GET",
                        f"/mapping/draft-sessions/{selected_draft_session['draft_session_id']}",
                        params=_draft_session_identity_query_params(selected_draft_session),
                    )
                    restored_section = _apply_draft_session_detail_to_workspace(draft_session_detail)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": (
                            f"Resumed draft session '{draft_session_detail['name']}' "
                            f"into Workspace {restored_section}."
                            f"{_draft_session_resume_transformation_message(draft_session_detail)}"
                            f"{_draft_session_resume_output_message(draft_session_detail)}"
                        ),
                    }
                    st.rerun()
                except (KeyError, ValueError) as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Resuming draft session failed: {error}",
                    }
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": api_error_message(error, default_prefix="Resuming draft session failed"),
                    }
                    st.rerun()


def render_correction_panel(
    *,
    build_pending_corrections,
    correction_block_reason,
    admin_token_required,
    api_request,
    persist_corrections,
) -> None:
    """Render correction persistence and reusable-rule review controls."""

    pending_corrections = build_pending_corrections()
    block_reason = correction_block_reason()

    with st.expander(
        _section_label("Save Corrections", f"{len(pending_corrections)} pending" if pending_corrections else None),
        expanded=bool(pending_corrections),
    ):
        if pending_corrections:
            st.dataframe(pending_corrections, width="stretch", hide_index=True)
        else:
            st.info("No changed target selections to save as corrections yet.")

        note = st.text_input(
            "Correction note",
            value="",
            key="correction_note",
            placeholder="Optional note saved with each correction",
        )
        admin_token = st.session_state.get("admin_token", "").strip()
        token_required = admin_token_required()
        if token_required and not admin_token:
            st.warning("Admin token is required to save corrections through the observability API.")
        elif not token_required:
            st.info("Backend currently allows correction saves without an admin token.")

        if st.button(
            "Load reusable rule candidates",
            disabled=(token_required and not admin_token),
            key="load_reusable_rule_candidates",
        ):
            try:
                st.session_state["reusable_rule_candidates"] = api_request("GET", "/observability/corrections/reusable-rules")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Loaded reusable correction rule candidates.",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading reusable rule candidates failed: {error}",
                }
                st.rerun()

        if st.button(
            "Load promoted reusable rules",
            disabled=(token_required and not admin_token),
            key="load_promoted_reusable_rules",
        ):
            try:
                st.session_state["promoted_reusable_rules"] = api_request("GET", "/observability/corrections/reusable-rules/active")
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Loaded promoted reusable correction rules.",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Loading promoted reusable rules failed: {error}",
                }
                st.rerun()

        if st.button(
            "Save reviewed corrections",
            disabled=(not pending_corrections) or bool(block_reason) or (token_required and not admin_token),
        ):
            try:
                saved_entries = persist_corrections(note)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Saved {len(saved_entries)} correction(s) to the observability store.",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Saving corrections failed: {error}",
                }
                st.rerun()
        if block_reason:
            st.caption(block_reason)

        saved_corrections = st.session_state.get("saved_corrections")
        if saved_corrections:
            st.caption("Last saved corrections")
            st.dataframe(saved_corrections, width="stretch", hide_index=True)

        reusable_rule_candidates = st.session_state.get("reusable_rule_candidates")
        if reusable_rule_candidates:
            st.caption("Reusable rule candidates")
            st.dataframe(reusable_rule_candidates, width="stretch", hide_index=True)
            promotable_candidates = [item for item in reusable_rule_candidates if not item.get("already_promoted")]
            if promotable_candidates:
                candidate_labels = [
                    (
                        f"{item.get('source')} | {item.get('status')} | "
                        f"{item.get('suggested_target') or 'no_suggestion'} -> {item.get('corrected_target') or 'reject'} | "
                        f"seen {item.get('occurrence_count', 0)}x"
                    )
                    for item in promotable_candidates
                ]
                selected_label = st.selectbox(
                    "Promote reusable rule candidate",
                    candidate_labels,
                    key="promote_reusable_rule_candidate",
                )
                selected_candidate = promotable_candidates[candidate_labels.index(selected_label)]
                if st.button(
                    "Promote selected reusable rule",
                    disabled=(token_required and not admin_token),
                    key="promote_reusable_rule_button",
                ):
                    try:
                        promoted = api_request(
                            "POST",
                            "/observability/corrections/reusable-rules/promote",
                            json={
                                "source": selected_candidate.get("source"),
                                "suggested_target": selected_candidate.get("suggested_target"),
                                "corrected_target": selected_candidate.get("corrected_target"),
                                "status": selected_candidate.get("status"),
                                "occurrence_count": selected_candidate.get("occurrence_count", 0),
                            },
                        )
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": (
                                f"Promoted reusable rule #{promoted.get('rule_id')} for {promoted.get('source')} "
                                f"({promoted.get('status')})."
                            ),
                        }
                        st.session_state["reusable_rule_candidates"] = api_request("GET", "/observability/corrections/reusable-rules")
                        st.session_state["promoted_reusable_rules"] = api_request(
                            "GET",
                            "/observability/corrections/reusable-rules/active",
                        )
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Promoting reusable rule failed: {error}",
                        }
                        st.rerun()
            else:
                st.caption("All currently suggested reusable rules are already promoted.")

        promoted_reusable_rules = st.session_state.get("promoted_reusable_rules")
        if promoted_reusable_rules:
            st.caption("Promoted reusable rules")
            st.dataframe(promoted_reusable_rules, width="stretch", hide_index=True)
