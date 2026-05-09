from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import streamlit as st


def _normalized_text(value: object) -> str:
    return str(value or "").strip()


def _filter_canonical_concepts(concepts: list[dict] | None, query: str | None = None) -> list[dict]:
    items = concepts or []
    normalized_query = _normalized_text(query).lower()
    if not normalized_query:
        return list(items)

    filtered: list[dict] = []
    for concept in items:
        haystacks = [
            _normalized_text(concept.get("concept_id")),
            _normalized_text(concept.get("display_name")),
            _normalized_text(concept.get("description")),
            _normalized_text(concept.get("entity")),
            _normalized_text(concept.get("attribute")),
            _normalized_text(concept.get("source")),
            *(str(alias or "") for alias in concept.get("base_aliases", [])),
            *(str(alias or "") for alias in concept.get("active_overlay_aliases", [])),
        ]
        if any(normalized_query in value.lower() for value in haystacks if value):
            filtered.append(concept)
    return filtered


def _filter_canonical_concepts_by_focus(concepts: list[dict] | None, focus: str | None = None) -> list[dict]:
    items = concepts or []
    normalized_focus = _normalized_text(focus).lower() or "all"
    if normalized_focus == "all":
        return list(items)

    filtered: list[dict] = []
    for concept in items:
        source = _normalized_text(concept.get("source")).lower() or "base"
        usage_count = int(concept.get("usage_count", 0) or 0)
        field_context_count = int(concept.get("field_context_count", 0) or 0)
        overlay_count = int(concept.get("active_overlay_entry_count", 0) or 0)
        if normalized_focus == "active_overlay" and overlay_count > 0:
            filtered.append(concept)
        elif normalized_focus == "overlay_only" and source == "overlay_only":
            filtered.append(concept)
        elif normalized_focus == "in_use" and usage_count > 0:
            filtered.append(concept)
        elif normalized_focus == "with_context" and field_context_count > 0:
            filtered.append(concept)
        elif normalized_focus == "base_only" and source == "base":
            filtered.append(concept)
    return filtered


def _canonical_overlay_summary(runtime: dict | None, overlays: list[dict] | None) -> dict[str, object]:
    runtime_payload = runtime or {}
    overlay_rows = overlays or []
    entry_type_counts = runtime_payload.get("entry_type_counts") or {}
    status_counts: dict[str, int] = {}
    for overlay in overlay_rows:
        status = _normalized_text(overlay.get("status")).lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "mode": runtime_payload.get("mode") or "base_only",
        "active_overlay_name": runtime_payload.get("active_overlay_name") or "none",
        "active_entry_count": int(runtime_payload.get("active_entry_count", 0) or 0),
        "concept_alias_entries": int(entry_type_counts.get("concept_alias", 0) or 0),
        "total_versions": len(overlay_rows),
        "active_versions": int(status_counts.get("active", 0) or 0),
        "validated_versions": int(status_counts.get("validated", 0) or 0),
        "archived_versions": int(status_counts.get("archived", 0) or 0),
    }


def _canonical_concept_registry_rows(concepts: list[dict] | None) -> list[dict]:
    rows: list[dict] = []
    for concept in concepts or []:
        base_aliases = [str(alias).strip() for alias in concept.get("base_aliases", []) if str(alias).strip()]
        overlay_aliases = [str(alias).strip() for alias in concept.get("active_overlay_aliases", []) if str(alias).strip()]
        rows.append(
            {
                "concept_id": concept.get("concept_id"),
                "display_name": concept.get("display_name"),
                "entity": concept.get("entity") or "",
                "attribute": concept.get("attribute") or "",
                "data_type": concept.get("data_type") or "",
                "source": concept.get("source") or "base",
                "usage_count": concept.get("usage_count", 0),
                "field_context_count": concept.get("field_context_count", 0),
                "active_overlay_entry_count": concept.get("active_overlay_entry_count", 0),
                "base_aliases": ", ".join(base_aliases),
                "active_overlay_aliases": ", ".join(overlay_aliases),
            }
        )
    return rows


def _canonical_concept_option_label(concept: dict) -> str:
    concept_id = _normalized_text(concept.get("concept_id")) or "unknown"
    display_name = _normalized_text(concept.get("display_name")) or concept_id
    source = _normalized_text(concept.get("source")) or "base"
    usage_count = int(concept.get("usage_count", 0) or 0)
    return f"{concept_id} | {display_name} | source={source} | usage={usage_count}"


def _canonical_gap_candidate_key(index: int, candidate: dict) -> str:
    source = _normalized_text(candidate.get("source"))
    target = _normalized_text(candidate.get("target"))
    return f"canonical_gap_{index}_{source}_{target}".replace(" ", "_")


def _canonical_gap_console_state(candidate_key: str, console_states: dict[str, str] | None = None) -> str:
    state = _normalized_text((console_states or {}).get(candidate_key)) or "active"
    if state not in {"active", "ignored", "approved", "rejected"}:
        return "active"
    return state


