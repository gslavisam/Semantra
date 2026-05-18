from __future__ import annotations

import httpx
import streamlit as st


def _normalized_text(value: str | None) -> str:
    return str(value or "").strip().lower()


def _parse_hint_sample_values(value: str) -> list[str]:
    normalized = str(value or "").replace("\n", ",")
    parsed: list[str] = []
    for item in normalized.split(","):
        text = item.strip()
        if text and text not in parsed:
            parsed.append(text)
    return parsed


def _current_hint_scope() -> tuple[str | None, str | None, str | None]:
    return (
        str(st.session_state.get("analysis_source_system") or "").strip() or None,
        str(st.session_state.get("analysis_business_domain") or "").strip() or None,
        str(st.session_state.get("analysis_integration_name") or "").strip() or None,
    )


def _load_source_field_hint_map(api_request) -> dict[str, dict]:
    source_system, business_domain, integration_name = _current_hint_scope()
    if not source_system:
        st.session_state["source_field_hint_scope_signature"] = None
        st.session_state["source_field_hint_records"] = {}
        return {}

    scope_signature = (source_system, business_domain, integration_name)
    cached_signature = st.session_state.get("source_field_hint_scope_signature")
    if cached_signature == scope_signature:
        cached_records = st.session_state.get("source_field_hint_records") or {}
        if isinstance(cached_records, dict):
            return cached_records

    hint_records = api_request(
        "GET",
        "/mapping/source-field-hints",
        params={
            "source_system": source_system,
            "business_domain": business_domain,
            "integration_name": integration_name,
        },
    )
    hint_map = {
        _normalized_text(record.get("source_field")): record
        for record in hint_records or []
        if _normalized_text(record.get("source_field"))
    }
    st.session_state["source_field_hint_scope_signature"] = scope_signature
    st.session_state["source_field_hint_records"] = hint_map
    return hint_map


def _load_source_field_hint_records_for_system(api_request) -> list[dict]:
    source_system, _business_domain, _integration_name = _current_hint_scope()
    if not source_system:
        st.session_state["source_field_hint_system_signature"] = None
        st.session_state["source_field_hint_system_records"] = []
        return []

    cached_signature = st.session_state.get("source_field_hint_system_signature")
    if cached_signature == source_system:
        cached_records = st.session_state.get("source_field_hint_system_records") or []
        if isinstance(cached_records, list):
            return cached_records

    records = api_request(
        "GET",
        "/mapping/source-field-hints",
        params={"source_system": source_system, "active_only": False},
    )
    st.session_state["source_field_hint_system_signature"] = source_system
    st.session_state["source_field_hint_system_records"] = list(records or [])
    return list(records or [])


def _applied_source_field_hint_map(mapping_response: dict) -> dict[str, dict]:
    records = mapping_response.get("applied_source_field_hints") or []
    return {
        _normalized_text(record.get("source_field")): record
        for record in records
        if _normalized_text(record.get("source_field"))
    }


def _invalidate_source_field_hint_cache() -> None:
    st.session_state.pop("source_field_hint_scope_signature", None)
    st.session_state.pop("source_field_hint_records", None)
    st.session_state.pop("source_field_hint_system_signature", None)
    st.session_state.pop("source_field_hint_system_records", None)


def _compose_llm_mapping_refinement_instruction(*parts: str) -> str:
    return "\n\n".join(part.strip() for part in parts if str(part or "").strip())


def _remember_llm_mapping_refinement(
    entry: dict,
    *,
    refinement_response: dict,
    current_target: str,
    current_status: str,
    instruction: str,
) -> None:
    entry["llm_mapping_refinement"] = refinement_response
    entry["llm_mapping_refinement_previous_target"] = current_target
    entry["llm_mapping_refinement_previous_status"] = current_status
    entry["llm_mapping_instruction"] = instruction
    entry["llm_mapping_refinement_instruction"] = instruction
    entry["llm_mapping_refinement_applied"] = False


def _apply_llm_mapping_refinement(entry: dict) -> str:
    refinement_response = entry.get("llm_mapping_refinement") if isinstance(entry.get("llm_mapping_refinement"), dict) else {}
    selected = refinement_response.get("selected") or {}
    selected_target = str(selected.get("target") or "").strip()
    if not selected_target:
        return ""
    entry["target"] = selected_target
    entry["status"] = "needs_review"
    entry["llm_mapping_refinement_applied"] = True
    return selected_target


def _clear_llm_mapping_refinement(entry: dict, *, restore_previous: bool) -> None:
    if restore_previous:
        entry["target"] = str(entry.get("llm_mapping_refinement_previous_target") or "")
        entry["status"] = str(entry.get("llm_mapping_refinement_previous_status") or "needs_review")
    entry.pop("llm_mapping_refinement", None)
    entry.pop("llm_mapping_refinement_previous_target", None)
    entry.pop("llm_mapping_refinement_previous_status", None)
    entry.pop("llm_mapping_refinement_applied", None)


def _render_llm_mapping_refine_panel(
    *,
    trust_rows: list[dict],
    ranked_by_source: dict[str, dict],
    editor_state: dict,
    source_field_hint_map: dict[str, dict],
    llm_runtime_enabled,
    request_llm_mapping_refinement,
) -> None:
    low_confidence_rows = [
        mapping for mapping in trust_rows if float(mapping.get("confidence", 0.0) or 0.0) < 0.7
    ]
    with st.expander(
        _section_label("LLM Mapping Refine", f"{len(low_confidence_rows)} low-confidence" if low_confidence_rows else None),
        expanded=bool(low_confidence_rows),
    ):
        st.caption(
            "Enter shared guidance for the LLM here, then batch-refine low-confidence rows. "
            "Per-row LLM refine instructions remain available inside each row's Details panel. "
            "Unlike the explanation panels below, this surface can change row-level target proposals."
        )
        batch_instruction = st.text_area(
            "Batch LLM refine instruction",
            key="llm_mapping_batch_prompt",
            placeholder="Example: Prefer business meaning over technical abbreviations and choose the target that best represents transaction or operation type.",
        )
        if st.button(
            "Batch refine low-confidence rows",
            key="batch_refine_low_confidence_rows",
            width="stretch",
            disabled=(not llm_runtime_enabled()) or (not low_confidence_rows),
            help="Runs the closed-set LLM refine flow for every low-confidence row using the shared batch instruction plus any row-specific hints.",
        ):
            refined_count = 0
            no_match_count = 0
            skipped_count = 0
            for mapping in low_confidence_rows:
                source = str(mapping.get("source") or "").strip()
                if not source:
                    continue
                ranked = ranked_by_source.get(source) or {}
                candidate_targets = [
                    str(candidate.get("target") or "").strip()
                    for candidate in ranked.get("candidates", [])
                    if str(candidate.get("target") or "").strip()
                ]
                if not candidate_targets:
                    skipped_count += 1
                    continue
                entry = editor_state.setdefault(source, {})
                saved_hint = source_field_hint_map.get(_normalized_text(source)) or {}
                meaning_hint = str(
                    st.session_state.get(
                        f"field_hint_meaning_{source}",
                        entry.get("field_hint_meaning") or saved_hint.get("meaning_hint") or "",
                    )
                )
                negative_hint = str(
                    st.session_state.get(
                        f"field_hint_negative_{source}",
                        entry.get("field_hint_negative") or saved_hint.get("negative_hint") or "",
                    )
                )
                sample_values = _parse_hint_sample_values(
                    str(
                        st.session_state.get(
                            f"field_hint_samples_{source}",
                            ", ".join(saved_hint.get("sample_values") or []),
                        )
                    )
                )
                row_instruction = str(
                    st.session_state.get(
                        f"llm_mapping_prompt_{source}",
                        entry.get("llm_mapping_instruction") or "",
                    )
                )
                combined_instruction = _compose_llm_mapping_refinement_instruction(batch_instruction, row_instruction)
                try:
                    refinement_response = request_llm_mapping_refinement(
                        source,
                        candidate_targets=candidate_targets,
                        meaning_hint=meaning_hint,
                        negative_hint=negative_hint,
                        sample_values=sample_values,
                        refinement_instruction=combined_instruction,
                    )
                except (ValueError, httpx.HTTPError) as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Batch LLM mapping refine failed on {source}: {error}",
                    }
                    st.rerun()
                    return

                _remember_llm_mapping_refinement(
                    entry,
                    refinement_response=refinement_response,
                    current_target=str(entry.get("target") or mapping.get("target") or ""),
                    current_status=str(entry.get("status") or "needs_review"),
                    instruction=combined_instruction,
                )
                selected_refinement = refinement_response.get("selected") or {}
                if str(selected_refinement.get("target") or "").strip():
                    refined_count += 1
                else:
                    no_match_count += 1
            st.session_state["last_action"] = {
                "level": "success",
                "message": (
                    f"Prepared LLM refine previews for {refined_count} row(s); "
                    f"{no_match_count} returned no_match and {skipped_count} were skipped. "
                    "Use Accept refined mapping inside each row to apply a suggestion."
                ),
            }
            st.rerun()

        if not llm_runtime_enabled():
            st.caption("LLM mapping refine is disabled. Enable a runtime provider in backend config to use this panel.")


