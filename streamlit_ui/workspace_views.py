from __future__ import annotations

import httpx
import streamlit as st
import time

from streamlit_ui.governance import api_error_message, mapping_output_block_reason


def poll_mapping_job(
    *,
    api_request,
    start_path: str,
    payload: dict,
    status,
    timeout_seconds: float = 600.0,
) -> dict:
    started = api_request("POST", start_path, json=payload, timeout=30.0)
    job_id = started["job_id"]
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
            return response
        if job_status.get("status") == "failed":
            raise RuntimeError(job_status.get("error") or "Mapping job failed.")

        time.sleep(0.5)

    raise RuntimeError(f"Mapping job {job_id} did not finish before the timeout.")


def _workspace_codegen_block_reason(mapping_decisions: list[dict]) -> str:
    return mapping_output_block_reason(
        mapping_decisions,
        action_label="Pandas code generation",
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
    return bool(available_tables) and (is_sql or upload_mode == "Row data")


def companion_enrichment_message(result: dict | None) -> str:
    if not result:
        return ""

    matched_columns = int(result.get("matched_columns") or 0)
    unmatched_columns = [str(item) for item in (result.get("unmatched_columns") or []) if str(item).strip()]
    if unmatched_columns:
        return (
            f"Source companion metadata enriched {matched_columns} columns; "
            f"unmatched spec fields: {', '.join(unmatched_columns)}."
        )
    return f"Source companion metadata enriched {matched_columns} columns; all companion fields matched."


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
    display_trust_layer,
    render_mapping_review,
    render_mapping_editor,
    render_manual_mapping_panel,
    render_mapping_decision_summary,
    render_mapping_io_panel,
    render_correction_panel,
    build_mapping_decisions,
) -> None:
    setup_tab, review_tab, decisions_tab, output_tab = st.tabs(["Setup", "Review", "Decisions", "Output"])

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

    with setup_tab:
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
                        f"type={source_spec_hint.get('type_col') or '-'}"
                    )
                elif source_mode == "Schema spec":
                    st.caption(
                        "Auto-detection found no matching column headers. "
                        "Enter the column names from your spec file manually."
                    )
                    _src_cols = st.columns(3)
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
                        f"type={target_spec_hint.get('type_col') or '-'}"
                    )
                elif target_mode == "Schema spec":
                    st.caption(
                        "Auto-detection found no matching column headers. "
                        "Enter the column names from your spec file manually."
                    )
                    _tgt_cols = st.columns(3)
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
                    )
                st.session_state["upload_response"] = payload
                st.session_state.pop("mapping_response", None)
                st.session_state.pop("preview_response", None)
                st.session_state.pop("codegen_response", None)
                st.session_state.pop("mapping_editor_state", None)
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
            companion_result = st.session_state.get("source_companion_metadata_result")
            if companion_result:
                st.info(companion_enrichment_message(companion_result))

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
                    f"type={source_companion_hint.get('type_col') or '-'}"
                )
            elif source_companion_file is not None:
                st.caption(
                    "Auto-detection found no matching column headers in the companion file. "
                    "Enter the spec header names manually."
                )
                _cmp_cols = st.columns(3)
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
                    )
                    st.session_state["upload_response"]["source"] = enrichment_result["dataset"]
                    st.session_state["source_companion_metadata_result"] = {
                        "matched_columns": enrichment_result.get("matched_columns", 0),
                        "unmatched_columns": enrichment_result.get("unmatched_columns", []),
                    }
                    st.session_state.pop("mapping_response", None)
                    st.session_state.pop("preview_response", None)
                    st.session_state.pop("codegen_response", None)
                    st.session_state.pop("mapping_editor_state", None)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": companion_enrichment_message(st.session_state["source_companion_metadata_result"])
                        + " Re-run mapping to use the enriched source metadata.",
                    }
                    st.rerun()
                except (ValueError, httpx.HTTPError) as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Source companion metadata failed: {error}",
                    }
                    st.rerun()

            st.subheader("3. Review Mapping")
            use_llm = st.checkbox(
                "Use LLM validation",
                value=st.session_state.get("use_llm_validation", True),
                key="use_llm_validation",
                help=(
                    "When enabled, Semantra calls the configured LLM provider for fields in the ambiguity band. "
                    "Disable this if no LLM is running locally to avoid timeouts."
                ),
            )
            button_label = "Generate canonical mapping" if upload_mode == "canonical" else "Generate mapping"
            button_key = "generate_canonical_mapping" if upload_mode == "canonical" else "generate_mapping"
            activity_label = (
                "Canonical mapping activity"
                if upload_mode == "canonical"
                else "Mapping activity"
            )
            activity_placeholder = st.empty()
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
                                    },
                                    status=status,
                                )
                            status.write("Initializing review state.")
                            st.session_state["mapping_response"] = mapping_response
                            initialize_mapping_editor_state(mapping_response)
                            st.session_state.pop("preview_response", None)
                            st.session_state.pop("codegen_response", None)
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
        else:
            if canonical_mode:
                st.info("Upload and profile the source dataset to unlock canonical review and decision export.")
            else:
                st.info("Upload and profile both datasets to unlock review, decision, and output sections.")

    with review_tab:
        if mapping_response:
            if (upload_response or {}).get("mapping_mode") == "canonical":
                st.caption("Canonical-only review treats canonical concept IDs as virtual targets built from the glossary.")
            display_trust_layer(mapping_response)
            render_mapping_review(mapping_response)
            render_mapping_editor(mapping_response)
        else:
            if (upload_response or {}).get("mapping_mode") == "canonical":
                st.info("Generate canonical mapping in Setup to populate trust, candidate review, and manual review controls.")
            else:
                st.info("Generate mapping in Setup to populate trust, candidate review, and manual review controls.")

    with decisions_tab:
        if mapping_response:
            if (upload_response or {}).get("mapping_mode") != "canonical":
                render_manual_mapping_panel(mapping_response)
            else:
                st.info(
                    "Canonical-only mode currently keeps manual target additions and correction workflows disabled until a real target dataset exists."
                )
            render_mapping_decision_summary()
            render_mapping_io_panel()
            if (upload_response or {}).get("mapping_mode") != "canonical":
                render_correction_panel()
        else:
            st.info("Generate mapping in Setup before managing manual overrides, imports, mapping sets, or corrections.")

    with output_tab:
        if mapping_response:
            if (upload_response or {}).get("mapping_mode") == "canonical":
                st.info(
                    "Canonical-only mode stops at review and decision export for now. Preview rows and Pandas code generation become available after you switch back to Standard mode with a real target dataset."
                )
            else:
                mapping_decisions = build_mapping_decisions()
                codegen_block_reason = _workspace_codegen_block_reason(mapping_decisions)
                preview_advisory_message = _workspace_preview_advisory_message(mapping_decisions)
                actions_left, actions_right = st.columns(2)
                with actions_left:
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
                    if st.button("Generate Pandas code", disabled=bool(codegen_block_reason)):
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
                                json={"mapping_decisions": mapping_decisions},
                            )
                            st.session_state["last_action"] = {
                                "level": "success",
                                "message": "Generated Pandas code from the active mapping decisions.",
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
                if output_block_reason:
                    st.caption(output_block_reason)
        else:
            st.info("Generate mapping in Setup before preview or code generation.")

        if preview_response is not None:
            st.subheader("Preview")
            preview_rows = [row["values"] for row in preview_response["preview"]]
            if preview_rows:
                st.dataframe(preview_rows, width="stretch", hide_index=True)
            else:
                st.info("Preview is empty. This is expected for schema-only SQL uploads.")
            if preview_response.get("unresolved_targets"):
                st.warning(f"Needs review: {', '.join(preview_response['unresolved_targets'])}")
            transformation_previews = preview_response.get("transformation_previews") or []
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
            st.subheader("Generated Pandas Code")
            st.code(codegen_response["code"], language="python")
            if codegen_response.get("warnings"):
                for warning in codegen_response["warnings"]:
                    if isinstance(warning, dict):
                        prefix = warning.get("code") or "warning"
                        details = warning.get("details") or {}
                        suffix = ""
                        if details.get("line") is not None and details.get("column") is not None:
                            suffix = f" (line {details['line']}, col {details['column']})"
                        st.warning(f"{prefix}: {warning.get('message', '')}{suffix}")
                    else:
                        st.warning(str(warning))