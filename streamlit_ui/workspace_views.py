"""Primary Workspace UI for upload, mapping, preview, and generation workflows."""

from __future__ import annotations

import httpx
import streamlit as st
import time

from streamlit_ui.api import current_workspace_scope
from streamlit_ui.governance import api_error_message, mapping_output_block_reason


WORKSPACE_SECTIONS = ("Setup", "Review", "Decisions", "Output")
WORKSPACE_CODEGEN_MODES = ("pandas", "pyspark", "dbt")


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


def render_workspace_tab(
    *,
    all_upload_types,
    detect_spec_hint_for_upload,
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
    render_manual_mapping_panel,
    render_mapping_decision_summary,
    render_mapping_io_panel,
    render_mapping_set_versions_panel,
    render_correction_panel,
    build_mapping_decisions,
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
    source_file = st.session_state.get("source_file")
    target_file = st.session_state.get("target_file") if active_mapping_mode == "Standard" else None
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
            st.selectbox(
                "Canonical target",
                options=["canonical"],
                key="canonical_target_system",
                help="Epic 12A is system-neutral and maps source fields only to canonical glossary concepts.",
            )
            target_file = None
        else:
            target_file = st.file_uploader("Target file", type=all_upload_types, key="target_file")

        st.subheader("2. Interpret Files")
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
                    st.caption(
                        "Source file looks like a field specification: "
                        f"name={source_spec_hint['name_col']}, "
                        f"description={source_spec_hint.get('description_col') or '-'}, "
                        f"type={source_spec_hint.get('type_col') or '-'}, "
                        f"sample={source_spec_hint.get('sample_values_col') or '-'}"
                    )
                elif source_mode == "Schema spec":
                    st.caption(
                        "Auto-detection found no matching column headers. "
                        "Enter the column names from your spec file manually."
                    )
                    _src_cols = st.columns(4)
                    _src_cols[0].text_input(
                        "Name column",
                        key="source_spec_manual_name_col",
                        placeholder="e.g. Column",
                    )
                    _src_cols[1].text_input(
                        "Description column",
                        key="source_spec_manual_desc_col",
                        placeholder="e.g. Description",
                    )
                    _src_cols[2].text_input(
                        "Type column",
                        key="source_spec_manual_type_col",
                        placeholder="e.g. Type",
                    )
                    _src_cols[3].text_input(
                        "Sample values column",
                        key="source_spec_manual_sample_col",
                        placeholder="e.g. Sample Values",
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
                    st.caption(
                        "Target file looks like a field specification: "
                        f"name={target_spec_hint['name_col']}, "
                        f"description={target_spec_hint.get('description_col') or '-'}, "
                        f"type={target_spec_hint.get('type_col') or '-'}, "
                        f"sample={target_spec_hint.get('sample_values_col') or '-'}"
                    )
                elif target_mode == "Schema spec":
                    st.caption(
                        "Auto-detection found no matching column headers. "
                        "Enter the column names from your spec file manually."
                    )
                    _tgt_cols = st.columns(4)
                    _tgt_cols[0].text_input(
                        "Name column",
                        key="target_spec_manual_name_col",
                        placeholder="e.g. Column",
                    )
                    _tgt_cols[1].text_input(
                        "Description column",
                        key="target_spec_manual_desc_col",
                        placeholder="e.g. Description",
                    )
                    _tgt_cols[2].text_input(
                        "Type column",
                        key="target_spec_manual_type_col",
                        placeholder="e.g. Type",
                    )
                    _tgt_cols[3].text_input(
                        "Sample values column",
                        key="target_spec_manual_sample_col",
                        placeholder="e.g. Sample Values",
                    )

        st.subheader("3. Select Tables")
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
            st.info("Canonical mode builds a virtual target from canonical_glossary.csv when you generate mapping.")
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
                        "Uploaded source file and prepared canonical-only mapping context."
                        if canonical_mode
                        else "Uploaded files and built source/target schema profiles."
                    ),
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Upload failed: {error}"}
                st.rerun()

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

            st.subheader("Source Companion Metadata")
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
                st.caption(
                    "Companion file looks like a field specification: "
                    f"name={source_companion_hint['name_col']}, "
                    f"description={source_companion_hint.get('description_col') or '-'}, "
                    f"type={source_companion_hint.get('type_col') or '-'}, "
                    f"sample={source_companion_hint.get('sample_values_col') or '-'}"
                )
            elif source_companion_file is not None:
                st.caption(
                    "Auto-detection found no matching column headers in the companion file. "
                    "Enter the spec header names manually."
                )
                _cmp_cols = st.columns(4)
                _cmp_cols[0].text_input(
                    "Companion name column",
                    key="source_companion_manual_name_col",
                    placeholder="e.g. Column",
                )
                _cmp_cols[1].text_input(
                    "Companion description column",
                    key="source_companion_manual_desc_col",
                    placeholder="e.g. Description",
                )
                _cmp_cols[2].text_input(
                    "Companion type column",
                    key="source_companion_manual_type_col",
                    placeholder="e.g. Type",
                )
                _cmp_cols[3].text_input(
                    "Companion sample values column",
                    key="source_companion_manual_sample_col",
                    placeholder="e.g. Sample Values",
                )

            if st.button("Apply source companion metadata", key="apply_source_companion_metadata"):
                try:
                    enrichment_result = enrich_dataset_metadata(
                        upload_response["source"]["dataset_id"],
                        source_companion_file,
                        name_col=(
                            source_companion_hint.get("name_col")
                            if source_companion_hint
                            else (st.session_state.get("source_companion_manual_name_col") or None)
                        ),
                        description_col=(
                            source_companion_hint.get("description_col")
                            if source_companion_hint
                            else (st.session_state.get("source_companion_manual_desc_col") or None)
                        ),
                        type_col=(
                            source_companion_hint.get("type_col")
                            if source_companion_hint
                            else (st.session_state.get("source_companion_manual_type_col") or None)
                        ),
                        sample_values_col=(
                            source_companion_hint.get("sample_values_col")
                            if source_companion_hint
                            else (st.session_state.get("source_companion_manual_sample_col") or None)
                        ),
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
                st.subheader("Target Companion Metadata")
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
                    st.caption(
                        "Companion file looks like a field specification: "
                        f"name={target_companion_hint['name_col']}, "
                        f"description={target_companion_hint.get('description_col') or '-'}, "
                        f"type={target_companion_hint.get('type_col') or '-'}, "
                        f"sample={target_companion_hint.get('sample_values_col') or '-'}"
                    )
                elif target_companion_file is not None:
                    st.caption(
                        "Auto-detection found no matching column headers in the companion file. "
                        "Enter the spec header names manually."
                    )
                    _target_cmp_cols = st.columns(4)
                    _target_cmp_cols[0].text_input(
                        "Target companion name column",
                        key="target_companion_manual_name_col",
                        placeholder="e.g. Column",
                    )
                    _target_cmp_cols[1].text_input(
                        "Target companion description column",
                        key="target_companion_manual_desc_col",
                        placeholder="e.g. Description",
                    )
                    _target_cmp_cols[2].text_input(
                        "Target companion type column",
                        key="target_companion_manual_type_col",
                        placeholder="e.g. Type",
                    )
                    _target_cmp_cols[3].text_input(
                        "Target companion sample values column",
                        key="target_companion_manual_sample_col",
                        placeholder="e.g. Sample Values",
                    )

                if st.button("Apply target companion metadata", key="apply_target_companion_metadata"):
                    try:
                        enrichment_result = enrich_dataset_metadata(
                            upload_response["target"]["dataset_id"],
                            target_companion_file,
                            name_col=(
                                target_companion_hint.get("name_col")
                                if target_companion_hint
                                else (st.session_state.get("target_companion_manual_name_col") or None)
                            ),
                            description_col=(
                                target_companion_hint.get("description_col")
                                if target_companion_hint
                                else (st.session_state.get("target_companion_manual_desc_col") or None)
                            ),
                            type_col=(
                                target_companion_hint.get("type_col")
                                if target_companion_hint
                                else (st.session_state.get("target_companion_manual_type_col") or None)
                            ),
                            sample_values_col=(
                                target_companion_hint.get("sample_values_col")
                                if target_companion_hint
                                else (st.session_state.get("target_companion_manual_sample_col") or None)
                            ),
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

            st.subheader("3. Review Mapping")
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
            activity_label = (
                "Canonical mapping activity"
                if upload_mode == "canonical"
                else "Mapping activity"
            )
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
            if (upload_response or {}).get("mapping_mode") == "canonical":
                st.caption("Canonical-only review treats canonical concept IDs as virtual targets built from the glossary.")
            display_trust_layer(mapping_response)
            render_mapping_analysis_panel(mapping_response)
            render_mapping_review(mapping_response)
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
            render_mapping_decision_summary()
            render_manual_mapping_panel(mapping_response)
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
            canonical_output_mode = (upload_response or {}).get("mapping_mode") == "canonical"
            mapping_decisions = build_mapping_decisions()
            if canonical_output_mode:
                st.caption(
                    "Canonical mode supports code generation against canonical concept IDs, but preview stays unavailable because there is no concrete target dataset to materialize against."
                )
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
                    if st.button("Generate preview"):
                        if not mapping_decisions:
                            st.session_state["last_action"] = {
                                "level": "warning",
                                "message": "Add at least one active mapping before generating preview.",
                            }
                            st.rerun()
                        try:
                            st.session_state["preview_response"] = api_request(
                                "POST",
                                "/mapping/preview",
                                json={
                                    "source_dataset_id": st.session_state["upload_response"]["source"]["dataset_id"],
                                    "mapping_decisions": mapping_decisions,
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
                    if preview_advisory_message:
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
                        st.session_state["codegen_response"] = api_request(
                            "POST",
                            "/mapping/codegen",
                            json={
                                "mapping_decisions": mapping_decisions,
                                "mode": codegen_mode,
                                "allow_unaccepted": canonical_output_mode,
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
                            language=_workspace_generated_artifact_code_language(
                                codegen_refinement_response.get("language")
                            ),
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
                        not str(
                            (_workspace_refinement_source_response(codegen_response, codegen_refinement_response) or {}).get(
                                "code",
                                "",
                            )
                        ).strip()
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
                                "mode": (
                                    "pyspark"
                                    if refinement_source.get("language") == "python-pyspark"
                                    else "dbt"
                                    if refinement_source.get("language") == "sql-dbt"
                                    else "pandas"
                                ),
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