def _render_saved_source_field_hints_panel(api_request) -> None:
    source_system, _business_domain, _integration_name = _current_hint_scope()
    label = "Saved Source Field Hints"
    if not source_system:
        with st.expander(label, expanded=False):
            st.info("Set Source system in the workspace context to review and manage saved field hints.")
        return

    records = _load_source_field_hint_records_for_system(api_request)
    detail = f"{len(records)} for {source_system}" if records else f"0 for {source_system}"
    with st.expander(_section_label(label, detail), expanded=False):
        st.caption("Review, edit, and deactivate persistent hints saved for the active source system.")
        if not records:
            st.info("No persistent field hints are saved for this source system yet.")
            return

        st.dataframe(
            [
                {
                    "source_field": record.get("source_field"),
                    "business_domain": record.get("business_domain") or "",
                    "integration_name": record.get("integration_name") or "",
                    "active": bool(record.get("active", False)),
                    "meaning_hint": record.get("meaning_hint") or "",
                    "sample_values": ", ".join(record.get("sample_values") or []),
                }
                for record in records
            ],
            width="stretch",
            hide_index=True,
        )

        for record in records:
            hint_id = int(record.get("hint_id") or 0)
            source_field = str(record.get("source_field") or "").strip() or "unknown"
            if f"saved_field_hint_meaning_{hint_id}" not in st.session_state:
                st.session_state[f"saved_field_hint_meaning_{hint_id}"] = str(record.get("meaning_hint") or "")
            if f"saved_field_hint_negative_{hint_id}" not in st.session_state:
                st.session_state[f"saved_field_hint_negative_{hint_id}"] = str(record.get("negative_hint") or "")
            if f"saved_field_hint_samples_{hint_id}" not in st.session_state:
                st.session_state[f"saved_field_hint_samples_{hint_id}"] = ", ".join(record.get("sample_values") or [])

            status_label = "active" if record.get("active") else "inactive"
            with st.expander(f"Hint: {source_field} | {status_label}", expanded=False):
                st.caption(
                    " | ".join(
                        part
                        for part in (
                            f"source_system={record.get('source_system') or source_system}",
                            f"business_domain={record.get('business_domain')}" if record.get("business_domain") else "",
                            f"integration_name={record.get('integration_name')}" if record.get("integration_name") else "",
                        )
                        if part
                    )
                )
                st.text_area(
                    f"Meaning for {source_field}",
                    key=f"saved_field_hint_meaning_{hint_id}",
                )
                st.text_input(
                    f"Negative guidance for {source_field}",
                    key=f"saved_field_hint_negative_{hint_id}",
                )
                st.text_input(
                    f"Sample values for {source_field}",
                    key=f"saved_field_hint_samples_{hint_id}",
                )
                action_columns = st.columns(2)
                if action_columns[0].button("Save changes", key=f"saved_field_hint_update_{hint_id}", width="stretch"):
                    try:
                        api_request(
                            "POST",
                            "/mapping/source-field-hints",
                            json={
                                "source_system": record.get("source_system") or source_system,
                                "business_domain": record.get("business_domain"),
                                "integration_name": record.get("integration_name"),
                                "source_field": source_field,
                                "meaning_hint": st.session_state.get(f"saved_field_hint_meaning_{hint_id}", ""),
                                "negative_hint": st.session_state.get(f"saved_field_hint_negative_{hint_id}", ""),
                                "sample_values": _parse_hint_sample_values(
                                    st.session_state.get(f"saved_field_hint_samples_{hint_id}", "")
                                ),
                                "active": bool(record.get("active", True)),
                            },
                        )
                        _invalidate_source_field_hint_cache()
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Updated persistent hint for {source_field}.",
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Updating source field hint failed: {error}",
                        }
                        st.rerun()

                toggle_label = "Deactivate hint" if record.get("active") else "Activate hint"
                if action_columns[1].button(toggle_label, key=f"saved_field_hint_toggle_{hint_id}", width="stretch"):
                    try:
                        api_request(
                            "POST",
                            "/mapping/source-field-hints",
                            json={
                                "source_system": record.get("source_system") or source_system,
                                "business_domain": record.get("business_domain"),
                                "integration_name": record.get("integration_name"),
                                "source_field": source_field,
                                "meaning_hint": st.session_state.get(f"saved_field_hint_meaning_{hint_id}", ""),
                                "negative_hint": st.session_state.get(f"saved_field_hint_negative_{hint_id}", ""),
                                "sample_values": _parse_hint_sample_values(
                                    st.session_state.get(f"saved_field_hint_samples_{hint_id}", "")
                                ),
                                "active": not bool(record.get("active", True)),
                            },
                        )
                        _invalidate_source_field_hint_cache()
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": (
                                f"{'Deactivated' if record.get('active') else 'Activated'} persistent hint for {source_field}."
                            ),
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Changing source field hint status failed: {error}",
                        }
                        st.rerun()


def _canonical_gap_candidate_key(candidate: dict) -> str:
    source = str(candidate.get("source") or "").strip() or "unknown"
    target = str(candidate.get("target") or "").strip() or "unknown"
    return f"canonical_gap_{source}_{target}".replace(" ", "_")


def _canonical_gap_proposal_state(candidate_key: str, proposal_states: dict[str, str] | None = None) -> str:
    state = str((proposal_states or {}).get(candidate_key) or "").strip() or "new"
    if state not in {"new", "needs_review", "ready_for_approval"}:
        return "new"
    return state


def _canonical_gap_approval_block_reason(suggestion: dict | None, proposal_state: str) -> str:
    if not suggestion or suggestion.get("action") == "no_action":
        return "Generate a usable non-'no_action' canonical gap suggestion before approving."
    if proposal_state != "ready_for_approval":
        return (
            "Move proposal triage to 'Ready for approval' before approving and persisting this canonical gap. "
            f"Current state: {proposal_state}."
        )
    return ""


def _canonical_gap_triage_payload(
    candidates: list[dict] | None,
    suggestions: dict[str, dict] | None,
    proposal_states: dict[str, str] | None,
) -> dict:
    return {
        "candidates": list(candidates or []),
        "suggestions": dict(suggestions or {}),
        "proposal_states": dict(proposal_states or {}),
    }


def _canonical_gap_triage_group_rows(triage_summary: dict | None) -> list[dict]:
    rows: list[dict] = []
    for group in (triage_summary or {}).get("groups") or []:
        rows.append(
            {
                "priority": group.get("priority"),
                "focus": group.get("focus"),
                "count": group.get("count"),
                "suggestion_action": group.get("suggestion_action"),
                "proposal_state": group.get("proposal_state"),
                "source_examples": ", ".join(group.get("source_examples") or []),
                "recommended_follow_up": group.get("recommended_follow_up"),
            }
        )
    return rows


