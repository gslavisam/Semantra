from __future__ import annotations

import httpx
import streamlit as st


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
) -> None:
    st.subheader("🎯 Mapping Trust Layer")
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

            canonical_labels = canonical_concept_labels(mapping.get("canonical_details"))
            if canonical_labels:
                st.write("**Canonical path:**")
                st.write(f"- {source} -> {', '.join(canonical_labels)} -> {mapping.get('target') or 'unmapped'}")

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

    st.subheader("Selected Mapping")
    st.dataframe(filtered_rows, width="stretch", hide_index=True)

    if source_concept_view_rows:
        st.subheader("Source -> Concept View")
        st.dataframe(source_concept_view_rows, width="stretch", hide_index=True)

    if concept_target_view_rows:
        st.subheader("Concept -> Target View")
        st.dataframe(concept_target_view_rows, width="stretch", hide_index=True)

    if concept_rows:
        st.subheader("Canonical Concept Summary")
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