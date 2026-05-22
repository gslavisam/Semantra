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


def _section_label(title: str, detail: str | None = None) -> str:
    detail_text = str(detail or "").strip()
    return f"{title} · {detail_text}" if detail_text else title


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
    if proposal_type == "switch_target":
        current_entry["target"] = str(proposal.get("proposed_target") or "").strip()
        current_entry["status"] = "accepted"
        _record_decision_audit(
            source,
            origin="llm_proposal",
            details={
                "mode": "switch_target",
                "proposal_origin": str(proposal.get("origin") or ""),
                "confidence": float(proposal.get("confidence", 0.0) or 0.0),
            },
        )
        return bool(current_entry.get("target"))
    if proposal_type == "accept_current":
        if not actual_target and expected_target:
            current_entry["target"] = expected_target
        current_entry["status"] = "accepted"
        _record_decision_audit(
            source,
            origin="llm_proposal",
            details={
                "mode": "accept_current",
                "proposal_origin": str(proposal.get("origin") or ""),
                "confidence": float(proposal.get("confidence", 0.0) or 0.0),
            },
        )
        return bool(current_entry.get("target"))
    if proposal_type == "reject":
        if not actual_target and expected_target:
            current_entry["target"] = expected_target
        current_entry["status"] = "rejected"
        _record_decision_audit(
            source,
            origin="llm_proposal",
            details={
                "mode": "reject",
                "proposal_origin": str(proposal.get("origin") or ""),
                "confidence": float(proposal.get("confidence", 0.0) or 0.0),
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
