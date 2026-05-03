from __future__ import annotations

import json

import httpx
import streamlit as st


def render_manual_mapping_panel(
    mapping_response: dict,
    *,
    schema_column_names,
    build_mapping_decisions,
    upsert_manual_mapping,
    manual_mapping_rows,
    remove_manual_mapping,
) -> None:
    upload_response = st.session_state.get("upload_response")
    if not upload_response:
        return

    st.subheader("Add Manual Mapping")
    st.caption("Add or override a source-to-target pair even when the auto-mapper did not propose it.")

    source_columns = schema_column_names(upload_response["source"])
    target_columns = schema_column_names(upload_response["target"])
    active_sources = {decision["source"] for decision in build_mapping_decisions()}
    preferred_sources = [source for source in source_columns if source not in active_sources]
    source_options = preferred_sources or source_columns

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
        st.session_state["last_action"] = {
            "level": "success",
            "message": f"Added manual mapping {selected_source} -> {selected_target}.",
        }
        st.rerun()

    manual_rows = manual_mapping_rows(mapping_response)
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
    decisions = build_mapping_decisions()
    if not decisions:
        st.warning("No active mapping decisions. Accept or mark at least one candidate as needs review.")
        return
    st.subheader("Active Decisions")
    st.dataframe(decisions, width="stretch", hide_index=True)


def render_mapping_io_panel(
    *,
    build_mapping_decisions,
    export_mapping_payload,
    apply_imported_mapping_payload,
    api_request,
    build_mapping_set_payload,
) -> None:
    st.subheader("Export / Import Decisions")
    decisions = build_mapping_decisions()
    export_disabled = not decisions
    st.download_button(
        "Download mapping JSON",
        data=export_mapping_payload(),
        file_name="semantra_mapping_decisions.json",
        mime="application/json",
        disabled=export_disabled,
        use_container_width=True,
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

    st.caption("Save a versioned mapping set to the backend or reload a saved version into the current review state.")
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
        saved_mapping_set_actions = st.columns([2, 2])
        if saved_mapping_set_actions[0].button(
            "Apply saved mapping set",
            width="stretch",
            key="apply_saved_mapping_set",
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
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, UnicodeDecodeError) as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Applying saved mapping set failed: {error}",
                }
                st.rerun()

        target_status = saved_mapping_set_actions[1].selectbox(
            "Saved mapping set status",
            ["draft", "review", "approved", "archived"],
            index=["draft", "review", "approved", "archived"].index(selected_mapping_set.get("status", "draft")),
            key="selected_saved_mapping_set_status",
        )
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


def render_correction_panel(
    *,
    build_pending_corrections,
    admin_token_required,
    api_request,
    persist_corrections,
) -> None:
    pending_corrections = build_pending_corrections()
    st.subheader("Save Corrections")
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
        disabled=(not pending_corrections) or (token_required and not admin_token),
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