def _review_attention_summary_rows(selected_rows: list[dict] | None) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in selected_rows or []:
        target = str(row.get("target") or "").strip()
        confidence_label = str(row.get("confidence_label") or "").strip()
        issue_type = ""
        if not target:
            issue_type = "unmatched"
        elif confidence_label == "low_confidence":
            issue_type = "low_confidence"
        if not issue_type:
            continue

        canonical_status = str(row.get("canonical_status_label") or row.get("canonical_status") or "").strip() or "Unknown"
        focus = (
            target
            or str(row.get("shared_concepts") or "").strip()
            or str(row.get("source_concepts") or "").strip()
            or str(row.get("target_concepts") or "").strip()
            or canonical_status
        )
        group_key = (issue_type, focus, canonical_status)
        group = grouped.setdefault(
            group_key,
            {
                "issue_type": issue_type,
                "focus": focus,
                "canonical_status": canonical_status,
                "count": 0,
                "source_examples": [],
            },
        )
        group["count"] = int(group["count"]) + 1
        source = str(row.get("source") or "").strip()
        source_examples = group["source_examples"]
        if source and isinstance(source_examples, list) and source not in source_examples and len(source_examples) < 4:
            source_examples.append(source)

    rows: list[dict] = []
    for group in grouped.values():
        issue_type = str(group["issue_type"])
        canonical_status = str(group["canonical_status"])
        follow_up = "Review target ranking or metadata context."
        if canonical_status.lower() in {"no canonical match", "source-only canonical match", "target-only canonical match", "different canonical concepts"}:
            follow_up = "Check glossary/knowledge coverage before forcing target decisions."
        if issue_type == "unmatched":
            follow_up = "Check missing glossary coverage or absent viable target candidates."
        rows.append(
            {
                "issue_type": issue_type,
                "focus": group["focus"],
                "canonical_status": canonical_status,
                "count": group["count"],
                "source_examples": ", ".join(group["source_examples"]),
                "follow_up": follow_up,
            }
        )

    return sorted(
        rows,
        key=lambda item: (
            item.get("issue_type") != "unmatched",
            -int(item.get("count") or 0),
            str(item.get("focus") or "").lower(),
        ),
    )


def _section_label(title: str, detail: str | None = None) -> str:
    detail_text = str(detail or "").strip()
    return f"{title} · {detail_text}" if detail_text else title


def _manual_review_open_item_count(mapping_response: dict, editor_state: dict, *, selected_target_options) -> int:
    open_count = 0
    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked.get("source") or ""
        options = selected_target_options(ranked)
        current = editor_state.get(source, {"target": options[0] if options else "", "status": "needs_review"})
        target = str(current.get("target") or "").strip()
        status = str(current.get("status") or "needs_review").strip() or "needs_review"
        if status != "accepted" or not target:
            open_count += 1
    return open_count


def _review_plan_request_payload(
    filtered_rows: list[dict] | None,
    attention_summary_rows: list[dict] | None,
    *,
    status_filter: str,
    confidence_filter: str,
    source_filter: str,
) -> dict:
    return {
        "filtered_rows": list(filtered_rows or []),
        "attention_summary_rows": list(attention_summary_rows or []),
        "filters": {
            "status": status_filter,
            "confidence_label": confidence_filter,
            "source": source_filter,
        },
    }


def _review_plan_cluster_rows(plan_summary: dict | None) -> list[dict]:
    rows: list[dict] = []
    for cluster in (plan_summary or {}).get("clusters") or []:
        rows.append(
            {
                "priority": cluster.get("priority"),
                "issue_type": cluster.get("issue_type"),
                "focus": cluster.get("focus"),
                "canonical_status": cluster.get("canonical_status"),
                "count": cluster.get("count"),
                "source_examples": ", ".join(cluster.get("source_examples") or []),
                "recommended_follow_up": cluster.get("recommended_follow_up"),
            }
        )
    return rows


def render_mapping_analysis_panel(
    mapping_response: dict,
    *,
    request_mapping_analysis_audio,
    request_mapping_analysis_narration,
    request_mapping_analysis_summary,
) -> None:
    summary = st.session_state.get("mapping_analysis_summary")
    analysis_error = st.session_state.get("mapping_analysis_error")
    spoken_script = str(st.session_state.get("mapping_analysis_spoken_script") or "").strip()
    audio_bytes = st.session_state.get("mapping_analysis_audio_bytes")
    audio_mime_type = str(st.session_state.get("mapping_analysis_audio_mime_type") or "audio/wav")
    audio_error = st.session_state.get("mapping_analysis_audio_error")
    force_open = bool(st.session_state.pop("mapping_analysis_force_open", False))
    analysis_label = "Mapping Analysis Overview"
    if summary:
        metadata = summary.get("generation_metadata") or {}
        analysis_label = _section_label(
            analysis_label,
            "LLM summary" if metadata.get("used_llm") else "Fallback summary",
        )

    with st.expander(analysis_label, expanded=(summary is None or analysis_error is not None or force_open)):
        st.caption(
            "Generate one structured technical overview of the current mapping state before drilling into row-level trust evidence. "
            "This is a read-only explanation surface and does not change decisions or approval state."
        )

        action_col, audio_col = st.columns([1, 1])
        action_label = "Refresh mapping overview" if summary else "Generate mapping overview"
        if action_col.button(action_label, key="generate_mapping_analysis_summary", width="stretch"):
            try:
                with st.spinner("Generating mapping analysis overview..."):
                    st.session_state["mapping_analysis_summary"] = request_mapping_analysis_summary()
                st.session_state.pop("mapping_analysis_error", None)
                st.session_state.pop("mapping_analysis_spoken_script", None)
                st.session_state.pop("mapping_analysis_audio_bytes", None)
                st.session_state.pop("mapping_analysis_audio_mime_type", None)
                st.session_state.pop("mapping_analysis_audio_error", None)
                st.session_state["mapping_analysis_force_open"] = True
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Generated a technical mapping analysis overview for the current review state.",
                }
                st.rerun()
            except (ValueError, httpx.HTTPError) as error:
                st.session_state["mapping_analysis_error"] = str(error)
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Mapping analysis generation failed: {error}",
                }
                st.rerun()
        if audio_col.button(
            "Generate audio",
            key="generate_mapping_analysis_audio",
            width="stretch",
            disabled=not bool(summary),
        ):
            try:
                with st.spinner("Generating narration and audio..."):
                    narration_response = request_mapping_analysis_narration()
                    spoken_script = str(narration_response.get("spoken_script") or "").strip()
                    audio_bytes, audio_mime_type = request_mapping_analysis_audio(spoken_script)
                    st.session_state["mapping_analysis_spoken_script"] = spoken_script
                    st.session_state["mapping_analysis_audio_bytes"] = audio_bytes
                    st.session_state["mapping_analysis_audio_mime_type"] = audio_mime_type
                st.session_state.pop("mapping_analysis_audio_error", None)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Generated Orpheus audio narration for the current mapping analysis overview.",
                }
                st.rerun()
            except (ValueError, httpx.HTTPError) as error:
                st.session_state["mapping_analysis_audio_error"] = str(error)
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Mapping analysis audio generation failed: {error}",
                }
                st.rerun()

        if analysis_error and not summary:
            st.error(f"Analysis generation failed: {analysis_error}")

        if not summary:
            st.info("No mapping overview has been generated yet. Use this panel to create a technical readout of the current mapping state.")
            return

        metadata = summary.get("generation_metadata") or {}
        llm_status = "LLM summary" if metadata.get("used_llm") else "Fallback summary"
        fallback_suffix = " with fallback contract" if metadata.get("fallback_used") else ""
        st.caption(f"{llm_status}{fallback_suffix}")
        if audio_error:
            st.error(f"Audio generation failed: {audio_error}")
        if audio_bytes:
            st.audio(audio_bytes, format=audio_mime_type)
            st.download_button(
                "Download audio",
                data=audio_bytes,
                file_name="mapping_analysis.wav",
                mime=audio_mime_type,
                key="download_mapping_analysis_audio",
                width="stretch",
            )

        health = summary.get("overall_mapping_health") or {}
        metric_columns = st.columns(4)
        metric_columns[0].metric("Accepted", int(health.get("accepted_count") or 0))
        metric_columns[1].metric("Needs review", int(health.get("needs_review_count") or 0))
        metric_columns[2].metric("Unmatched", int(health.get("unmatched_count") or 0))
        metric_columns[3].metric("Overall risk", str(health.get("overall_risk") or "n/a").replace("_", " ").title())
        if health.get("summary"):
            st.write(str(health.get("summary")))

        left, right = st.columns(2)
        with left:
            st.markdown("#### Strongest matches")
            strongest_matches = summary.get("strongest_matches") or []
            if strongest_matches:
                for item in strongest_matches:
                    st.write(
                        f"{item.get('source') or 'source'} -> {item.get('target') or 'target'} "
                        f"({round(float(item.get('confidence') or 0.0) * 100)}%)"
                    )
                    if item.get("why_it_is_strong"):
                        st.caption(str(item.get("why_it_is_strong")))
            else:
                st.info("No strongest-match highlights are available for the current payload.")
        with right:
            st.markdown("#### Needs review")
            review_items = summary.get("needs_review_items") or []
            if review_items:
                for item in review_items:
                    st.write(
                        f"{item.get('source') or 'source'} -> {item.get('proposed_target') or 'unmapped'} "
                        f"({round(float(item.get('confidence') or 0.0) * 100)}%)"
                    )
                    if item.get("review_reason"):
                        st.caption(str(item.get("review_reason")))
            else:
                st.info("No active review queue items are highlighted in the current payload.")

        st.markdown("#### Canonical coverage and findings")
        canonical_summary = summary.get("canonical_coverage_summary") or {}
        coverage_columns = st.columns(3)
        coverage_columns[0].metric("Source coverage", f"{round(float(canonical_summary.get('source_coverage') or 0.0) * 100)}%")
        coverage_columns[1].metric("Target coverage", f"{round(float(canonical_summary.get('target_coverage') or 0.0) * 100)}%")
        coverage_columns[2].metric("Project coverage", f"{round(float(canonical_summary.get('project_coverage') or 0.0) * 100)}%")
        if canonical_summary.get("coverage_interpretation"):
            st.caption(str(canonical_summary.get("coverage_interpretation")))
        shared_concepts = canonical_summary.get("shared_concepts") or []
        if shared_concepts:
            st.write("Shared concepts: " + ", ".join(str(item) for item in shared_concepts))

        lower_left, lower_right = st.columns(2)
        with lower_left:
            st.markdown("#### Transformation hotspots")
            hotspots = summary.get("transformation_hotspots") or []
            if hotspots:
                for item in hotspots:
                    st.write(
                        f"{item.get('source') or 'source'} -> {item.get('target') or 'target'} "
                        f"({str(item.get('transformation_risk') or 'low').replace('_', ' ').title()} risk)"
                    )
                    if item.get("reason"):
                        st.caption(str(item.get("reason")))
            else:
                st.info("No transformation hotspots are currently flagged.")
        with lower_right:
            st.markdown("#### Implementation risks")
            risks = summary.get("implementation_risks") or []
            if risks:
                for risk in risks:
                    st.write(f"- {risk}")
            else:
                st.info("No implementation risks were returned for the current payload.")

        st.markdown("#### Recommended next actions")
        next_actions = summary.get("recommended_next_actions") or []
        if next_actions:
            for index, action in enumerate(next_actions, start=1):
                st.write(f"{index}. {action}")
        else:
            st.info("No explicit next actions were returned for the current payload.")

        with st.expander("Narration preview"):
            narration_text = spoken_script or str(summary.get("narration_script_seed") or "").strip()
            if narration_text:
                st.write(narration_text)
            else:
                st.info("Narration seed is empty for the current summary.")