def _canonical_gap_queue_rows(
    candidates: list[dict] | None,
    suggestions: dict[str, dict] | None = None,
    console_states: dict[str, str] | None = None,
) -> list[dict]:
    rows: list[dict] = []
    suggestion_map = suggestions or {}
    for index, candidate in enumerate(candidates or []):
        candidate_key = _canonical_gap_candidate_key(index, candidate)
        suggestion = suggestion_map.get(candidate_key) or {}
        aliases = [str(alias).strip() for alias in suggestion.get("aliases", []) if str(alias).strip()]
        rows.append(
            {
                "source": candidate.get("source") or "",
                "target": candidate.get("target") or "",
                "confidence_pct": int(float(candidate.get("confidence", 0.0) or 0.0) * 100),
                "confidence_label": candidate.get("confidence_label") or "",
                "status": candidate.get("status") or "",
                "method": candidate.get("method") or "",
                "reason": candidate.get("reason") or "",
                "suggested_action": suggestion.get("action") or "pending",
                "suggested_concept": suggestion.get("concept_id") or "",
                "suggested_display_name": suggestion.get("display_name") or "",
                "alias_count": len(aliases),
                "reasoning_count": len(suggestion.get("reasoning") or []),
                "risk_count": len(suggestion.get("risk_notes") or []),
                "console_state": _canonical_gap_console_state(candidate_key, console_states),
            }
        )
    return rows


def _canonical_gap_option_label(index: int, candidate: dict, suggestion: dict | None = None) -> str:
    source = _normalized_text(candidate.get("source")) or "unknown"
    target = _normalized_text(candidate.get("target")) or "unknown"
    confidence_pct = int(float(candidate.get("confidence", 0.0) or 0.0) * 100)
    action = _normalized_text((suggestion or {}).get("action")) or "pending"
    return f"{source} -> {target} | confidence={confidence_pct}% | action={action}"


def _canonical_gap_can_approve(suggestion: dict | None, console_state: str = "active") -> bool:
    action = _normalized_text((suggestion or {}).get("action"))
    return bool(action and action != "no_action" and console_state == "active")


def _canonical_gap_can_ignore(console_state: str) -> bool:
    return console_state == "active"


def _canonical_gap_can_restore(console_state: str) -> bool:
    return console_state == "ignored"


def _canonical_gap_can_reject(console_state: str) -> bool:
    return console_state == "active"


def _canonical_gap_rejection_request(
    candidate: dict,
    suggestion: dict | None,
    rejected_by: str | None,
    note: str | None,
    disposition: str = "rejected",
) -> dict:
    payload: dict[str, object] = {
        "candidate": candidate,
        "disposition": disposition,
        "rejected_by": _normalized_text(rejected_by) or "streamlit-admin-debug",
    }
    if suggestion:
        payload["suggestion"] = suggestion
    if _normalized_text(note):
        payload["note"] = _normalized_text(note)
    return payload


def _canonical_gap_related_audit_entries(audit_entries: list[dict] | None, candidate: dict | None) -> list[dict]:
    source = _normalized_text((candidate or {}).get("source"))
    target = _normalized_text((candidate or {}).get("target"))
    if not source or not target:
        return []

    needle = f"{source} -> {target}"
    rows: list[dict] = []
    for entry in audit_entries or []:
        message = _normalized_text(entry.get("message"))
        if needle not in message:
            continue
        rows.append(
            {
                "action": entry.get("action") or "",
                "overlay_name": entry.get("overlay_name") or "",
                "created_at": entry.get("created_at") or "",
                "message": message,
            }
        )
    return rows


def _canonical_gap_approval_request(candidate: dict, suggestion: dict, approved_by: str | None) -> dict:
    return {
        "candidate": candidate,
        "suggestion": suggestion,
        "approved_by": _normalized_text(approved_by) or "streamlit-admin-debug",
    }


def _refresh_canonical_console_knowledge_state(*, api_request: Callable[..., Any]) -> None:
    st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")


