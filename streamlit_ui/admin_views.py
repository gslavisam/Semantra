from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import streamlit as st


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

    st.subheader("Knowledge Overlays")
    knowledge_action_columns = st.columns(4)
    if knowledge_action_columns[0].button("Load knowledge overlays", width="stretch", key="debug_load_knowledge_overlays"):
        try:
            st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded knowledge overlay versions."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge overlays failed: {error}"}
        st.rerun()

    if knowledge_action_columns[1].button("Reload knowledge", width="stretch", key="debug_reload_knowledge"):
        try:
            st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
            st.session_state["last_action"] = {"level": "success", "message": "Reloaded active knowledge overlay into runtime."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Knowledge reload failed: {error}"}
        st.rerun()

    if knowledge_action_columns[2].button("Load active knowledge status", width="stretch", key="debug_load_knowledge_runtime"):
        try:
            st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded active knowledge runtime status."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading knowledge runtime status failed: {error}"}
        st.rerun()

    if knowledge_action_columns[3].button("Load knowledge audit log", width="stretch", key="debug_load_knowledge_audit"):
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
        key="debug_validate_knowledge_overlay",
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
        key="debug_save_knowledge_overlay",
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
            st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Saved knowledge overlay version '{created['version']['name']}' with {created['saved_entry_count']} entries.",
            }
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Saving knowledge overlay failed: {error}"}
        st.rerun()

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
        key="debug_export_canonical_glossary",
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
        key="debug_import_canonical_glossary",
        disabled=canonical_glossary_upload is None,
    ):
        try:
            st.session_state["debug_canonical_glossary_import"] = api_request(
                "POST",
                "/knowledge/canonical-glossary/import",
                files=upload_file_to_request_files(canonical_glossary_upload),
            )
            st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
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

    knowledge_validation = st.session_state.get("debug_knowledge_validation")
    if knowledge_validation:
        validation_entry_type_counts: dict[str, int] = {}
        for row in knowledge_validation.get("normalized_preview", []):
            if row.get("status") != "valid":
                continue
            entry_type = str(row.get("entry_type") or "")
            if not entry_type:
                continue
            validation_entry_type_counts[entry_type] = validation_entry_type_counts.get(entry_type, 0) + 1
        st.caption(
            f"Validation summary: total={knowledge_validation.get('total_rows', 0)} | "
            f"valid={knowledge_validation.get('valid_rows', 0)} | invalid={knowledge_validation.get('invalid_rows', 0)} | "
            f"duplicates={knowledge_validation.get('duplicate_rows', 0)} | conflicts={knowledge_validation.get('conflicts', 0)}"
        )
        if validation_entry_type_counts:
            st.caption(
                "Valid entry types: "
                + " | ".join(f"{entry_type}={count}" for entry_type, count in sorted(validation_entry_type_counts.items()))
            )
        if knowledge_validation.get("normalized_preview"):
            st.dataframe(
                [
                    {
                        "row_number": row.get("row_number"),
                        "status": row.get("status"),
                        "entry_type": row.get("entry_type"),
                        "canonical_term": row.get("canonical_term"),
                        "alias": row.get("alias"),
                        "normalized_canonical_term": row.get("normalized_canonical_term"),
                        "normalized_alias": row.get("normalized_alias"),
                        "issues": " | ".join(issue.get("message", "") for issue in row.get("issues", [])),
                    }
                    for row in knowledge_validation.get("normalized_preview", [])
                ],
                width="stretch",
                hide_index=True,
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
            if overlay_columns[0].button("Load details", width="stretch", key="debug_load_overlay_details"):
                try:
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Loaded knowledge overlay details for version #{selected_overlay_id}.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Loading overlay details failed: {error}"}
                st.rerun()

            if overlay_columns[1].button("Activate selected overlay", width="stretch", key="debug_activate_overlay"):
                try:
                    activated = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/activate")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
                    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Activated knowledge overlay '{activated['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay activation failed: {error}"}
                st.rerun()

            if overlay_columns[2].button("Deactivate selected overlay", width="stretch", key="debug_deactivate_overlay"):
                try:
                    deactivated = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/deactivate")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
                    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Deactivated knowledge overlay '{deactivated['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay deactivation failed: {error}"}
                st.rerun()

            if overlay_columns[3].button("Archive selected overlay", width="stretch", key="debug_archive_overlay"):
                try:
                    archived = api_request("POST", f"/knowledge/overlays/{selected_overlay_id}/archive")
                    st.session_state["debug_selected_knowledge_overlay"] = api_request("GET", f"/knowledge/overlays/{selected_overlay_id}")
                    st.session_state["debug_knowledge_runtime"] = api_request("POST", "/knowledge/reload")
                    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Archived knowledge overlay '{archived['name']}'.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Overlay archive failed: {error}"}
                st.rerun()

            if st.button("Rollback active overlay", width="stretch", key="debug_rollback_overlay"):
                try:
                    runtime = api_request("POST", "/knowledge/overlays/rollback")
                    st.session_state["debug_knowledge_runtime"] = runtime
                    st.session_state["debug_knowledge_overlays"] = api_request("GET", "/knowledge/overlays")
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