def display_trust_layer(
    mapping_response: dict,
    *,
    trust_layer_rows,
    has_knowledge_match,
    has_canonical_match,
    canonical_concept_labels,
    transformation_mode_label,
    llm_runtime_enabled,
    request_llm_mapping_refinement,
    request_llm_transformation_suggestion,
    request_transformation_templates,
    materialize_transformation_template,
    api_request=None,
) -> None:
    trust_rows = trust_layer_rows(mapping_response)
    ranked_by_source = {item.get("source"): item for item in mapping_response.get("ranked_mappings", [])}
    editor_state = st.session_state.setdefault("mapping_editor_state", {})
    source_field_hint_map: dict[str, dict] = {}
    applied_hint_map = _applied_source_field_hint_map(mapping_response)
    if api_request is not None:
        try:
            source_field_hint_map = _load_source_field_hint_map(api_request)
        except httpx.HTTPError:
            source_field_hint_map = {}
    low_confidence_count = sum(1 for mapping in trust_rows if float(mapping.get("confidence", 0.0) or 0.0) < 0.7)
    st.subheader(_section_label("🎯 Mapping Trust Layer", f"{low_confidence_count} low-confidence" if low_confidence_count else None))
    canonical_only = (st.session_state.get("upload_response") or {}).get("mapping_mode") == "canonical"
    canonical_coverage = mapping_response.get("canonical_coverage") or {}
    source_coverage = canonical_coverage.get("source") or {}
    target_coverage = canonical_coverage.get("target") or {}
    project_coverage = canonical_coverage.get("project") or {}
    if source_coverage or target_coverage:
        st.caption(
            "Canonical coverage: "
            f"source={int(float(source_coverage.get('coverage_ratio', 0.0) or 0.0) * 100)}% "
            f"({source_coverage.get('matched_columns', 0)}/{source_coverage.get('total_columns', 0)}), "
            f"target={int(float(target_coverage.get('coverage_ratio', 0.0) or 0.0) * 100)}% "
            f"({target_coverage.get('matched_columns', 0)}/{target_coverage.get('total_columns', 0)}), "
            f"project={int(float(project_coverage.get('coverage_ratio', 0.0) or 0.0) * 100)}% "
            f"({project_coverage.get('matched_columns', 0)}/{project_coverage.get('total_columns', 0)})."
        )
        if project_coverage:
            st.caption(
                "Project concepts: "
                f"{project_coverage.get('concept_count', 0)} total, "
                f"{project_coverage.get('shared_concept_count', 0)} shared across source and target."
            )
    _render_llm_mapping_refine_panel(
        trust_rows=trust_rows,
        ranked_by_source=ranked_by_source,
        editor_state=editor_state,
        source_field_hint_map=source_field_hint_map,
        llm_runtime_enabled=llm_runtime_enabled,
        request_llm_mapping_refinement=request_llm_mapping_refinement,
    )
    if api_request is not None:
        _render_saved_source_field_hints_panel(api_request)
    for mapping in trust_rows:
        source = mapping["source"]
        entry = editor_state.setdefault(source, {})
        ranked = ranked_by_source.get(source) or {}
        ranked_candidate_targets = [
            str(candidate.get("target") or "").strip()
            for candidate in ranked.get("candidates", [])
            if str(candidate.get("target") or "").strip()
        ]
        refinement_result = entry.get("llm_mapping_refinement") if isinstance(entry.get("llm_mapping_refinement"), dict) else {}
        refinement_selected = refinement_result.get("selected") or {}
        refinement_selected_target = str(refinement_selected.get("target") or "").strip()
        refinement_applied = bool(entry.get("llm_mapping_refinement_applied", False))
        applied_hint = applied_hint_map.get(_normalized_text(source)) or {}
        saved_hint = source_field_hint_map.get(_normalized_text(source)) or {}
        suggested_code = mapping.get("suggested_transformation_code") or ""
        if suggested_code and f"transform_{source}" not in st.session_state:
            st.session_state[f"transform_{source}"] = bool(entry.get("apply_transformation", False))
        if f"llm_transform_prompt_{source}" not in st.session_state:
            st.session_state[f"llm_transform_prompt_{source}"] = entry.get("llm_transformation_instruction", "")
        if f"manual_transform_{source}" not in st.session_state:
            st.session_state[f"manual_transform_{source}"] = entry.get("manual_transformation_code", "")
        if f"manual_apply_{source}" not in st.session_state:
            st.session_state[f"manual_apply_{source}"] = bool(entry.get("manual_apply_transformation", False))
        if f"field_hint_meaning_{source}" not in st.session_state:
            st.session_state[f"field_hint_meaning_{source}"] = str(saved_hint.get("meaning_hint") or "")
        if f"field_hint_negative_{source}" not in st.session_state:
            st.session_state[f"field_hint_negative_{source}"] = str(saved_hint.get("negative_hint") or "")
        if f"field_hint_samples_{source}" not in st.session_state:
            st.session_state[f"field_hint_samples_{source}"] = ", ".join(saved_hint.get("sample_values") or [])
        if f"llm_mapping_prompt_{source}" not in st.session_state:
            st.session_state[f"llm_mapping_prompt_{source}"] = str(entry.get("llm_mapping_instruction") or "")

        col1, col2, col3 = st.columns([3, 3, 2])
        with col1:
            st.info(f"Source: **{source}**")
        with col2:
            st.success(f"Target: **{mapping.get('target') or '—'}**")
            llm_recommendation = (
                refinement_selected.get("llm_recommendation")
                if refinement_applied and refinement_selected_target == str(mapping.get("target") or "").strip()
                else mapping.get("llm_recommendation")
            ) or {}
            llm_decision_proposition = (
                refinement_selected.get("llm_decision_proposition")
                if refinement_applied and refinement_selected_target == str(mapping.get("target") or "").strip()
                else mapping.get("llm_decision_proposition")
            ) or {}
            if (mapping.get("llm_consulted") or refinement_applied) and llm_recommendation:
                llm_target = llm_recommendation.get("selected_target") or "unmapped"
                llm_confidence = round(float(llm_recommendation.get("confidence", 0.0) or 0.0) * 100)
                if llm_target != (mapping.get("target") or ""):
                    st.caption(
                        f"LLM consulted: recommended {llm_target} ({llm_confidence}%), but the final target differs after global assignment."
                    )
                else:
                    st.caption(f"LLM consulted: confirmed {llm_target} ({llm_confidence}%).")
            if has_knowledge_match(mapping.get("signals"), mapping.get("explanation")):
                st.caption("Knowledge-backed match")
            if has_canonical_match(mapping.get("signals"), mapping.get("explanation")):
                st.caption("Canonical-backed match")
                canonical_labels = canonical_concept_labels(mapping.get("canonical_details"))
                if canonical_labels:
                    st.caption("Canonical concept: " + ", ".join(canonical_labels))
            if applied_hint:
                applied_hint_text = str(applied_hint.get("meaning_hint") or "").strip()
                if applied_hint_text:
                    st.caption(f"Persistent hint applied in this run: {applied_hint_text}")
                else:
                    st.caption("Persistent hint applied in this run.")
            elif saved_hint:
                st.caption("Persistent hint exists for this scope. Re-run mapping to apply it to the current results.")
            if refinement_result and not refinement_selected_target:
                st.caption("LLM refine preview: no reliable match in the current closed candidate set.")
            elif refinement_result and refinement_selected_target and not refinement_applied:
                st.caption(f"LLM refine preview: {refinement_selected_target}. Open Details and accept it if you want to apply it.")
            elif refinement_applied and refinement_selected_target == str(mapping.get("target") or "").strip():
                st.caption("Accepted LLM refine applied in this session.")
            st.caption(transformation_mode_label(mapping["transformation_mode"]))
        with col3:
            score = mapping.get("confidence", 0.0)
            st.metric("Confidence", f"{round(float(score or 0.0) * 100)}%")
            st.progress(score)
        with st.expander(f"⚙️ Details and Transformation for {source}"):
            st.caption(transformation_mode_label(mapping["transformation_mode"]))
            reason = mapping.get("explanation", []) or mapping.get("reason", [])
            if isinstance(reason, str):
                st.write(f"**Reasoning:** {reason}")
            elif reason:
                st.write("**Reasoning:**")
                for reason_line in reason:
                    st.write(f"- {reason_line}")
            else:
                st.write("No explanation provided.")

            if mapping.get("llm_consulted") and llm_decision_proposition:
                st.write("**LLM decision proposition:**")
                st.write(f"- Summary: {llm_decision_proposition.get('summary') or 'LLM provided an additional decision proposition.'}")
                st.write(f"- Proposition type: {llm_decision_proposition.get('proposition_type') or 'n/a'}")
                st.write(
                    f"- Proposed target: {llm_decision_proposition.get('proposed_target') or 'no_match'} | "
                    f"Final target: {llm_decision_proposition.get('final_target') or 'unmapped'} | "
                    f"Confidence: {round(float(llm_decision_proposition.get('confidence', 0.0) or 0.0) * 100)}%"
                )
                st.write(
                    f"- Applied to final decision: {'yes' if llm_decision_proposition.get('applied_to_final_decision') else 'no'}"
                )
                considered_targets = llm_decision_proposition.get("considered_targets") or []
                if considered_targets:
                    st.write(f"- Considered targets: {', '.join(str(item) for item in considered_targets)}")
                rejected_targets = llm_decision_proposition.get("rejected_targets") or []
                if rejected_targets:
                    st.write(f"- Rejected targets: {', '.join(str(item) for item in rejected_targets)}")

            if refinement_result:
                st.write("**LLM mapping refinement:**")
                if refinement_selected_target:
                    st.write(
                        f"- Refined target: {refinement_selected_target} "
                        f"({round(float((refinement_selected.get('llm_recommendation') or {}).get('confidence', 0.0) or 0.0) * 100)}%)"
                    )
                else:
                    st.write("- Refined target: no_match")
                if entry.get("llm_mapping_instruction"):
                    st.write(f"- Instruction: {entry.get('llm_mapping_instruction')}")
                for reason_line in (refinement_selected.get("llm_recommendation") or {}).get("reasoning", []) or []:
                    st.write(f"- LLM refine: {reason_line}")
                if refinement_selected_target and not refinement_applied:
                    refinement_action_columns = st.columns(2)
                    if refinement_action_columns[0].button(
                        "Accept refined mapping",
                        key=f"accept_refined_mapping_{source}",
                        width="stretch",
                    ):
                        applied_target = _apply_llm_mapping_refinement(entry)
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Accepted LLM refined mapping for {source} -> {applied_target}.",
                        }
                        st.rerun()
                    if refinement_action_columns[1].button(
                        "Discard refine preview",
                        key=f"discard_refined_mapping_{source}",
                        width="stretch",
                    ):
                        _clear_llm_mapping_refinement(entry, restore_previous=False)
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Discarded the pending LLM refine preview for {source}.",
                        }
                        st.rerun()
                elif refinement_applied:
                    if st.button(
                        "Revert refined mapping",
                        key=f"revert_refined_mapping_{source}",
                        width="stretch",
                    ):
                        _clear_llm_mapping_refinement(entry, restore_previous=True)
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Reverted the accepted LLM refined mapping for {source}.",
                        }
                        st.rerun()

            if (mapping.get("llm_consulted") or refinement_applied) and llm_recommendation:
                st.write("**LLM review:**")
                st.write(
                    f"- Recommended target: {llm_recommendation.get('selected_target') or 'unmapped'} "
                    f"({round(float(llm_recommendation.get('confidence', 0.0) or 0.0) * 100)}%)"
                )
                for reason_line in llm_recommendation.get("reasoning", []) or []:
                    st.write(f"- LLM: {reason_line}")

            canonical_labels = canonical_concept_labels(mapping.get("canonical_details"))
            if canonical_labels:
                st.write("**Canonical path:**")
                st.write(f"- {source} -> {', '.join(canonical_labels)} -> {mapping.get('target') or 'unmapped'}")

            st.write("**Persistent source field hint:**")
            source_system, business_domain, integration_name = _current_hint_scope()
            if saved_hint:
                scope_parts = [f"source_system={saved_hint.get('source_system')}"]
                if saved_hint.get("business_domain"):
                    scope_parts.append(f"business_domain={saved_hint.get('business_domain')}")
                if saved_hint.get("integration_name"):
                    scope_parts.append(f"integration_name={saved_hint.get('integration_name')}")
                st.caption("Saved hint active for current scope: " + " | ".join(scope_parts))
            if applied_hint:
                st.write(
                    f"- Applied in current run: yes | meaning: {applied_hint.get('meaning_hint') or 'n/a'}"
                )
            st.write("**LLM mapping refine input:**")
            st.caption(
                "This text is used only for the one-shot LLM refine action. It is available for every field and is not saved unless you separately save the persistent hint below."
            )
            st.text_area(
                f"LLM refine instruction for {source}",
                key=f"llm_mapping_prompt_{source}",
                placeholder="Example: This field is a transaction or operation type. Prefer canonical/target fields that encode business event category, not a person or free-text label.",
            )
            st.caption(
                "Optional manual field context for this refine preview. These values can be used immediately for LLM refine even if you do not save them persistently."
            )
            st.text_area(
                f"Business meaning for {source}",
                key=f"field_hint_meaning_{source}",
                placeholder="Example: Operation type / transaction type.",
            )
            st.text_input(
                f"What this field is not for {source}",
                key=f"field_hint_negative_{source}",
                placeholder="Example: Not contact name or person name.",
            )
            st.text_input(
                f"Representative sample values for {source}",
                key=f"field_hint_samples_{source}",
                placeholder="Example: SALE, RETURN, STORNO",
            )
            if st.button(
                "Preview LLM refine",
                key=f"refine_mapping_{source}",
                width="stretch",
                disabled=(not llm_runtime_enabled()) or (not ranked_candidate_targets),
                help="Runs a closed-set LLM review for this field using the current typed refine instruction, manual hints, and candidate shortlist.",
            ):
                try:
                    composed_instruction = _compose_llm_mapping_refinement_instruction(
                        st.session_state.get("llm_mapping_batch_prompt", ""),
                        st.session_state.get(f"llm_mapping_prompt_{source}", ""),
                    )
                    refinement_response = request_llm_mapping_refinement(
                        source,
                        candidate_targets=ranked_candidate_targets,
                        meaning_hint=st.session_state.get(f"field_hint_meaning_{source}", ""),
                        negative_hint=st.session_state.get(f"field_hint_negative_{source}", ""),
                        sample_values=_parse_hint_sample_values(
                            st.session_state.get(f"field_hint_samples_{source}", "")
                        ),
                        refinement_instruction=composed_instruction,
                    )
                    _remember_llm_mapping_refinement(
                        entry,
                        refinement_response=refinement_response,
                        current_target=str(entry.get("target") or mapping.get("target") or ""),
                        current_status=str(entry.get("status") or "needs_review"),
                        instruction=composed_instruction,
                    )
                    selected_refinement = refinement_response.get("selected") or {}
                    if str(selected_refinement.get("target") or "").strip():
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": (
                                f"Prepared an LLM refine preview for {source} -> {selected_refinement.get('target')}. "
                                "Use Accept refined mapping below to apply it."
                            ),
                        }
                    else:
                        st.session_state["last_action"] = {
                            "level": "warning",
                            "message": (
                                f"LLM refinement for {source} returned no_match in the current candidate set."
                            ),
                        }
                    st.rerun()
                except ValueError as error:
                    st.session_state["last_action"] = {"level": "warning", "message": str(error)}
                    st.rerun()
                except httpx.HTTPError as error:
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"LLM mapping refinement failed: {error}",
                    }
                    st.rerun()

            if not llm_runtime_enabled():
                st.caption("LLM mapping refine is disabled. Enable a runtime provider in backend config to use it.")

            if not source_system:
                st.info("Set Source system in the workspace context before saving a persistent field hint.")
            else:
                st.caption(
                    "Save field-level business meaning once and Semantra will auto-inject it into future runs for the same scope."
                )
                if st.button("Save hint for future runs", key=f"save_field_hint_{source}", width="stretch"):
                    try:
                        saved_record = api_request(
                            "POST",
                            "/mapping/source-field-hints",
                            json={
                                "source_field": source,
                                "source_system": source_system,
                                "business_domain": business_domain,
                                "integration_name": integration_name,
                                "meaning_hint": st.session_state.get(f"field_hint_meaning_{source}", ""),
                                "negative_hint": st.session_state.get(f"field_hint_negative_{source}", ""),
                                "sample_values": _parse_hint_sample_values(
                                    st.session_state.get(f"field_hint_samples_{source}", "")
                                ),
                            },
                        )
                        _invalidate_source_field_hint_cache()
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": (
                                f"Saved a persistent hint for {source}. Re-run mapping to apply it automatically for "
                                f"{saved_record.get('source_system') or source_system}."
                            ),
                        }
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Saving source field hint failed: {error}",
                        }
                        st.rerun()

            if canonical_only:
                st.info(
                    "Canonical-only mode disables transformation authoring until a real target dataset exists in Standard mode."
                )
            else:
                transformation = suggested_code.strip()
                if transformation:
                    st.markdown("🛠️ **Transformation code (Pandas):**")
                    st.code(transformation, language="python")
                    entry["apply_transformation"] = st.checkbox(
                        "Apply this transformation to data",
                        key=f"transform_{source}",
                    )
                else:
                    st.write("✅ No transformation needed (direct mapping).")

                st.caption(
                    "Expected format: pandas-oriented Python using `df_source`, `df_target`, and `pd`. "
                    "You can enter either a full statement such as `df_target[\"target_col\"] = ...` "
                    "or only the right-hand expression; if you omit the assignment, Semantra wraps it "
                    f"as `df_target[\"{mapping.get('target') or 'target_col'}\"] = <your code>`."
                )
                llm_instruction = st.text_area(
                    f"Describe desired transformation for {source}",
                    key=f"llm_transform_prompt_{source}",
                    help="Describe the business intent in natural language and let the active LLM propose pandas code.",
                    placeholder="Example: Extract the person's full name from the email address and title-case it.",
                )
                entry["llm_transformation_instruction"] = llm_instruction
                if st.button(
                    "Generate with LLM",
                    key=f"generate_transform_{source}",
                    disabled=(not llm_runtime_enabled()) or (not mapping.get("target")),
                    help="Uses the active runtime LLM to propose pandas transformation code for the currently selected target.",
                ):
                    try:
                        generated = request_llm_transformation_suggestion(source, mapping.get("target") or "", llm_instruction)
                        entry["manual_transformation_code"] = generated["transformation_code"]
                        entry["generated_transformation_reasoning"] = generated.get("reasoning", [])
                        entry["generated_transformation_warnings"] = generated.get("warnings", [])
                        st.session_state[f"manual_transform_{source}"] = generated["transformation_code"]
                        st.session_state[f"manual_apply_{source}"] = False
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Generated an LLM transformation suggestion for {source} -> {mapping.get('target') or 'target'}.",
                        }
                        st.rerun()
                    except ValueError as error:
                        st.session_state["last_action"] = {"level": "warning", "message": str(error)}
                        st.rerun()
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"LLM transformation generation failed: {error}",
                        }
                        st.rerun()

                if not llm_runtime_enabled():
                    st.caption("LLM generation is disabled. Enable a runtime provider in backend config to use this helper.")
                template_options = [{"template_id": "", "name": "Select reusable template", "description": "", "code_template": ""}]
                try:
                    template_options.extend(request_transformation_templates())
                except httpx.HTTPError:
                    pass
                selected_template_name = st.selectbox(
                    f"Reusable template for {source}",
                    [item["name"] for item in template_options],
                    key=f"template_select_{source}",
                )
                selected_template = next(
                    (item for item in template_options if item["name"] == selected_template_name),
                    template_options[0],
                )
                if selected_template.get("template_id"):
                    st.caption(selected_template.get("description") or "")
                    if st.button("Apply template", key=f"apply_template_{source}", disabled=not mapping.get("target")):
                        template_code = materialize_transformation_template(selected_template, source, mapping.get("target") or "target_col")
                        entry["manual_transformation_code"] = template_code
                        st.session_state[f"manual_transform_{source}"] = template_code
                        st.session_state[f"manual_apply_{source}"] = False
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Applied reusable transformation template '{selected_template_name}' for {source}.",
                        }
                        st.rerun()
                manual_code = st.text_area(
                    f"Define pandas/Python transformation for {source} (optional)",
                    key=f"manual_transform_{source}",
                    help=(
                        "Use pandas-style Python over df_source/df_target. Example: "
                        "df_source[\"email\"].str.split(\"@\").str[0].str.title()"
                    ),
                    placeholder=(
                        "Example:\n"
                        f"df_source[\"{source}\"].astype(str).str.strip()"
                    ),
                )
                entry["manual_transformation_code"] = manual_code
                if manual_code.strip():
                    if entry.get("generated_transformation_reasoning") or entry.get("generated_transformation_warnings"):
                        st.info(
                            "LLM generated a transformation suggestion. Review it below, then check Apply generated/custom transformation to activate it."
                        )
                        reasoning = entry.get("generated_transformation_reasoning", [])
                        if reasoning:
                            st.caption("LLM reasoning: " + " | ".join(reasoning))
                        warnings = entry.get("generated_transformation_warnings", [])
                        if warnings:
                            st.caption("Warnings: " + " | ".join(warnings))
                    st.markdown("You entered a custom transformation:")
                    st.code(manual_code, language="python")
                    entry["manual_apply_transformation"] = st.checkbox(
                        "Apply generated/custom transformation",
                        key=f"manual_apply_{source}",
                    )
                else:
                    entry["manual_apply_transformation"] = False

            if score < 0.7:
                st.warning("⚠️ Low confidence. Please review this mapping manually.")
            else:
                st.write("✅ High confidence based on signals.")

    st.session_state["mapping_editor_state"] = editor_state