def render_canonical_console_panel(
    *,
    api_request: Callable[..., Any],
    api_request_content: Callable[..., bytes],
    upload_file_to_request_files: Callable[[Any], dict | None],
) -> None:
    st.header("Canonical Console")
    st.caption(
        "Concept registry and review console for the active canonical model, including overlay aliases, usage, gap queue, and audit context."
    )

    if "debug_knowledge_audit_logs" not in st.session_state:
        try:
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
        except httpx.HTTPError:
            st.session_state["debug_knowledge_audit_logs"] = []

    canonical_console_actions = st.columns(4)
    if canonical_console_actions[0].button(
        "Load canonical concept registry",
        width="stretch",
        key="debug_load_canonical_concepts",
    ):
        try:
            st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            st.session_state["last_action"] = {"level": "success", "message": "Loaded canonical concept registry."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Loading canonical concept registry failed: {error}",
            }
        st.rerun()

    if canonical_console_actions[1].button(
        "Refresh overlay summary",
        width="stretch",
        key="canonical_console_refresh_overlay_summary",
    ):
        try:
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            st.session_state["last_action"] = {
                "level": "success",
                "message": "Refreshed overlay summary and knowledge audit state.",
            }
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Refreshing overlay summary failed: {error}",
            }
        st.rerun()

    if canonical_console_actions[2].button(
        "Load knowledge audit log",
        width="stretch",
        key="canonical_console_load_audit",
    ):
        try:
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge audit log."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Loading knowledge audit log failed: {error}",
            }
        st.rerun()

    if canonical_console_actions[3].button(
        "Clear canonical console state",
        width="stretch",
        key="debug_clear_canonical_concepts",
    ):
        for key in (
            "debug_canonical_concepts",
            "debug_selected_canonical_concept_label",
            "debug_canonical_concept_detail",
            "debug_selected_canonical_gap_label",
            "debug_canonical_gap_console_states",
            "debug_knowledge_audit_logs",
            "debug_knowledge_runtime",
            "debug_knowledge_overlays",
            "debug_selected_knowledge_overlay",
            "debug_knowledge_validation",
            "debug_knowledge_created",
            "debug_canonical_glossary_import",
            "canonical_glossary_export_bytes",
        ):
            st.session_state.pop(key, None)
        st.session_state["last_action"] = {"level": "info", "message": "Cleared canonical console state."}
        st.rerun()

    overlay_summary = _canonical_overlay_summary(
        st.session_state.get("debug_knowledge_runtime"),
        st.session_state.get("debug_knowledge_overlays"),
    )
    st.subheader("Overlay Summary")
    overlay_summary_columns = st.columns(5)
    overlay_summary_columns[0].metric("Active overlay", str(overlay_summary.get("active_overlay_name") or "none"))
    overlay_summary_columns[1].metric("Active entries", int(overlay_summary.get("active_entry_count", 0) or 0))
    overlay_summary_columns[2].metric("Concept aliases", int(overlay_summary.get("concept_alias_entries", 0) or 0))
    overlay_summary_columns[3].metric("Versions", int(overlay_summary.get("total_versions", 0) or 0))
    overlay_summary_columns[4].metric("Validated", int(overlay_summary.get("validated_versions", 0) or 0))
    st.caption(
        f"Mode={overlay_summary.get('mode') or 'base_only'} | "
        f"active_versions={overlay_summary.get('active_versions', 0)} | "
        f"archived_versions={overlay_summary.get('archived_versions', 0)}"
    )

    st.subheader("Overlay Management")
    overlay_action_columns = st.columns(4)
    if overlay_action_columns[0].button(
        "Load knowledge overlays",
        width="stretch",
        key="canonical_console_load_knowledge_overlays",
    ):
        try:
            st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge overlay versions."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge overlays failed: {error}"}
        st.rerun()

    if overlay_action_columns[1].button(
        "Reload knowledge",
        width="stretch",
        key="canonical_console_reload_knowledge",
    ):
        try:
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            st.session_state["last_action"] = {"level": "success", "message": "Reloaded active knowledge overlay into runtime."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Knowledge reload failed: {error}"}
        st.rerun()

    if overlay_action_columns[2].button(
        "Load active knowledge status",
        width="stretch",
        key="canonical_console_load_knowledge_runtime",
    ):
        try:
            st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded active knowledge runtime status."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge runtime status failed: {error}"}
        st.rerun()

    if overlay_action_columns[3].button(
        "Load overlay audit log",
        width="stretch",
        key="canonical_console_load_overlay_audit",
    ):
        try:
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge audit log."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge audit log failed: {error}"}
        st.rerun()

    knowledge_upload = st.file_uploader(
        "Knowledge overlay CSV",
        type=["csv"],
        key="knowledge_overlay_file",
        help="Upload CSV entries for abbreviations, synonyms, field aliases, or concept aliases.",
    )
    knowledge_overlay_name = st.text_input(
        "Overlay version name",
        value="",
        key="knowledge_overlay_name",
        placeholder="Example: customer-domain-overlay-v1",
    )
    knowledge_overlay_created_by = st.text_input(
        "Created by",
        value="",
        key="knowledge_overlay_created_by",
        placeholder="Example: data-governance-team",
    )
    knowledge_upload_columns = st.columns(2)
    if knowledge_upload_columns[0].button(
        "Validate knowledge CSV",
        width="stretch",
        key="canonical_console_validate_knowledge_overlay",
        disabled=knowledge_upload is None,
    ):
        try:
            st.session_state["debug_knowledge_validation"] = api_request(
                "POST",
                "/knowledge/overlays/validate",
                files=upload_file_to_request_files(knowledge_upload),
            )
            st.session_state["last_action"] = {"level": "success", "message": "Validated knowledge overlay CSV."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Knowledge CSV validation failed: {error}"}
        st.rerun()

    if knowledge_upload_columns[1].button(
        "Save overlay version",
        width="stretch",
        key="canonical_console_save_knowledge_overlay",
        disabled=knowledge_upload is None,
    ):
        try:
            created = api_request(
                "POST",
                "/knowledge/overlays",
                files=upload_file_to_request_files(knowledge_upload),
                data={
                    key: value
                    for key, value in {
                        "name": knowledge_overlay_name.strip(),
                        "created_by": knowledge_overlay_created_by.strip(),
                    }.items()
                    if value
                }
                or None,
            )
            st.session_state["debug_knowledge_created"] = created
            st.session_state["debug_knowledge_validation"] = created.get("validation")
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Saved knowledge overlay version '{created['version']['name']}' with {created['saved_entry_count']} entries.",
            }
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Saving knowledge overlay failed: {error}"}
        st.rerun()

    knowledge_validation = st.session_state.get("debug_knowledge_validation")
    if knowledge_validation:
        st.caption(
            f"Validation summary: total={knowledge_validation.get('total_rows', 0)} | "
            f"valid={knowledge_validation.get('valid_rows', 0)} | invalid={knowledge_validation.get('invalid_rows', 0)} | "
            f"duplicates={knowledge_validation.get('duplicate_rows', 0)} | conflicts={knowledge_validation.get('conflicts', 0)}"
        )

    knowledge_overlays = st.session_state.get("debug_knowledge_overlays")
    if knowledge_overlays:
        st.dataframe(knowledge_overlays, width="stretch", hide_index=True)
        overlay_options = {
            f"#{item['overlay_id']} | {item['name']} | {item['status']}": item["overlay_id"]
            for item in knowledge_overlays
        }
        if overlay_options:
            selected_overlay_label = st.selectbox(
                "Overlay version",
                list(overlay_options.keys()),
                key="debug_selected_overlay_version",
            )
            selected_overlay_id = overlay_options[selected_overlay_label]
            overlay_columns = st.columns(4)
            if overlay_columns[0].button("Load details", width="stretch", key="canonical_console_load_overlay_details"):
                try:
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Loaded knowledge overlay details for version #{selected_overlay_id}.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Loading overlay details failed: {error}"}
                st.rerun()

            if overlay_columns[1].button("Activate selected overlay", width="stretch", key="canonical_console_activate_overlay"):
                try:
                    activated = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/activate")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Activated knowledge overlay '{activated['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay activation failed: {error}"}
                st.rerun()

            if overlay_columns[2].button("Deactivate selected overlay", width="stretch", key="canonical_console_deactivate_overlay"):
                try:
                    deactivated = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/deactivate")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Deactivated knowledge overlay '{deactivated['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay deactivation failed: {error}"}
                st.rerun()

            if overlay_columns[3].button("Archive selected overlay", width="stretch", key="canonical_console_archive_overlay"):
                try:
                    archived = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/archive")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    _refresh_canonical_console_knowledge_state(api_request=api_request)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Archived knowledge overlay '{archived['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay archive failed: {error}"}
                st.rerun()

            if st.button("Rollback active overlay", width="stretch", key="canonical_console_rollback_overlay"):
                try:
                    runtime = api_request("POST", "/knowledge/overlays/rollback")
                    st.session_state["debug_knowledge_runtime"] = runtime
                    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
                    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                    active_overlay_id = runtime.get("active_overlay_id")
                    st.session_state["debug_selected_knowledge_overlay"] = (
                        api_request("GET", f"/knowledge/overlays/{active_overlay_id}") if active_overlay_id else None
                    )
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": (
                            f"Rolled back to knowledge overlay '{runtime['active_overlay_name']}'."
                            if active_overlay_id
                            else "Rolled back to base-only knowledge mode."
                        ),
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay rollback failed: {error}"}
                st.rerun()

    selected_overlay = st.session_state.get("debug_selected_knowledge_overlay")
    if selected_overlay:
        version = selected_overlay.get("version", {})
        overlay_entry_counts: dict[str, int] = {}
        for entry in selected_overlay.get("entries", []):
            entry_type = str(entry.get("entry_type") or "")
            if not entry_type:
                continue
            overlay_entry_counts[entry_type] = overlay_entry_counts.get(entry_type, 0) + 1
        st.caption(
            f"Overlay detail: #{version.get('overlay_id')} | {version.get('name')} | status={version.get('status')} | created_by={version.get('created_by') or 'n/a'} | source={version.get('source_filename') or 'n/a'}"
        )
        if overlay_entry_counts:
            st.caption(
                "Overlay entry summary: "
                + " | ".join(f"{entry_type}={count}" for entry_type, count in sorted(overlay_entry_counts.items()))
            )
        entries = selected_overlay.get("entries", [])
        if entries:
            st.dataframe(entries, width="stretch", hide_index=True)
        else:
            st.info("This overlay version does not contain any saved entries.")

    st.subheader("Canonical Glossary")
    canonical_glossary_upload = st.file_uploader(
        "Canonical glossary CSV",
        type=["csv"],
        key="canonical_glossary_file",
        help="Import or export the canonical business concept glossary as CSV.",
    )
    canonical_glossary_columns = st.columns(2)
    if canonical_glossary_columns[0].button(
        "Load canonical glossary export",
        width="stretch",
        key="canonical_console_export_canonical_glossary",
    ):
        try:
            st.session_state["canonical_glossary_export_bytes"] = api_request_content("GET", "/knowledge/canonical-glossary/export")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded canonical glossary export."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Canonical glossary export failed: {error}"}
        st.rerun()

    if canonical_glossary_columns[1].button(
        "Import canonical glossary",
        width="stretch",
        key="canonical_console_import_canonical_glossary",
        disabled=canonical_glossary_upload is None,
    ):
        try:
            st.session_state["debug_canonical_glossary_import"] = api_request(
                "POST",
                "/knowledge/canonical-glossary/import",
                files=upload_file_to_request_files(canonical_glossary_upload),
            )
            _refresh_canonical_console_knowledge_state(api_request=api_request)
            if st.session_state.get("debug_canonical_concepts") is not None:
                st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
            st.session_state["last_action"] = {"level": "success", "message": "Imported canonical glossary CSV."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Canonical glossary import failed: {error}"}
        st.rerun()

    canonical_glossary_export_bytes = st.session_state.get("canonical_glossary_export_bytes")
    if canonical_glossary_export_bytes:
        st.download_button(
            "Download canonical glossary CSV",
            data=canonical_glossary_export_bytes,
            file_name="canonical_glossary.csv",
            mime="text/csv",
            width="stretch",
        )

    canonical_glossary_import = st.session_state.get("debug_canonical_glossary_import")
    if canonical_glossary_import:
        st.caption(
            "Canonical glossary import: "
            f"rows={canonical_glossary_import.get('imported_row_count', 0)}, "
            f"concepts={canonical_glossary_import.get('canonical_concept_count', 0)}."
        )

    canonical_concepts = st.session_state.get("debug_canonical_concepts") or []
    if canonical_concepts:
        filter_columns = st.columns(2)
        concept_query = filter_columns[0].text_input(
            "Canonical concept search",
            value=st.session_state.get("debug_canonical_concept_query", ""),
            key="debug_canonical_concept_query",
            placeholder="Search by concept id, display name, alias, entity, or source",
        )
        concept_focus = filter_columns[1].selectbox(
            "Concept focus",
            options=["all", "active_overlay", "overlay_only", "in_use", "with_context", "base_only"],
            index=0,
            key="debug_canonical_concept_focus",
            format_func=lambda value: {
                "all": "All concepts",
                "active_overlay": "With active overlay aliases",
                "overlay_only": "Overlay-only concepts",
                "in_use": "Used in catalog",
                "with_context": "With field contexts",
                "base_only": "Base-only concepts",
            }.get(value, value),
        )
        filtered_concepts = _filter_canonical_concepts_by_focus(
            _filter_canonical_concepts(canonical_concepts, concept_query),
            concept_focus,
        )
        st.dataframe(_canonical_concept_registry_rows(filtered_concepts), width="stretch", hide_index=True)

        if filtered_concepts:
            concept_options = {_canonical_concept_option_label(item): item["concept_id"] for item in filtered_concepts}
            selected_concept_label = st.selectbox(
                "Canonical concept detail",
                list(concept_options.keys()),
                key="debug_selected_canonical_concept_label",
            )
            if st.button("Load canonical concept detail", width="stretch", key="debug_load_canonical_concept_detail"):
                selected_concept_id = concept_options[selected_concept_label]
                try:
                    st.session_state["debug_canonical_concept_detail"] = api_request(
                        "GET",
                        f"/knowledge/canonical-concepts/{selected_concept_id}",
                    )
                    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Loaded canonical concept detail for {selected_concept_id}.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Loading canonical concept detail failed: {error}",
                    }
                st.rerun()
        else:
            st.info("No canonical concepts match the current search.")

    canonical_concept_detail = st.session_state.get("debug_canonical_concept_detail")
    if canonical_concept_detail:
        concept = canonical_concept_detail.get("concept") or {}
        summary_columns = st.columns(4)
        summary_columns[0].metric("Usage", int(concept.get("usage_count", 0) or 0))
        summary_columns[1].metric("Field contexts", int(concept.get("field_context_count", 0) or 0))
        summary_columns[2].metric("Active overlay aliases", int(concept.get("active_overlay_entry_count", 0) or 0))
        summary_columns[3].metric("Alias count", int(concept.get("alias_count", 0) or 0))
        st.caption(
            f"{concept.get('concept_id') or 'unknown'} | {concept.get('display_name') or 'n/a'} | "
            f"entity={concept.get('entity') or '-'} | attribute={concept.get('attribute') or '-'} | "
            f"source={concept.get('source') or 'base'}"
        )
        if concept.get("description"):
            st.write(concept.get("description"))
        if concept.get("base_aliases") or concept.get("active_overlay_aliases"):
            st.caption(
                "Aliases: "
                + " | ".join(
                    part
                    for part in [
                        (
                            "base=" + ", ".join(concept.get("base_aliases") or [])
                            if concept.get("base_aliases")
                            else ""
                        ),
                        (
                            "active_overlay=" + ", ".join(concept.get("active_overlay_aliases") or [])
                            if concept.get("active_overlay_aliases")
                            else ""
                        ),
                    ]
                    if part
                )
            )

        if canonical_concept_detail.get("field_contexts"):
            st.write("**Field contexts**")
            st.dataframe(canonical_concept_detail.get("field_contexts"), width="stretch", hide_index=True)
        if canonical_concept_detail.get("active_overlay_entries"):
            st.write("**Active overlay entries**")
            st.dataframe(canonical_concept_detail.get("active_overlay_entries"), width="stretch", hide_index=True)
        if canonical_concept_detail.get("integrations"):
            st.write("**Catalog usage**")
            st.dataframe(canonical_concept_detail.get("integrations"), width="stretch", hide_index=True)
        if canonical_concept_detail.get("audit_entries"):
            st.write("**Knowledge audit references**")
            st.dataframe(canonical_concept_detail.get("audit_entries"), width="stretch", hide_index=True)

    st.write("**Canonical gap review queue**")
    st.caption(
        "Mirror of the Review tab canonical gap state. Console can approve, ignore, or reject cached suggestions while showing direct audit context for the selected gap."
    )
    canonical_gap_candidates = st.session_state.get("canonical_gap_candidates") or []
    canonical_gap_suggestions = st.session_state.get("canonical_gap_suggestions") or {}
    canonical_gap_console_states = st.session_state.setdefault("debug_canonical_gap_console_states", {})
    if canonical_gap_candidates:
        queue_columns = st.columns(5)
        queue_columns[0].metric("Candidates", len(canonical_gap_candidates))
        queue_columns[1].metric(
            "Ignored",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if _canonical_gap_console_state(
                    _canonical_gap_candidate_key(index, candidate),
                    canonical_gap_console_states,
                )
                == "ignored"
            ),
        )
        queue_columns[2].metric(
            "Rejected",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if _canonical_gap_console_state(
                    _canonical_gap_candidate_key(index, candidate),
                    canonical_gap_console_states,
                )
                == "rejected"
            ),
        )
        queue_columns[3].metric(
            "With suggestion",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if canonical_gap_suggestions.get(_canonical_gap_candidate_key(index, candidate))
            ),
        )
        queue_columns[4].metric(
            "Approve-ready",
            sum(
                1
                for index, candidate in enumerate(canonical_gap_candidates)
                if _canonical_gap_can_approve(
                    canonical_gap_suggestions.get(_canonical_gap_candidate_key(index, candidate)),
                    _canonical_gap_console_state(
                        _canonical_gap_candidate_key(index, candidate),
                        canonical_gap_console_states,
                    ),
                )
            ),
        )
        st.dataframe(
            _canonical_gap_queue_rows(canonical_gap_candidates, canonical_gap_suggestions, canonical_gap_console_states),
            width="stretch",
            hide_index=True,
        )

        gap_options = {
            _canonical_gap_option_label(index, candidate, canonical_gap_suggestions.get(_canonical_gap_candidate_key(index, candidate))): index
            for index, candidate in enumerate(canonical_gap_candidates)
        }
        selected_gap_label = st.selectbox(
            "Canonical gap queue detail",
            list(gap_options.keys()),
            key="debug_selected_canonical_gap_label",
        )
        selected_gap_index = gap_options[selected_gap_label]
        selected_candidate = canonical_gap_candidates[selected_gap_index]
        selected_candidate_key = _canonical_gap_candidate_key(selected_gap_index, selected_candidate)
        selected_suggestion = canonical_gap_suggestions.get(selected_candidate_key) or {}
        selected_console_state = _canonical_gap_console_state(selected_candidate_key, canonical_gap_console_states)

        detail_columns = st.columns([3, 3, 2])
        detail_columns[0].markdown(f"**Source:** {_normalized_text(selected_candidate.get('source')) or 'n/a'}")
        detail_columns[1].markdown(f"**Target:** {_normalized_text(selected_candidate.get('target')) or 'n/a'}")
        detail_columns[2].metric("Confidence", f"{int(float(selected_candidate.get('confidence', 0.0) or 0.0) * 100)}%")
        st.caption(f"Console state: {selected_console_state}")
        if selected_candidate.get("reason"):
            st.caption(selected_candidate.get("reason"))
        if selected_candidate.get("explanation"):
            st.caption("Signals: " + " | ".join(selected_candidate.get("explanation") or []))

        review_note = st.text_input(
            "Review note",
            value="",
            key=f"debug_review_note_{selected_gap_index}",
            placeholder="Why is this gap being ignored or rejected?",
        )

        state_action_columns = st.columns(3)
        if state_action_columns[0].button(
            "Ignore with audit",
            width="stretch",
            key=f"debug_ignore_canonical_gap_{selected_gap_index}",
            disabled=not _canonical_gap_can_ignore(selected_console_state),
        ):
            try:
                api_request(
                    "POST",
                    "/knowledge/canonical-gaps/reject",
                    json=_canonical_gap_rejection_request(
                        selected_candidate,
                        selected_suggestion or None,
                        st.session_state.get("admin_token"),
                        review_note,
                        disposition="ignored",
                    ),
                )
                canonical_gap_console_states[selected_candidate_key] = "ignored"
                st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": "Ignored canonical gap suggestion and persisted an audit entry.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Canonical gap ignore failed: {error}",
                }
            st.rerun()

        if state_action_columns[1].button(
            "Restore to queue",
            width="stretch",
            key=f"debug_restore_canonical_gap_{selected_gap_index}",
            disabled=not _canonical_gap_can_restore(selected_console_state),
        ):
            canonical_gap_console_states.pop(selected_candidate_key, None)
            st.session_state["last_action"] = {
                "level": "info",
                "message": "Restored canonical gap to the active console queue. Existing ignore audit entries remain in history.",
            }
            st.rerun()

        if state_action_columns[2].button(
            "Reject with audit",
            width="stretch",
            key=f"debug_reject_canonical_gap_{selected_gap_index}",
            disabled=not _canonical_gap_can_reject(selected_console_state),
        ):
            try:
                api_request(
                    "POST",
                    "/knowledge/canonical-gaps/reject",
                    json=_canonical_gap_rejection_request(
                        selected_candidate,
                        selected_suggestion or None,
                        st.session_state.get("admin_token"),
                        review_note,
                    ),
                )
                canonical_gap_console_states[selected_candidate_key] = "rejected"
                st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                st.session_state["last_action"] = {
                    "level": "info",
                    "message": "Rejected canonical gap suggestion and persisted an audit entry.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Canonical gap rejection failed: {error}",
                }
            st.rerun()

        related_gap_audit_entries = _canonical_gap_related_audit_entries(
            st.session_state.get("debug_knowledge_audit_logs"),
            selected_candidate,
        )
        if related_gap_audit_entries:
            st.write("**Gap audit references**")
            st.dataframe(related_gap_audit_entries, width="stretch", hide_index=True)

        if selected_suggestion:
            st.write(
                f"Action: **{selected_suggestion.get('action', 'no_action')}** | "
                f"Concept: **{selected_suggestion.get('concept_id') or 'n/a'}** - {selected_suggestion.get('display_name') or 'n/a'}"
            )
            if selected_suggestion.get("aliases"):
                st.caption("Aliases: " + ", ".join(selected_suggestion.get("aliases") or []))
            for line in selected_suggestion.get("reasoning") or []:
                st.caption(f"Reason: {line}")
            for line in selected_suggestion.get("risk_notes") or []:
                st.caption(f"Risk: {line}")

            approve_ready = _canonical_gap_can_approve(selected_suggestion, selected_console_state)
            if st.button(
                "Approve from console",
                width="stretch",
                key=f"debug_approve_canonical_gap_{selected_gap_index}",
                disabled=not approve_ready,
            ):
                try:
                    response = api_request(
                        "POST",
                        "/knowledge/canonical-gaps/approve",
                        json=_canonical_gap_approval_request(
                            selected_candidate,
                            selected_suggestion,
                            st.session_state.get("admin_token"),
                        ),
                    )
                    canonical_gap_console_states[selected_candidate_key] = "approved"
                    st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
                    st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
                    if st.session_state.get("debug_canonical_concepts") is not None:
                        st.session_state["debug_canonical_concepts"] = api_request("GET", "/knowledge/canonical-concepts")
                    approved_concept_id = _normalized_text(selected_suggestion.get("concept_id"))
                    if approved_concept_id:
                        st.session_state["debug_canonical_concept_detail"] = api_request(
                            "GET",
                            f"/knowledge/canonical-concepts/{approved_concept_id}",
                        )
                    if st.session_state.get("debug_knowledge_overlays") is not None:
                        st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": (
                            f"Approved canonical gap into overlay '{response.get('overlay_name')}'. "
                            "Regenerate mapping to see the canonical path filled."
                        ),
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Canonical gap approval failed: {error}",
                    }
                st.rerun()
            elif selected_console_state == "ignored":
                st.caption("This gap is currently ignored in the console. Restore it to the active queue before approving.")
            elif selected_console_state == "approved":
                st.caption("This gap was already approved from the console in this session.")
            elif selected_console_state == "rejected":
                st.caption("This gap was rejected from the console and the decision was persisted to the audit log.")
            elif not approve_ready:
                st.caption("This suggestion is not approve-ready. Generate a usable non-`no_action` suggestion from the Review tab first.")
        else:
            if selected_console_state == "rejected":
                st.caption("This gap was rejected without a cached suggestion payload. The audit decision is persisted.")
            elif selected_console_state == "ignored":
                st.caption("This gap was ignored with audit. Restore it locally if you want to reconsider it in the queue.")
            else:
                st.info("No cached LLM suggestion for this gap yet. Generate it from the Review tab.")
    else:
        st.info("Canonical gap review queue is empty. Use the Review tab to find high-confidence gaps first.")


