from __future__ import annotations

import httpx
import streamlit as st


def render_workspace_tab(
    *,
    all_upload_types,
    sql_tables_for_upload,
    api_request,
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

    source_file = st.session_state.get("source_file")
    target_file = st.session_state.get("target_file")
    source_tables: list[str] = []
    target_tables: list[str] = []
    discovery_error = None
    if source_file is not None or target_file is not None:
        try:
            source_tables = sql_tables_for_upload(source_file, "source")
            target_tables = sql_tables_for_upload(target_file, "target")
        except httpx.HTTPError as error:
            discovery_error = str(error)

    upload_response = st.session_state.get("upload_response")
    mapping_response = st.session_state.get("mapping_response")
    preview_response = st.session_state.get("preview_response")
    codegen_response = st.session_state.get("codegen_response")

    with setup_tab:
        st.subheader("1. Upload")
        st.caption("Any row-based format can map to any other row-based format across CSV, JSON, XML, and XLSX.")
        source_file = st.file_uploader("Source file", type=all_upload_types, key="source_file")
        target_file = st.file_uploader("Target file", type=all_upload_types, key="target_file")

        st.subheader("2. Select Tables")
        if discovery_error:
            st.error(f"SQL inspection failed: {discovery_error}")

        source_table = None
        if source_tables:
            source_table = st.selectbox("Source table", source_tables, key="source_table")
        else:
            st.info("Source upload is row-based (CSV/JSON/XML/XLSX) or single-table SQL.")

        target_table = None
        if target_tables:
            target_table = st.selectbox("Target table", target_tables, key="target_table")
        else:
            st.info("Target upload is row-based (CSV/JSON/XML/XLSX) or single-table SQL.")

        if st.button("Upload and profile", type="primary", disabled=source_file is None or target_file is None):
            try:
                payload = api_request(
                    "POST",
                    "/upload",
                    files={
                        "source_file": (
                            source_file.name,
                            uploaded_file_bytes(source_file),
                            source_file.type or "application/octet-stream",
                        ),
                        "target_file": (
                            target_file.name,
                            uploaded_file_bytes(target_file),
                            target_file.type or "application/octet-stream",
                        ),
                    },
                    data={
                        "source_table": source_table or "",
                        "target_table": target_table or "",
                    },
                )
                st.session_state["upload_response"] = payload
                st.session_state.pop("mapping_response", None)
                st.session_state.pop("preview_response", None)
                st.session_state.pop("codegen_response", None)
                st.session_state.pop("mapping_editor_state", None)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Uploaded files and built source/target schema profiles.",
                }
                st.rerun()
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Upload failed: {error}"}
                st.rerun()

        if upload_response:
            left, right = st.columns(2)
            with left:
                render_dataset_summary("Source", upload_response["source"])
            with right:
                render_dataset_summary("Target", upload_response["target"])

            st.subheader("3. Review Mapping")
            if st.button("Generate mapping", type="primary"):
                try:
                    mapping_response = api_request(
                        "POST",
                        "/mapping/auto",
                        json={
                            "source_dataset_id": upload_response["source"]["dataset_id"],
                            "target_dataset_id": upload_response["target"]["dataset_id"],
                        },
                    )
                    st.session_state["mapping_response"] = mapping_response
                    initialize_mapping_editor_state(mapping_response)
                    st.session_state.pop("preview_response", None)
                    st.session_state.pop("codegen_response", None)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": "Generated ranked mapping candidates from the current datasets.",
                    }
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {"level": "error", "message": f"Mapping failed: {error}"}
                    st.rerun()

            if mapping_response:
                st.success(
                    "Mapping is ready. Continue in Review for trust-layer inspection, Decisions for overrides and mapping sets, "
                    "or Output for preview and Pandas code generation."
                )
        else:
            st.info("Upload and profile both datasets to unlock review, decision, and output sections.")

    with review_tab:
        if mapping_response:
            display_trust_layer(mapping_response)
            render_mapping_review(mapping_response)
            render_mapping_editor(mapping_response)
        else:
            st.info("Generate mapping in Setup to populate trust, candidate review, and manual review controls.")

    with decisions_tab:
        if mapping_response:
            render_manual_mapping_panel(mapping_response)
            render_mapping_decision_summary()
            render_mapping_io_panel()
            render_correction_panel()
        else:
            st.info("Generate mapping in Setup before managing manual overrides, imports, mapping sets, or corrections.")

    with output_tab:
        if mapping_response:
            mapping_decisions = build_mapping_decisions()
            actions_left, actions_right = st.columns(2)
            with actions_left:
                if st.button("Generate preview"):
                    if not mapping_decisions:
                        st.session_state["last_action"] = {
                            "level": "warning",
                            "message": "Add at least one accepted or needs-review mapping before generating preview.",
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
                            "message": f"Preview failed: {error}",
                        }
                        st.rerun()
            with actions_right:
                if st.button("Generate Pandas code"):
                    if not mapping_decisions:
                        st.session_state["last_action"] = {
                            "level": "warning",
                            "message": "Add at least one accepted or needs-review mapping before generating code.",
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
                            "message": f"Code generation failed: {error}",
                        }
                        st.rerun()
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