def render_canonical_gap_assistant(mapping_response: dict, *, api_request) -> None:
    candidates = st.session_state.get("canonical_gap_candidates") or []
    with st.expander(
        _section_label("Canonical Gap Suggestions", f"{len(candidates)} open" if candidates else None),
        expanded=bool(candidates),
    ):
        st.caption("Review high-confidence mappings that are missing a canonical path, then approve overlay-only glossary updates.")
        if st.button("Find canonical gaps", key="canonical_gap_find"):
            try:
                st.session_state["canonical_gap_candidates"] = api_request(
                    "POST",
                    "/knowledge/canonical-gaps/candidates",
                    json={"mapping_response": mapping_response},
                ).get("candidates", [])
                st.session_state.pop("canonical_gap_triage_summary", None)
                st.session_state.pop("canonical_gap_triage_error", None)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Loaded canonical gap candidates for review.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Canonical gap detection failed: {error}",
                }
            st.rerun()

        if not candidates:
            with st.expander("Gap Queue Summary", expanded=False):
                st.caption("Queue-level summary of repeated canonical-gap families once candidates are loaded.")
                st.info("Run 'Find canonical gaps' first to unlock the queue-level summary.")
            st.info("No canonical gap candidates loaded yet, or no high-confidence gaps were found.")
            return

        try:
            proposal_state_records = api_request("GET", "/knowledge/canonical-gaps/proposal-states")
        except httpx.HTTPError:
            proposal_state_records = []
        proposal_states = {
            str(record.get("candidate_key") or "").strip(): str(record.get("proposal_state") or "").strip()
            for record in proposal_state_records
            if str(record.get("candidate_key") or "").strip()
        }

        suggestions = st.session_state.setdefault("canonical_gap_suggestions", {})
        triage_summary = st.session_state.get("canonical_gap_triage_summary")
        triage_error = st.session_state.get("canonical_gap_triage_error")
        triage_label = _section_label(
            "Gap Queue Summary",
            "LLM summary" if (triage_summary or {}).get("generation_metadata", {}).get("used_llm") else (
                "Fallback summary" if triage_summary else None
            ),
        )
        with st.expander(triage_label, expanded=bool(triage_summary) or bool(triage_error)):
            st.caption("Summarize the current canonical-gap queue into repeated families before reviewing candidates one by one.")
            if st.button(
                "Refresh gap summary" if triage_summary else "Generate gap summary",
                key="canonical_gap_triage_summary",
                width="stretch",
            ):
                try:
                    st.session_state["canonical_gap_triage_summary"] = api_request(
                        "POST",
                        "/knowledge/canonical-gaps/triage-summary",
                        json=_canonical_gap_triage_payload(candidates, suggestions, proposal_states),
                        timeout=90.0,
                    )
                    st.session_state.pop("canonical_gap_triage_error", None)
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": "Generated a batch triage summary for the current canonical-gap queue.",
                    }
                except httpx.HTTPError as error:
                    st.session_state["canonical_gap_triage_error"] = str(error)
                    st.session_state["last_action"] = {
                        "level": "error",
                        "message": f"Canonical gap triage summary failed: {error}",
                    }
                st.rerun()

            if triage_error and not triage_summary:
                st.error(f"Canonical gap triage summary failed: {triage_error}")
            elif triage_summary:
                st.write(str(triage_summary.get("summary") or ""))
                triage_rows = _canonical_gap_triage_group_rows(triage_summary)
                if triage_rows:
                    st.dataframe(triage_rows, width="stretch", hide_index=True)
                columns = st.columns(2)
                with columns[0]:
                    st.caption("Risks")
                    for line in triage_summary.get("risks") or []:
                        st.write(f"- {line}")
                with columns[1]:
                    st.caption("Next actions")
                    for line in triage_summary.get("next_actions") or []:
                        st.write(f"- {line}")
            else:
                st.info("No queue-level canonical-gap triage summary has been generated yet.")

        for candidate in candidates:
            source = candidate.get("source", "")
            target = candidate.get("target", "")
            key = _canonical_gap_candidate_key(candidate)
            proposal_state = _canonical_gap_proposal_state(key, proposal_states)
            with st.container(border=True):
                columns = st.columns([3, 3, 2])
                columns[0].markdown(f"**Source:** {source}")
                columns[1].markdown(f"**Target:** {target}")
                columns[2].metric("Confidence", f"{int(float(candidate.get('confidence', 0.0) or 0.0) * 100)}%")
                st.caption(candidate.get("reason") or "Missing canonical path.")
                if candidate.get("explanation"):
                    st.caption("Signals: " + " | ".join(candidate.get("explanation") or []))

                action_columns = st.columns(2)
                if action_columns[0].button("Suggest with LLM", key=f"suggest_{key}"):
                    try:
                        suggestions[key] = api_request(
                            "POST",
                            "/knowledge/canonical-gaps/suggest",
                            json={"candidate": candidate},
                            timeout=90.0,
                        )
                        st.session_state.pop("canonical_gap_triage_summary", None)
                        st.session_state.pop("canonical_gap_triage_error", None)
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": f"Generated canonical gap suggestion for {source} -> {target}.",
                        }
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Canonical gap suggestion failed: {error}",
                        }
                    st.rerun()

                suggestion = suggestions.get(key)
                if not suggestion:
                    continue
                st.write(f"Action: **{suggestion.get('action', 'no_action')}**")
                st.write(f"Concept: **{suggestion.get('concept_id') or 'n/a'}** - {suggestion.get('display_name') or 'n/a'}")
                if suggestion.get("aliases"):
                    st.caption("Aliases: " + ", ".join(suggestion.get("aliases") or []))
                for line in suggestion.get("reasoning") or []:
                    st.caption(f"Reason: {line}")
                for line in suggestion.get("risk_notes") or []:
                    st.caption(f"Risk: {line}")

                block_reason = _canonical_gap_approval_block_reason(suggestion, proposal_state)
                disabled = bool(block_reason)
                if action_columns[1].button("Approve and persist", key=f"approve_{key}", disabled=disabled):
                    try:
                        response = api_request(
                            "POST",
                            "/knowledge/canonical-gaps/approve",
                            json={
                                "candidate": candidate,
                                "suggestion": suggestion,
                                "approved_by": st.session_state.get("admin_token", "") or "streamlit-review",
                            },
                        )
                        st.session_state["last_action"] = {
                            "level": "success",
                            "message": (
                                f"Approved canonical gap into overlay '{response.get('overlay_name')}'. "
                                "Regenerate mapping to see the canonical path filled."
                            ),
                        }
                        st.session_state.pop("canonical_gap_triage_summary", None)
                        st.session_state.pop("canonical_gap_triage_error", None)
                    except httpx.HTTPError as error:
                        st.session_state["last_action"] = {
                            "level": "error",
                            "message": f"Canonical gap approval failed: {error}",
                        }
                    st.rerun()
                if block_reason:
                    st.caption(block_reason)