def render_admin_debug_tab(
    *,
    admin_token_required: Callable[[], bool],
    api_request: Callable[..., Any],
    api_request_content: Callable[..., bytes],
    upload_file_to_request_files: Callable[[Any], dict | None],
    knowledge_debug_rows: Callable[[dict], list[dict]],
) -> None:
    st.header("Admin / Debug")
    admin_token = st.session_state.get("admin_token", "").strip()
    token_required = admin_token_required()
    if token_required and not admin_token:
        st.warning("Admin token is required for observability and evaluation admin endpoints.")
        return
    if not token_required:
        st.info("Backend currently exposes these admin/debug endpoints without an admin token.")

    action_columns = st.columns(4)
    if action_columns[0].button("Load runtime config", width="stretch", key="debug_load_runtime_config"):
        try:
            st.session_state["debug_runtime_config"] = api_request("GET", "/observability/config")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded runtime config snapshot."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading runtime config failed: {error}"}
        st.rerun()

    if action_columns[1].button("Load decision logs", width="stretch", key="debug_load_decision_logs"):
        try:
            st.session_state["debug_decision_logs"] = api_request("GET", "/observability/decision-logs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded decision logs."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading decision logs failed: {error}"}
        st.rerun()

    if action_columns[2].button("Load saved corrections", width="stretch", key="debug_load_corrections"):
        try:
            st.session_state["debug_corrections"] = api_request("GET", "/observability/corrections")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded saved corrections."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading corrections failed: {error}"}
        st.rerun()

    if action_columns[3].button("Load benchmark runs", width="stretch", key="debug_load_benchmark_runs"):
        try:
            st.session_state["debug_runs"] = api_request("GET", "/evaluation/runs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded evaluation runs."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading evaluation runs failed: {error}"}
        st.rerun()

    st.subheader("Knowledge Governance Debug")
    knowledge_debug_columns = st.columns(2)
    if knowledge_debug_columns[0].button("Load active knowledge status", width="stretch", key="debug_load_knowledge_runtime"):
        try:
            st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded active knowledge runtime status."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge runtime status failed: {error}"}
        st.rerun()

    if knowledge_debug_columns[1].button("Load knowledge audit log", width="stretch", key="debug_load_knowledge_audit"):
        try:
            st.session_state["debug_knowledge_audit_logs"] = api_request("GET", "/knowledge/audit")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge audit log."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge audit log failed: {error}"}
        st.rerun()
    st.info("Canonical Console tab now owns overlay summary, overlay lifecycle controls, and canonical glossary authoring UI.")

    knowledge_runtime = st.session_state.get("debug_knowledge_runtime")
    if knowledge_runtime:
        st.caption(
            "Knowledge mode: "
            + str(knowledge_runtime.get("mode") or "base_only")
            + " | active overlay: "
            + str(knowledge_runtime.get("active_overlay_name") or "none")
            + f" | active_entry_count={knowledge_runtime.get('active_entry_count', 0)}"
            + f" | concept_count={knowledge_runtime.get('concept_count', 0)}"
        )
        entry_type_counts = knowledge_runtime.get("entry_type_counts") or {}
        if entry_type_counts:
            st.caption(
                "Active overlay breakdown: "
                + " | ".join(f"{entry_type}={count}" for entry_type, count in sorted(entry_type_counts.items()))
            )

    knowledge_audit_logs = st.session_state.get("debug_knowledge_audit_logs")
    if knowledge_audit_logs:
        st.subheader("Knowledge Audit Log")
        st.dataframe(knowledge_audit_logs, width="stretch", hide_index=True)

    runtime_config = st.session_state.get("debug_runtime_config")
    if runtime_config:
        st.subheader("Runtime Config")
        st.json(runtime_config)

    mapping_response = st.session_state.get("mapping_response")
    if mapping_response:
        canonical_coverage = mapping_response.get("canonical_coverage") or {}
        source_coverage = canonical_coverage.get("source") or {}
        target_coverage = canonical_coverage.get("target") or {}
        project_coverage = canonical_coverage.get("project") or {}
        if source_coverage or target_coverage or project_coverage:
            st.subheader("Canonical Coverage")
            st.dataframe(
                [
                    {
                        "dataset": "source",
                        "coverage_ratio": source_coverage.get("coverage_ratio", 0.0),
                        "matched_columns": source_coverage.get("matched_columns", 0),
                        "total_columns": source_coverage.get("total_columns", 0),
                        "unmatched_columns": " | ".join(source_coverage.get("unmatched_columns", [])),
                    },
                    {
                        "dataset": "target",
                        "coverage_ratio": target_coverage.get("coverage_ratio", 0.0),
                        "matched_columns": target_coverage.get("matched_columns", 0),
                        "total_columns": target_coverage.get("total_columns", 0),
                        "unmatched_columns": " | ".join(target_coverage.get("unmatched_columns", [])),
                    },
                    {
                        "dataset": "project",
                        "coverage_ratio": project_coverage.get("coverage_ratio", 0.0),
                        "matched_columns": project_coverage.get("matched_columns", 0),
                        "total_columns": project_coverage.get("total_columns", 0),
                        "unmatched_columns": "shared=" + " | ".join(project_coverage.get("shared_concepts", [])),
                    },
                ],
                width="stretch",
                hide_index=True,
            )
        knowledge_rows = knowledge_debug_rows(mapping_response)
        if knowledge_rows:
            st.subheader("Knowledge and Canonical Match Insights")
            st.dataframe(
                [
                    {
                        "source": row["source"],
                        "target": row["target"],
                        "knowledge_signal": row["knowledge_signal"],
                        "canonical_signal": row["canonical_signal"],
                        "confidence": row["confidence"],
                        "validator": row["validator"],
                    }
                    for row in knowledge_rows
                ],
                width="stretch",
                hide_index=True,
            )
            for row in knowledge_rows:
                with st.expander(f"Knowledge details: {row['source']} -> {row['target']}"):
                    for line in row["knowledge_explanations"]:
                        st.caption(line)
                    for line in row["canonical_explanations"]:
                        st.caption(line)

    decision_logs = st.session_state.get("debug_decision_logs")
    if decision_logs:
        st.subheader("Decision Logs")
        st.dataframe(decision_logs, width="stretch", hide_index=True)

    corrections = st.session_state.get("debug_corrections")
    if corrections:
        st.subheader("Saved Corrections")
        st.dataframe(corrections, width="stretch", hide_index=True)

    runs = st.session_state.get("debug_runs")
    if runs:
        st.subheader("Evaluation Runs")
        st.dataframe(runs, width="stretch", hide_index=True)