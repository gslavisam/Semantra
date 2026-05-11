from __future__ import annotations

import httpx
import streamlit as st


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


def display_trust_layer(
    mapping_response: dict,
    *,
    trust_layer_rows,
    has_knowledge_match,
    has_canonical_match,
    canonical_concept_labels,
    transformation_mode_label,
    llm_runtime_enabled,
    request_llm_transformation_suggestion,
    request_transformation_templates,
    materialize_transformation_template,
    api_request=None,
) -> None:
    st.subheader("🎯 Mapping Trust Layer")
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
    editor_state = st.session_state.setdefault("mapping_editor_state", {})
    for mapping in trust_layer_rows(mapping_response):
        source = mapping["source"]
        entry = editor_state.setdefault(source, {})
        suggested_code = mapping.get("suggested_transformation_code") or ""
        if suggested_code and f"transform_{source}" not in st.session_state:
            st.session_state[f"transform_{source}"] = bool(entry.get("apply_transformation", False))
        if f"llm_transform_prompt_{source}" not in st.session_state:
            st.session_state[f"llm_transform_prompt_{source}"] = entry.get("llm_transformation_instruction", "")
        if f"manual_transform_{source}" not in st.session_state:
            st.session_state[f"manual_transform_{source}"] = entry.get("manual_transformation_code", "")
        if f"manual_apply_{source}" not in st.session_state:
            st.session_state[f"manual_apply_{source}"] = bool(entry.get("manual_apply_transformation", False))

        col1, col2, col3 = st.columns([3, 3, 2])
        with col1:
            st.info(f"Source: **{source}**")
        with col2:
            st.success(f"Target: **{mapping.get('target') or '—'}**")
            llm_recommendation = mapping.get("llm_recommendation") or {}
            if mapping.get("llm_consulted") and llm_recommendation:
                llm_target = llm_recommendation.get("selected_target") or "unmapped"
                llm_confidence = int(float(llm_recommendation.get("confidence", 0.0) or 0.0) * 100)
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
            st.caption(transformation_mode_label(mapping["transformation_mode"]))
        with col3:
            score = mapping.get("confidence", 0.0)
            st.metric("Confidence", f"{int(score * 100)}%")
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

            if mapping.get("llm_consulted") and llm_recommendation:
                st.write("**LLM review:**")
                st.write(
                    f"- Recommended target: {llm_recommendation.get('selected_target') or 'unmapped'} "
                    f"({int(float(llm_recommendation.get('confidence', 0.0) or 0.0) * 100)}%)"
                )
                for reason_line in llm_recommendation.get("reasoning", []) or []:
                    st.write(f"- LLM: {reason_line}")

            canonical_labels = canonical_concept_labels(mapping.get("canonical_details"))
            if canonical_labels:
                st.write("**Canonical path:**")
                st.write(f"- {source} -> {', '.join(canonical_labels)} -> {mapping.get('target') or 'unmapped'}")

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
    if api_request is not None:
        render_canonical_gap_assistant(mapping_response, api_request=api_request)


def render_canonical_gap_assistant(mapping_response: dict, *, api_request) -> None:
    st.subheader("Canonical Gap Suggestions")
    st.caption("Review high-confidence mappings that are missing a canonical path, then approve overlay-only glossary updates.")
    if st.button("Find canonical gaps", key="canonical_gap_find"):
        try:
            st.session_state["canonical_gap_candidates"] = api_request(
                "POST",
                "/knowledge/canonical-gaps/candidates",
                json={"mapping_response": mapping_response},
            ).get("candidates", [])
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

    candidates = st.session_state.get("canonical_gap_candidates") or []
    if not candidates:
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
    for index, candidate in enumerate(candidates):
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
    canonical_concept_groups,
    source_concept_rows,
    concept_target_rows,
    all_filter_option: str,
    validator_badge,
    canonical_path_label,
) -> None:
    selected_rows = current_mapping_rows(mapping_response)
    concept_rows = canonical_concept_groups(mapping_response)
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

    if attention_summary_rows:
        st.subheader("Repeated Review Attention")
        st.caption(
            "Groups unmatched and low-confidence patterns in the current review set so repeated glossary, knowledge, or ranking gaps are visible before row-by-row triage."
        )
        st.dataframe(attention_summary_rows, width="stretch", hide_index=True)

    st.subheader("Selected Mapping")
    st.caption(
        "Canonical status shows whether both sides share a business concept, only the source resolved, only the target resolved, source and target resolve to different concepts, or neither side resolved to a canonical concept."
    )
    st.dataframe(selected_mapping_display_rows, width="stretch", hide_index=True)

    if canonical_mismatch_rows:
        st.subheader("Canonical Mismatch Review")
        st.caption("These are the rows where the selected mapping does not have a shared canonical concept yet.")
        st.dataframe(canonical_mismatch_display_rows, width="stretch", hide_index=True)

    if source_concept_view_rows:
        st.subheader("Source -> Concept View")
        st.caption("Shows only concepts resolved on the source side of the currently selected mapping.")
        st.dataframe(source_concept_view_rows, width="stretch", hide_index=True)

    if concept_target_view_rows:
        st.subheader("Concept -> Target View")
        st.caption("Shows only concepts resolved on the target side of the currently selected mapping.")
        st.dataframe(concept_target_view_rows, width="stretch", hide_index=True)

    if concept_rows:
        st.subheader("Canonical Concept Summary")
        st.caption("Summarizes only rows with a shared source-target canonical concept.")
        st.dataframe(concept_rows, width="stretch", hide_index=True)

    st.subheader("Ranked Candidates")
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


def render_mapping_editor(mapping_response: dict, *, selected_target_options) -> None:
    st.subheader("Manual Review")
    st.caption("Adjust the selected target and mark each mapping as accepted, needs review, or rejected.")
    editor_state = st.session_state.setdefault("mapping_editor_state", {})

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