def render_mapping_review(
    mapping_response: dict,
    *,
    current_mapping_rows,
    source_concept_rows,
    concept_target_rows,
    all_filter_option: str,
    validator_badge,
    canonical_path_label,
    request_review_plan_summary,
) -> None:
    selected_rows = current_mapping_rows(mapping_response)
    source_concept_view_rows = source_concept_rows(mapping_response)
    concept_target_view_rows = concept_target_rows(mapping_response)
    filter_columns = st.columns(3)
    status_options = [all_filter_option, "accepted", "needs_review", "rejected"]
    confidence_options = [all_filter_option, "high_confidence", "medium_confidence", "low_confidence"]
    source_options = [all_filter_option, *[row["source"] for row in selected_rows]]

    selected_status = filter_columns[0].selectbox("Filter by status", status_options, key="filter_status")
    selected_confidence = filter_columns[1].selectbox(
        "Filter by confidence label",
        confidence_options,
        key="filter_confidence",
    )
    selected_source = filter_columns[2].selectbox("Filter by source", source_options, key="filter_source")

    filtered_rows = [
        row
        for row in selected_rows
        if (selected_status == all_filter_option or row["status"] == selected_status)
        and (selected_confidence == all_filter_option or row["confidence_label"] == selected_confidence)
        and (selected_source == all_filter_option or row["source"] == selected_source)
    ]
    canonical_mismatch_rows = [
        row
        for row in filtered_rows
        if row.get("canonical_status") != "shared_match"
    ]
    selected_mapping_display_rows = [
        {
            **{key: value for key, value in row.items() if key != "canonical_status"},
            "canonical_status": row.get("canonical_status_label") or row.get("canonical_status") or "",
        }
        for row in filtered_rows
    ]
    canonical_mismatch_display_rows = [
        {
            **{key: value for key, value in row.items() if key != "canonical_status"},
            "canonical_status": row.get("canonical_status_label") or row.get("canonical_status") or "",
        }
        for row in canonical_mismatch_rows
    ]
    attention_summary_rows = _review_attention_summary_rows(filtered_rows)
    review_plan_summary = st.session_state.get("review_plan_summary")
    review_plan_error = st.session_state.get("review_plan_error")

    if attention_summary_rows:
        st.subheader("Repeated Review Attention")
        st.caption(
            "Groups unmatched and low-confidence patterns in the current review set so repeated glossary, knowledge, or ranking gaps are visible before row-by-row triage. "
            "This is deterministic attention surfacing, not a generated review plan."
        )
        st.dataframe(attention_summary_rows, width="stretch", hide_index=True)

    review_plan_label = _section_label(
        "Review Queue Plan",
        "LLM plan" if (review_plan_summary or {}).get("generation_metadata", {}).get("used_llm") else (
            "Fallback plan" if review_plan_summary else None
        ),
    )
    with st.expander(review_plan_label, expanded=bool(review_plan_summary) or bool(review_plan_error)):
        st.caption(
            "Generate one bounded queue plan for the currently filtered review set before changing row-level decisions. "
            "Unlike Mapping Analysis Overview, this is about review order and cluster-level follow-up. "
            "It does not change row-level targets or statuses."
        )
        action_label = "Refresh review plan" if review_plan_summary else "Generate review plan"
        if st.button(action_label, key="generate_review_plan", width="stretch"):
            try:
                payload = _review_plan_request_payload(
                    filtered_rows,
                    attention_summary_rows,
                    status_filter=selected_status,
                    confidence_filter=selected_confidence,
                    source_filter=selected_source,
                )
                st.session_state["review_plan_summary"] = request_review_plan_summary(
                    payload["filtered_rows"],
                    payload["attention_summary_rows"],
                    status_filter=payload["filters"]["status"],
                    confidence_filter=payload["filters"]["confidence_label"],
                    source_filter=payload["filters"]["source"],
                )
                st.session_state.pop("review_plan_error", None)
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": "Generated a bounded queue plan for the current review set.",
                }
                st.rerun()
            except (ValueError, httpx.HTTPError) as error:
                st.session_state["review_plan_error"] = str(error)
                st.session_state["last_action"] = {
                    "level": "error",
                    "message": f"Review queue plan generation failed: {error}",
                }
                st.rerun()

        if review_plan_error and not review_plan_summary:
            st.error(f"Review queue plan generation failed: {review_plan_error}")

        if review_plan_summary:
            st.write(str(review_plan_summary.get("queue_summary") or ""))
            cluster_rows = _review_plan_cluster_rows(review_plan_summary)
            if cluster_rows:
                st.dataframe(cluster_rows, width="stretch", hide_index=True)
            summary_columns = st.columns(2)
            with summary_columns[0]:
                st.caption("Risks")
                for line in review_plan_summary.get("risks") or []:
                    st.write(f"- {line}")
            with summary_columns[1]:
                st.caption("Next actions")
                for line in review_plan_summary.get("next_actions") or []:
                    st.write(f"- {line}")
        else:
            st.info("No review queue plan has been generated yet for the current filters.")

    st.subheader(_section_label("Selected Mapping", f"{len(selected_mapping_display_rows)} active" if selected_mapping_display_rows else None))
    st.caption(
        "Canonical status shows whether both sides share a business concept, only the source resolved, only the target resolved, source and target resolve to different concepts, or neither side resolved to a canonical concept."
    )
    st.dataframe(selected_mapping_display_rows, width="stretch", hide_index=True)

    if canonical_mismatch_rows or source_concept_view_rows or concept_target_view_rows:
        with st.expander("Selected Mapping Details"):
            if canonical_mismatch_rows:
                st.caption("These are the rows where the selected mapping does not have a shared canonical concept yet.")
                st.dataframe(canonical_mismatch_display_rows, width="stretch", hide_index=True)

            if source_concept_view_rows:
                st.caption("Shows only concepts resolved on the source side of the currently selected mapping.")
                st.dataframe(source_concept_view_rows, width="stretch", hide_index=True)

            if concept_target_view_rows:
                st.caption("Shows only concepts resolved on the target side of the currently selected mapping.")
                st.dataframe(concept_target_view_rows, width="stretch", hide_index=True)

    with st.expander("Ranked Candidates"):
        for ranked in mapping_response["ranked_mappings"]:
            if selected_source != all_filter_option and ranked["source"] != selected_source:
                continue
            with st.expander(f"{ranked['source']}"):
                st.dataframe(
                    [
                        {
                            "target": candidate["target"],
                            "confidence": candidate["confidence"],
                            "label": candidate["confidence_label"],
                            "validator": validator_badge(candidate["method"]),
                        }
                        for candidate in ranked["candidates"]
                        if selected_confidence == all_filter_option or candidate["confidence_label"] == selected_confidence
                    ],
                    width="stretch",
                    hide_index=True,
                )
                for candidate in ranked["candidates"]:
                    if selected_confidence != all_filter_option and candidate["confidence_label"] != selected_confidence:
                        continue
                    if candidate["explanation"]:
                        st.caption(f"{candidate['target']}: {' | '.join(candidate['explanation'])}")
                    canonical_path = canonical_path_label(
                        ranked["source"],
                        candidate.get("target"),
                        candidate.get("canonical_details"),
                    )
                    if canonical_path:
                        st.caption(f"Canonical path: {canonical_path}")


def render_canonical_concept_summary(
    mapping_response: dict,
    *,
    canonical_concept_groups,
) -> None:
    concept_rows = canonical_concept_groups(mapping_response)
    if not concept_rows:
        return

    canonical_mode = (st.session_state.get("upload_response") or {}).get("mapping_mode") == "canonical"
    with st.expander(
        _section_label("Canonical Concept Summary", f"{len(concept_rows)} shared concepts"),
        expanded=canonical_mode,
    ):
        st.caption("Summarizes only rows with a shared source-target canonical concept.")
        st.dataframe(concept_rows, width="stretch", hide_index=True)


def render_mapping_editor(mapping_response: dict, *, selected_target_options) -> None:
    editor_state = st.session_state.setdefault("mapping_editor_state", {})
    open_item_count = _manual_review_open_item_count(
        mapping_response,
        editor_state,
        selected_target_options=selected_target_options,
    )

    with st.expander(
        _section_label("Manual Review", f"{open_item_count} items" if open_item_count else None),
        expanded=open_item_count > 0,
    ):
        st.caption("Adjust the selected target and mark each mapping as accepted, needs review, or rejected.")

        for ranked in mapping_response["ranked_mappings"]:
            source = ranked["source"]
            options = selected_target_options(ranked)
            current = editor_state.get(source, {"target": options[0] if options else "", "status": "needs_review"})
            editor_state[source] = current

            with st.container(border=True):
                st.markdown(f"**{source}**")
                columns = st.columns([2, 1, 2])
                with columns[0]:
                    if options:
                        selected_index = options.index(current["target"]) if current["target"] in options else 0
                        editor_state[source]["target"] = st.selectbox(
                            f"Target for {source}",
                            options,
                            index=selected_index,
                            key=f"target_choice_{source}",
                            format_func=lambda option: option or "unmapped",
                            label_visibility="collapsed",
                        )
                    else:
                        st.warning("No target candidates returned.")
                        editor_state[source]["target"] = ""
                with columns[1]:
                    editor_state[source]["status"] = st.selectbox(
                        f"Status for {source}",
                        ["accepted", "needs_review", "rejected"],
                        index=["accepted", "needs_review", "rejected"].index(current["status"]),
                        key=f"status_choice_{source}",
                        label_visibility="collapsed",
                    )
                with columns[2]:
                    selected_candidate = next(
                        (candidate for candidate in ranked["candidates"] if candidate["target"] == editor_state[source]["target"]),
                        None,
                    )
                    if selected_candidate and selected_candidate["explanation"]:
                        st.caption(" | ".join(selected_candidate["explanation"]))
                    elif ranked["candidates"]:
                        st.caption("No explanation available for the selected candidate.")