from __future__ import annotations

import json

import httpx
import streamlit as st


st.set_page_config(page_title="Semantra - Data Integration", page_icon="ST", layout="wide")


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000"
ROW_DATA_UPLOAD_TYPES = ["csv", "json", "xml", "xlsx"]
ALL_UPLOAD_TYPES = [*ROW_DATA_UPLOAD_TYPES, "sql"]


STATUS_STYLES = {
    "done": ("Done", "#0f766e", "#ccfbf1"),
    "active": ("Active", "#9a3412", "#ffedd5"),
    "pending": ("Pending", "#475569", "#e2e8f0"),
}

ALL_FILTER_OPTION = "All"

def suggested_mapping_by_source(mapping_response: dict) -> dict[str, dict]:
    return {item["source"]: item for item in mapping_response.get("mappings", [])}


def resolve_suggested_transformation_code(entry: dict | None, fallback_code: str | None = None) -> str:
    current_entry = entry or {}
    current_target = str(current_entry.get("target") or "").strip()
    suggested_target = str(current_entry.get("suggested_target") or "").strip()
    if suggested_target and current_target and suggested_target != current_target:
        return ""
    return str(current_entry.get("suggested_transformation_code") or fallback_code or "").strip()


def effective_transformation_code(source: str, fallback_code: str | None = None) -> str | None:
    manual_code = st.session_state.get(f"manual_transform_{source}", "").strip()
    if manual_code and st.session_state.get(f"manual_apply_{source}", False):
        return manual_code

    suggested_code = (fallback_code or "").strip()
    if suggested_code and st.session_state.get(f"transform_{source}", False):
        return suggested_code
    return None


def transformation_mode(source: str, fallback_code: str | None = None) -> str:
    manual_code = st.session_state.get(f"manual_transform_{source}", "").strip()
    if manual_code and st.session_state.get(f"manual_apply_{source}", False):
        return "custom"

    suggested_code = (fallback_code or "").strip()
    if suggested_code and st.session_state.get(f"transform_{source}", False):
        return "suggested"
    return "direct"


def transformation_mode_label(mode: str) -> str:
    labels = {
        "custom": "Transformation: custom",
        "suggested": "Transformation: suggested",
        "direct": "Transformation: direct",
    }
    return labels.get(mode, "Transformation: direct")


def knowledge_explanation_lines(explanation: list[str] | None) -> list[str]:
    lines = explanation or []
    return [
        line for line in lines
        if line.startswith("Internal metadata dictionary") or line.startswith("Context prior:")
    ]


def knowledge_debug_rows(mapping_response: dict) -> list[dict]:
    rows: list[dict] = []
    selected_by_source = suggested_mapping_by_source(mapping_response)
    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        target = selected_row.get("target")
        if not target:
            continue
        selected_candidate = next((candidate for candidate in ranked.get("candidates", []) if candidate.get("target") == target), None)
        selected_payload = selected_candidate or ranked.get("selected") or selected_row
        signals = selected_payload.get("signals", {}) if isinstance(selected_payload, dict) else {}
        knowledge_lines = knowledge_explanation_lines(selected_payload.get("explanation", []) if isinstance(selected_payload, dict) else [])
        if not knowledge_lines and float(signals.get("knowledge", 0.0) or 0.0) <= 0:
            continue
        rows.append(
            {
                "source": source,
                "target": target,
                "knowledge_signal": float(signals.get("knowledge", 0.0) or 0.0),
                "confidence": float(selected_payload.get("confidence", 0.0) or 0.0) if isinstance(selected_payload, dict) else 0.0,
                "validator": validator_badge(selected_payload.get("method", "manual_review")) if isinstance(selected_payload, dict) else "Manual",
                "knowledge_explanations": knowledge_lines,
            }
        )
    return rows


def trust_layer_rows(mapping_response: dict) -> list[dict]:
    selected_by_source = suggested_mapping_by_source(mapping_response)
    rows: list[dict] = []
    for ranked in mapping_response.get("ranked_mappings", []):
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        current_state = st.session_state.get("mapping_editor_state", {}).get(source, {})
        current_target = current_state.get("target", selected_row.get("target"))
        selected_candidate = next(
            (candidate for candidate in ranked["candidates"] if candidate["target"] == current_target),
            None,
        )
        fallback_code = resolve_suggested_transformation_code(current_state, selected_row.get("transformation_code"))
        rows.append(
            {
                "source": source,
                "target": current_target,
                "confidence": selected_candidate["confidence"] if selected_candidate else selected_row.get("confidence", 0.0),
                "explanation": selected_candidate["explanation"] if selected_candidate else selected_row.get("explanation", []),
                "signals": selected_candidate["signals"] if selected_candidate else selected_row.get("signals", {}),
                "suggested_transformation_code": fallback_code,
                "active_transformation_code": effective_transformation_code(source, fallback_code),
                "transformation_mode": transformation_mode(source, fallback_code),
            }
        )
    return rows


def display_trust_layer(mapping_response: dict) -> None:
    st.subheader("\U0001F3AF Mapping Trust Layer")
    editor_state = st.session_state.setdefault("mapping_editor_state", {})
    for m in trust_layer_rows(mapping_response):
        source = m["source"]
        entry = editor_state.setdefault(source, {})
        suggested_code = m.get("suggested_transformation_code") or ""
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
            st.success(f"Target: **{m.get('target') or '—'}**")
            if has_knowledge_match(m.get("signals"), m.get("explanation")):
                st.caption("Knowledge-backed match")
            st.caption(transformation_mode_label(m["transformation_mode"]))
        with col3:
            score = m.get('confidence', 0.0)
            st.metric("Confidence", f"{int(score * 100)}%")
            st.progress(score)
        with st.expander(f"⚙️ Details and Transformation for {source}"):
            st.caption(transformation_mode_label(m["transformation_mode"]))
            reason = m.get('explanation', []) or m.get('reason', [])
            if isinstance(reason, str):
                st.write(f"**Reasoning:** {reason}")
            elif reason:
                st.write("**Reasoning:**")
                for r in reason:
                    st.write(f"- {r}")
            else:
                st.write("No explanation provided.")

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
                f"as `df_target[\"{m.get('target') or 'target_col'}\"] = <your code>`."
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
                disabled=(not llm_runtime_enabled()) or (not m.get("target")),
                help="Uses the active runtime LLM to propose pandas transformation code for the currently selected target.",
            ):
                try:
                    generated = request_llm_transformation_suggestion(source, m.get("target") or "", llm_instruction)
                    entry["manual_transformation_code"] = generated["transformation_code"]
                    entry["generated_transformation_reasoning"] = generated.get("reasoning", [])
                    entry["generated_transformation_warnings"] = generated.get("warnings", [])
                    st.session_state[f"manual_transform_{source}"] = generated["transformation_code"]
                    st.session_state[f"manual_apply_{source}"] = False
                    st.session_state["last_action"] = {
                        "level": "success",
                        "message": f"Generated an LLM transformation suggestion for {source} -> {m.get('target') or 'target'}.",
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


def has_knowledge_match(signals: dict | None, explanation: list[str] | str | None = None) -> bool:
    if isinstance(signals, dict):
        try:
            if float(signals.get("knowledge", 0.0) or 0.0) > 0.0:
                return True
        except (TypeError, ValueError):
            pass

    if isinstance(explanation, str):
        explanation_text = explanation.lower()
        return (
            "knowledge" in explanation_text
            or "metadata" in explanation_text
            or "context prior" in explanation_text
        )

    if isinstance(explanation, list):
        for item in explanation:
            if not isinstance(item, str):
                continue
            item_text = item.lower()
            if "knowledge" in item_text or "metadata" in item_text or "context prior" in item_text:
                return True

    return False

def reset_flow_state() -> None:
    for key in (
        "upload_response",
        "mapping_response",
        "preview_response",
        "codegen_response",
        "saved_corrections",
        "mapping_editor_state",
        "source_signature",
        "source_tables",
        "target_signature",
        "target_tables",
        "source_table",
        "target_table",
    ):
        st.session_state.pop(key, None)


def current_step() -> int:
    if st.session_state.get("mapping_response"):
        return 3
    if st.session_state.get("upload_response"):
        return 2
    return 1


def render_step_status() -> None:
    step = current_step()
    steps = [
        (1, "Upload", "Provide source and target CSV, JSON, XML, XLSX, or SQL files."),
        (2, "Profile", "Confirm schema summary and SQL table selection."),
        (3, "Review", "Edit mapping decisions, preview output, and save corrections."),
    ]
    columns = st.columns(len(steps))
    for column, (index, title, detail) in zip(columns, steps, strict=False):
        if step > index:
            status_key = "done"
        elif step == index:
            status_key = "active"
        else:
            status_key = "pending"
        badge, text_color, background = STATUS_STYLES[status_key]
        with column:
            st.markdown(
                f"""
                <div style="border:1px solid {background}; border-radius:14px; padding:14px; background:{background}; min-height:112px;">
                    <div style="font-size:12px; font-weight:700; color:{text_color}; text-transform:uppercase; letter-spacing:0.04em;">{badge}</div>
                    <div style="font-size:22px; font-weight:700; margin-top:6px; color:#111827;">{index}. {title}</div>
                    <div style="font-size:13px; margin-top:8px; color:#334155;">{detail}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def api_request(
    method: str,
    path: str,
    *,
    files: dict | None = None,
    data: dict | None = None,
    json: dict | None = None,
) -> dict:
    headers = {"Accept": "application/json"}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token

    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    with httpx.Client(timeout=60.0) as client:
        response = client.request(
            method,
            f"{base_url}{path}",
            headers=headers,
            files=files,
            data=data,
            json=json,
        )
    response.raise_for_status()
    return response.json()


def refresh_admin_requirement() -> None:
    headers = {"Accept": "application/json"}
    admin_token = st.session_state.get("admin_token", "").strip()
    if admin_token:
        headers["X-Admin-Token"] = admin_token
    base_url = st.session_state.get("api_base_url", DEFAULT_API_BASE_URL).rstrip("/")
    try:
        with httpx.Client(timeout=20.0) as client:
            response = client.get(f"{base_url}/observability/config", headers=headers)
        if response.status_code == 403:
            st.session_state["admin_requirement"] = {"requires_token": True, "reachable": True}
            st.session_state.pop("runtime_config_snapshot", None)
            return
        response.raise_for_status()
        payload = response.json()
        st.session_state["runtime_config_snapshot"] = payload
        st.session_state["admin_requirement"] = {
            "requires_token": bool(payload.get("admin_api_token_configured", False)),
            "reachable": True,
        }
    except httpx.HTTPError:
        st.session_state["admin_requirement"] = {"requires_token": True, "reachable": False}
        st.session_state.pop("runtime_config_snapshot", None)


def admin_token_required() -> bool:
    current_signature = (
        st.session_state.get("api_base_url", DEFAULT_API_BASE_URL),
        st.session_state.get("admin_token", ""),
    )
    cached_signature = st.session_state.get("admin_requirement_signature")
    if cached_signature != current_signature:
        refresh_admin_requirement()
        st.session_state["admin_requirement_signature"] = current_signature
    requirement = st.session_state.get("admin_requirement", {"requires_token": True, "reachable": False})
    return bool(requirement.get("requires_token", True))


def backend_is_reachable() -> bool:
    admin_token_required()
    requirement = st.session_state.get("admin_requirement", {"reachable": False})
    return bool(requirement.get("reachable", False))


def render_llm_runtime_status() -> None:
    admin_token_required()
    config = st.session_state.get("runtime_config_snapshot")
    requirement = st.session_state.get("admin_requirement", {"reachable": False, "requires_token": True})

    st.subheader("Runtime")
    if not requirement.get("reachable", False):
        st.warning("LLM status unavailable because the backend is not reachable.")
        return

    if config is None:
        if requirement.get("requires_token", True):
            st.info("LLM status is hidden until a valid admin token is provided.")
        else:
            st.info("LLM status is not available yet.")
        return

    llm_provider = str(config.get("llm_provider", "none")).strip() or "none"
    llm_model = str(config.get("llm_model", "")).strip() or "n/a"
    gate_min = config.get("llm_gate_min_score", "?")
    gate_max = config.get("llm_gate_max_score", "?")

    if llm_provider.lower() == "none":
        st.warning("LLM is currently disabled.")
    else:
        st.success(f"LLM active: {llm_provider} / {llm_model}")
    st.caption(f"Ambiguity gate: {gate_min} - {gate_max}")


def llm_runtime_enabled() -> bool:
    config = st.session_state.get("runtime_config_snapshot")
    if not config:
        return False
    return str(config.get("llm_provider", "none")).strip().lower() != "none"


def request_llm_transformation_suggestion(source: str, target: str, instruction: str) -> dict:
    upload_response = st.session_state.get("upload_response")
    if not upload_response:
        raise ValueError("Upload source and target datasets before generating a transformation.")
    if not target:
        raise ValueError("Select a target column before generating a transformation.")
    if not instruction.strip():
        raise ValueError("Describe the desired transformation before generating code.")

    return api_request(
        "POST",
        "/mapping/transformation/generate",
        json={
            "source_dataset_id": upload_response["source"]["dataset_id"],
            "target_dataset_id": upload_response["target"]["dataset_id"],
            "source_column": source,
            "target_column": target,
            "instruction": instruction.strip(),
        },
    )


def status_banner(level: str, message: str) -> None:
    renderers = {
        "success": st.success,
        "error": st.error,
        "warning": st.warning,
        "info": st.info,
    }
    renderers.get(level, st.info)(message)


def uploaded_file_bytes(uploaded_file) -> bytes:
    return uploaded_file.getvalue() if uploaded_file is not None else b""


def sql_tables_for_upload(uploaded_file, cache_key: str) -> list[str]:
    if uploaded_file is None or not uploaded_file.name.lower().endswith(".sql"):
        return []

    file_bytes = uploaded_file_bytes(uploaded_file)
    signature = (uploaded_file.name, len(file_bytes))
    cached_signature = st.session_state.get(f"{cache_key}_signature")
    if cached_signature == signature:
        return st.session_state.get(f"{cache_key}_tables", [])

    payload = api_request(
        "POST",
        "/upload/sql/tables",
        files={"file": (uploaded_file.name, file_bytes, uploaded_file.type or "application/sql")},
    )
    st.session_state[f"{cache_key}_signature"] = signature
    st.session_state[f"{cache_key}_tables"] = payload["tables"]
    return payload["tables"]


def render_dataset_summary(label: str, handle: dict) -> None:
    schema = handle["schema_profile"]
    st.markdown(f"### {label}")
    st.write(f"Dataset: {handle['dataset_name']}")
    st.write(f"Columns: {len(schema['columns'])} | Rows: {schema['row_count']}")
    st.dataframe(
        [
            {
                "name": column["name"],
                "dtype": column["dtype"],
                "patterns": ", ".join(column["detected_patterns"]),
            }
            for column in schema["columns"]
        ],
        width='stretch',
        hide_index=True,
    )


def schema_columns_for_case(handle: dict) -> list[dict]:
    return [
        {
            "name": column["name"],
            "normalized_name": column["normalized_name"],
            "dtype": column["dtype"],
            "null_ratio": column["null_ratio"],
            "unique_ratio": column["unique_ratio"],
            "avg_length": column["avg_length"],
            "non_null_count": column["non_null_count"],
            "sample_values": column["sample_values"],
            "distinct_sample_values": column["distinct_sample_values"],
            "detected_patterns": column["detected_patterns"],
            "tokenized_name": column["tokenized_name"],
        }
        for column in handle["schema_profile"]["columns"]
    ]


def render_last_action_status() -> None:
    last_action = st.session_state.get("last_action")
    if last_action:
        status_banner(last_action.get("level", "info"), last_action.get("message", ""))
    if not backend_is_reachable():
        status_banner("warning", "Backend observability check failed. Verify API Base URL or backend availability.")


def validator_badge(method: str) -> str:
    labels = {
        "llm_validated": "LLM validator",
        "multi_signal_heuristic": "Heuristic",
        "manual_review": "Manual",
    }
    return labels.get(method, method.replace("_", " ").title())


def render_mapping_review(mapping_response: dict) -> None:
    selected_rows = current_mapping_rows(mapping_response)
    filter_columns = st.columns(3)
    status_options = [ALL_FILTER_OPTION, "accepted", "needs_review", "rejected"]
    confidence_options = [ALL_FILTER_OPTION, "high_confidence", "medium_confidence", "low_confidence"]
    source_options = [ALL_FILTER_OPTION, *[row["source"] for row in selected_rows]]

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
        if (selected_status == ALL_FILTER_OPTION or row["status"] == selected_status)
        and (selected_confidence == ALL_FILTER_OPTION or row["confidence_label"] == selected_confidence)
        and (selected_source == ALL_FILTER_OPTION or row["source"] == selected_source)
    ]

    st.subheader("Selected Mapping")
    st.dataframe(filtered_rows, width='stretch', hide_index=True)

    st.subheader("Ranked Candidates")
    for ranked in mapping_response["ranked_mappings"]:
        if selected_source != ALL_FILTER_OPTION and ranked["source"] != selected_source:
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
                    if selected_confidence == ALL_FILTER_OPTION or candidate["confidence_label"] == selected_confidence
                ],
                width='stretch',
                hide_index=True,
            )
            for candidate in ranked["candidates"]:
                if selected_confidence != ALL_FILTER_OPTION and candidate["confidence_label"] != selected_confidence:
                    continue
                if candidate["explanation"]:
                    st.caption(f"{candidate['target']}: {' | '.join(candidate['explanation'])}")


def current_mapping_rows(mapping_response: dict) -> list[dict]:
    selected_by_source = suggested_mapping_by_source(mapping_response)
    rows: list[dict] = []
    for ranked in mapping_response["ranked_mappings"]:
        source = ranked["source"]
        selected_row = selected_by_source.get(source, {})
        current_state = st.session_state.get("mapping_editor_state", {}).get(source, {})
        current_target = current_state.get("target", selected_row.get("target"))
        selected_candidate = next(
            (candidate for candidate in ranked["candidates"] if candidate["target"] == current_target),
            None,
        )
        rows.append(
            {
                "source": source,
                "target": current_target,
                "confidence": selected_candidate["confidence"] if selected_candidate else selected_row.get("confidence", 0.0),
                "confidence_label": (
                    selected_candidate["confidence_label"] if selected_candidate else selected_row.get("confidence_label", "low_confidence")
                ),
                "status": current_state.get("status", selected_row.get("status", "needs_review")),
                "validator": validator_badge(
                    selected_candidate["method"] if selected_candidate else selected_row.get("method", "manual_review")
                ),
            }
        )
    return rows


def initialize_mapping_editor_state(mapping_response: dict) -> None:
    editor_state: dict[str, dict[str, str]] = {}
    for ranked in mapping_response["ranked_mappings"]:
        selected_mapping = suggested_mapping_by_source(mapping_response).get(ranked["source"], {})
        editor_state[ranked["source"]] = default_editor_entry(ranked, selected_mapping)
    st.session_state["mapping_editor_state"] = editor_state


def selected_target_options(ranked: dict) -> list[str]:
    options = [candidate["target"] for candidate in ranked["candidates"]]
    selected = ranked["selected"]["target"] if ranked["selected"] and ranked["selected"].get("target") else None
    if selected and selected not in options:
        options.insert(0, selected)
    return options


def schema_column_names(handle: dict) -> list[str]:
    return [column["name"] for column in handle["schema_profile"]["columns"]]


def ranked_sources(mapping_response: dict) -> set[str]:
    return {ranked["source"] for ranked in mapping_response["ranked_mappings"]}


def render_mapping_editor(mapping_response: dict) -> None:
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


def upsert_manual_mapping(source: str, target: str, status: str) -> None:
    editor_state = st.session_state.setdefault("mapping_editor_state", {})
    current_entry = editor_state.get(source, {})
    editor_state[source] = {
        "target": target,
        "status": status,
        "suggested_target": current_entry.get("suggested_target", ""),
        "manual": True,
    }
    st.session_state["mapping_editor_state"] = editor_state


def default_editor_entry(ranked: dict, selected_mapping: dict | None = None) -> dict[str, str | bool]:
    selected_mapping = selected_mapping or {}
    selected_target = None
    selected_status = "rejected"
    if ranked["selected"] and ranked["selected"].get("target"):
        selected_target = ranked["selected"]["target"]
        selected_status = ranked["selected"]["status"]
    elif ranked["candidates"]:
        selected_target = ranked["candidates"][0]["target"]
        selected_status = "needs_review"
    return {
        "target": selected_target or "",
        "status": selected_status,
        "suggested_target": selected_target or "",
        "suggested_transformation_code": selected_mapping.get("transformation_code") or "",
        "manual_transformation_code": "",
        "llm_transformation_instruction": "",
        "generated_transformation_reasoning": [],
        "generated_transformation_warnings": [],
        "apply_transformation": False,
        "manual_apply_transformation": False,
        "manual": False,
    }


def remove_manual_mapping(source: str, mapping_response: dict) -> None:
    editor_state = st.session_state.setdefault("mapping_editor_state", {})
    ranked_by_source = {ranked["source"]: ranked for ranked in mapping_response["ranked_mappings"]}
    if source in ranked_by_source:
        selected_mapping = suggested_mapping_by_source(mapping_response).get(source, {})
        editor_state[source] = default_editor_entry(ranked_by_source[source], selected_mapping)
    else:
        editor_state.pop(source, None)
    st.session_state["mapping_editor_state"] = editor_state


def manual_mapping_rows(mapping_response: dict) -> list[dict]:
    editor_state = st.session_state.get("mapping_editor_state", {})
    auto_sources = ranked_sources(mapping_response)
    rows: list[dict] = []
    for source, entry in editor_state.items():
        if source in auto_sources and not entry.get("manual"):
            continue
        target = entry.get("target", "")
        status = entry.get("status", "needs_review")
        if not target or status == "rejected":
            continue
        rows.append(
            {
                "source": source,
                "target": target,
                "status": status,
                "suggested_target": entry.get("suggested_target") or None,
                "mode": "manual_override" if source in auto_sources else "manual_addition",
            }
        )
    return rows


def render_manual_mapping_panel(mapping_response: dict) -> None:
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
    if form_columns[3].button("Add mapping", width='stretch', key="manual_mapping_add"):
        upsert_manual_mapping(selected_source, selected_target, selected_status)
        st.session_state["last_action"] = {
            "level": "success",
            "message": f"Added manual mapping {selected_source} -> {selected_target}.",
        }
        st.rerun()

    manual_rows = manual_mapping_rows(mapping_response)
    if manual_rows:
        st.caption("Manual additions and overrides")
        st.dataframe(manual_rows, width='stretch', hide_index=True)
        removable_sources = [row["source"] for row in manual_rows]
        remove_columns = st.columns([3, 1])
        source_to_remove = remove_columns[0].selectbox(
            "Remove manual mapping",
            removable_sources,
            key="manual_mapping_remove_source",
        )
        if remove_columns[1].button("Remove", width='stretch', key="manual_mapping_remove"):
            remove_manual_mapping(source_to_remove, mapping_response)
            st.session_state["last_action"] = {
                "level": "info",
                "message": f"Removed manual mapping for {source_to_remove}.",
            }
            st.rerun()
    else:
        st.info("No manual additions yet. Use this section when you already know a source-to-target pair that should exist.")


def build_mapping_decisions() -> list[dict]:
    decisions: list[dict] = []
    for source, entry in st.session_state.get("mapping_editor_state", {}).items():
        target = entry.get("target", "")
        status = entry.get("status", "needs_review")
        if not target or status == "rejected":
            continue
        transformation_code = effective_transformation_code(source, resolve_suggested_transformation_code(entry))
        decision = {"source": source, "target": target, "status": status}
        if transformation_code:
            decision["transformation_code"] = transformation_code
        decisions.append(decision)
    return decisions


def export_mapping_payload() -> str:
    payload = {
        "source_dataset_id": st.session_state.get("upload_response", {}).get("source", {}).get("dataset_id"),
        "target_dataset_id": st.session_state.get("upload_response", {}).get("target", {}).get("dataset_id"),
        "mapping_decisions": build_mapping_decisions(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=True)


def build_current_benchmark_case() -> dict | None:
    upload_response = st.session_state.get("upload_response")
    mapping_decisions = build_mapping_decisions()
    if not upload_response or not mapping_decisions:
        return None
    return {
        "source_columns": schema_columns_for_case(upload_response["source"]),
        "target_columns": schema_columns_for_case(upload_response["target"]),
        "ground_truth": {decision["source"]: decision["target"] for decision in mapping_decisions},
        "row_count": upload_response["source"]["schema_profile"]["row_count"],
    }


def apply_imported_mapping_payload(raw_payload: bytes) -> None:
    payload = json.loads(raw_payload.decode("utf-8"))
    imported_decisions = payload.get("mapping_decisions", [])
    editor_state = st.session_state.get("mapping_editor_state", {})
    upload_response = st.session_state.get("upload_response")
    valid_sources = set(schema_column_names(upload_response["source"])) if upload_response else set()
    for decision in imported_decisions:
        source = decision["source"]
        if valid_sources and source not in valid_sources:
            continue
        current_entry = editor_state.get(source, {})
        editor_state[source] = {
            "target": decision["target"],
            "status": decision.get("status", "accepted"),
            "suggested_target": current_entry.get("suggested_target", ""),
            "suggested_transformation_code": current_entry.get("suggested_transformation_code", ""),
            "manual_transformation_code": decision.get("transformation_code", ""),
            "llm_transformation_instruction": current_entry.get("llm_transformation_instruction", ""),
            "generated_transformation_reasoning": current_entry.get("generated_transformation_reasoning", []),
            "generated_transformation_warnings": current_entry.get("generated_transformation_warnings", []),
            "apply_transformation": False,
            "manual_apply_transformation": bool(decision.get("transformation_code")),
            "manual": source not in editor_state or current_entry.get("manual", False),
        }
        st.session_state[f"manual_transform_{source}"] = decision.get("transformation_code", "")
        st.session_state[f"manual_apply_{source}"] = bool(decision.get("transformation_code"))
    st.session_state["mapping_editor_state"] = editor_state


def build_pending_corrections() -> list[dict]:
    pending: list[dict] = []
    for source, entry in st.session_state.get("mapping_editor_state", {}).items():
        target = entry.get("target", "")
        suggested_target = entry.get("suggested_target", "")
        status = entry.get("status", "needs_review")
        if not target or status == "rejected":
            continue
        if target == suggested_target:
            continue
        pending.append(
            {
                "source": source,
                "suggested_target": suggested_target or None,
                "corrected_target": target,
                "status": status,
            }
        )
    return pending


def persist_corrections(note: str) -> list[dict]:
    saved_entries: list[dict] = []
    pending = build_pending_corrections()
    for correction in pending:
        payload = {
            "source": correction["source"],
            "suggested_target": correction["suggested_target"],
            "corrected_target": correction["corrected_target"],
            "note": note or f"Saved from Streamlit review with status={correction['status']}",
        }
        saved_entries.append(api_request("POST", "/observability/corrections", json=payload))
    for saved in saved_entries:
        st.session_state["mapping_editor_state"][saved["source"]]["suggested_target"] = saved["corrected_target"]
    st.session_state["saved_corrections"] = saved_entries
    return saved_entries


def render_mapping_decision_summary() -> None:
    decisions = build_mapping_decisions()
    if not decisions:
        st.warning("No active mapping decisions. Accept or mark at least one candidate as needs review.")
        return
    st.subheader("Active Decisions")
    st.dataframe(decisions, width='stretch', hide_index=True)


def render_mapping_io_panel() -> None:
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
    if imported_file is not None and st.button("Apply imported mapping", width='stretch'):
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


def render_correction_panel() -> None:
    pending_corrections = build_pending_corrections()
    st.subheader("Save Corrections")
    if pending_corrections:
        st.dataframe(pending_corrections, width='stretch', hide_index=True)
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
        st.dataframe(saved_corrections, width='stretch', hide_index=True)


def render_admin_debug_tab() -> None:
    st.header("Admin / Debug")
    admin_token = st.session_state.get("admin_token", "").strip()
    token_required = admin_token_required()
    if token_required and not admin_token:
        st.warning("Admin token is required for observability and evaluation admin endpoints.")
        return
    if not token_required:
        st.info("Backend currently exposes these admin/debug endpoints without an admin token.")

    action_columns = st.columns(4)
    if action_columns[0].button("Load runtime config", width='stretch', key="debug_load_runtime_config"):
        try:
            st.session_state["debug_runtime_config"] = api_request("GET", "/observability/config")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded runtime config snapshot."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading runtime config failed: {error}"}
        st.rerun()

    if action_columns[1].button("Load decision logs", width='stretch', key="debug_load_decision_logs"):
        try:
            st.session_state["debug_decision_logs"] = api_request("GET", "/observability/decision-logs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded decision logs."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading decision logs failed: {error}"}
        st.rerun()

    if action_columns[2].button("Load saved corrections", width='stretch', key="debug_load_corrections"):
        try:
            st.session_state["debug_corrections"] = api_request("GET", "/observability/corrections")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded saved corrections."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading corrections failed: {error}"}
        st.rerun()

    if action_columns[3].button("Load benchmark runs", width='stretch', key="debug_load_benchmark_runs"):
        try:
            st.session_state["debug_runs"] = api_request("GET", "/evaluation/runs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded evaluation runs."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading evaluation runs failed: {error}"}
        st.rerun()

    runtime_config = st.session_state.get("debug_runtime_config")
    if runtime_config:
        st.subheader("Runtime Config")
        st.json(runtime_config)

    mapping_response = st.session_state.get("mapping_response")
    if mapping_response:
        knowledge_rows = knowledge_debug_rows(mapping_response)
        if knowledge_rows:
            st.subheader("Knowledge Match Insights")
            st.dataframe(
                [
                    {
                        "source": row["source"],
                        "target": row["target"],
                        "knowledge_signal": row["knowledge_signal"],
                        "confidence": row["confidence"],
                        "validator": row["validator"],
                    }
                    for row in knowledge_rows
                ],
                width='stretch',
                hide_index=True,
            )
            for row in knowledge_rows:
                with st.expander(f"Knowledge details: {row['source']} -> {row['target']}"):
                    for line in row["knowledge_explanations"]:
                        st.caption(line)

    decision_logs = st.session_state.get("debug_decision_logs")
    if decision_logs:
        st.subheader("Decision Logs")
        st.dataframe(decision_logs, width='stretch', hide_index=True)

    corrections = st.session_state.get("debug_corrections")
    if corrections:
        st.subheader("Saved Corrections")
        st.dataframe(corrections, width='stretch', hide_index=True)

    runs = st.session_state.get("debug_runs")
    if runs:
        st.subheader("Evaluation Runs")
        st.dataframe(runs, width='stretch', hide_index=True)


def benchmark_dataset_options() -> list[tuple[str, int]]:
    datasets = st.session_state.get("benchmark_datasets", [])
    return [
        (
            f"#{item['dataset_id']} | {item['name']} | v{item['version']} | cases={item['case_count']}",
            item["dataset_id"],
        )
        for item in datasets
    ]


def render_benchmark_tab() -> None:
    st.header("Benchmarks")
    admin_token = st.session_state.get("admin_token", "").strip()
    token_required = admin_token_required()
    if token_required and not admin_token:
        st.warning("Admin token is required for benchmark dataset management and saved runs.")
        return
    if not token_required:
        st.info("Backend currently allows benchmark operations without an admin token.")

    st.subheader("Save Current Mapping As Benchmark")
    benchmark_case = build_current_benchmark_case()
    benchmark_name = st.text_input(
        "Benchmark dataset name",
        value=st.session_state.get("benchmark_dataset_name", "mapping-review-benchmark"),
        key="benchmark_dataset_name",
    )
    if benchmark_case:
        st.json(benchmark_case)
    else:
        st.info("Upload data and keep at least one active mapping decision to create a benchmark dataset.")

    if st.button(
        "Save current mapping as benchmark",
        disabled=(benchmark_case is None) or (not benchmark_name.strip()),
        use_container_width=True,
        key="benchmark_save_current_mapping",
    ):
        try:
            saved = api_request(
                "POST",
                "/evaluation/datasets",
                json={"name": benchmark_name.strip(), "cases": [benchmark_case]},
            )
            st.session_state["last_action"] = {
                "level": "success",
                "message": f"Saved benchmark dataset #{saved['dataset_id']} ({saved['name']}, v{saved['version']}).",
            }
            st.rerun()
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {
                "level": "error",
                "message": f"Saving benchmark dataset failed: {error}",
            }
            st.rerun()

    st.subheader("Saved Benchmark Datasets")
    list_columns = st.columns(2)
    if list_columns[0].button("Load saved benchmark datasets", width='stretch', key="benchmark_load_datasets"):
        try:
            st.session_state["benchmark_datasets"] = api_request("GET", "/evaluation/datasets")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded saved benchmark datasets."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading benchmark datasets failed: {error}"}
        st.rerun()
    if list_columns[1].button("Load benchmark runs", width='stretch', key="benchmark_load_runs"):
        try:
            st.session_state["benchmark_runs"] = api_request("GET", "/evaluation/runs")
            st.session_state["last_action"] = {"level": "success", "message": "Loaded benchmark run history."}
        except httpx.HTTPError as error:
            st.session_state["last_action"] = {"level": "error", "message": f"Loading benchmark runs failed: {error}"}
        st.rerun()

    dataset_options = benchmark_dataset_options()
    if dataset_options:
        selected_label = st.selectbox(
            "Saved dataset",
            [label for label, _ in dataset_options],
            key="selected_benchmark_dataset_label",
        )
        selected_dataset_id = next(dataset_id for label, dataset_id in dataset_options if label == selected_label)
        with_llm = st.checkbox("Run selected benchmark with configured LLM", key="benchmark_with_llm")
        if st.button("Run selected benchmark", width='stretch', key="benchmark_run_selected"):
            try:
                result = api_request(
                    "POST",
                    f"/evaluation/datasets/{selected_dataset_id}/run?with_configured_llm={'true' if with_llm else 'false'}",
                )
                st.session_state["last_benchmark_result"] = result
                st.session_state["last_action"] = {
                    "level": "success",
                    "message": f"Ran benchmark dataset #{selected_dataset_id}.",
                }
            except httpx.HTTPError as error:
                st.session_state["last_action"] = {"level": "error", "message": f"Running benchmark failed: {error}"}
            st.rerun()
    else:
        st.info("No saved benchmark datasets loaded yet.")

    datasets = st.session_state.get("benchmark_datasets")
    if datasets:
        st.dataframe(datasets, width='stretch', hide_index=True)

    benchmark_result = st.session_state.get("last_benchmark_result")
    if benchmark_result:
        st.subheader("Last Benchmark Result")
        st.json(benchmark_result)

    benchmark_runs = st.session_state.get("benchmark_runs")
    if benchmark_runs:
        st.subheader("Benchmark Run History")
        st.dataframe(benchmark_runs, width='stretch', hide_index=True)


def main() -> None:
    st.title("Semantra - Data Mapping Review and Benchmarking")
    st.caption("Upload CSV / JSON / XML / XLSX / SQL -> Select Tables -> Review Mapping")
    render_step_status()
    render_last_action_status()

    with st.sidebar:
        st.header("Connection")
        st.text_input("API Base URL", value=DEFAULT_API_BASE_URL, key="api_base_url")
        st.text_input("Admin Token", value="", key="admin_token", type="password")
        st.markdown("This UI is a thin client above the existing FastAPI backend.")
        render_llm_runtime_status()
        if st.button("Reset flow"):
            reset_flow_state()
            st.session_state["last_action"] = {"level": "info", "message": "Flow state was reset."}
            st.rerun()

    workspace_tab, benchmark_tab, debug_tab = st.tabs(["Workspace", "Benchmarks", "Admin / Debug"])

    with workspace_tab:
        st.subheader("1. Upload")
        st.caption("Any row-based format can map to any other row-based format across CSV, JSON, XML, and XLSX.")
        source_file = st.file_uploader("Source file", type=ALL_UPLOAD_TYPES, key="source_file")
        target_file = st.file_uploader("Target file", type=ALL_UPLOAD_TYPES, key="target_file")

        source_tables: list[str] = []
        target_tables: list[str] = []
        discovery_error = None
        if source_file is not None or target_file is not None:
            try:
                source_tables = sql_tables_for_upload(source_file, "source")
                target_tables = sql_tables_for_upload(target_file, "target")
            except httpx.HTTPError as error:
                discovery_error = str(error)

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

        upload_response = st.session_state.get("upload_response")
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

        mapping_response = st.session_state.get("mapping_response")
        if mapping_response:
            # Trust Layer visualization
            display_trust_layer(mapping_response)
            render_mapping_review(mapping_response)
            render_mapping_editor(mapping_response)
            render_manual_mapping_panel(mapping_response)
            render_mapping_decision_summary()
            render_mapping_io_panel()
            render_correction_panel()
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

        preview_response = st.session_state.get("preview_response")
        if preview_response is not None:
            st.subheader("Preview")
            preview_rows = [row["values"] for row in preview_response["preview"]]
            if preview_rows:
                st.dataframe(preview_rows, width='stretch', hide_index=True)
            else:
                st.info("Preview is empty. This is expected for schema-only SQL uploads.")
            if preview_response.get("unresolved_targets"):
                st.warning(f"Needs review: {', '.join(preview_response['unresolved_targets'])}")

        codegen_response = st.session_state.get("codegen_response")
        if codegen_response is not None:
            st.subheader("Generated Pandas Code")
            st.code(codegen_response["code"], language="python")
            if codegen_response.get("warnings"):
                for warning in codegen_response["warnings"]:
                    st.warning(warning)

    with debug_tab:
        render_admin_debug_tab()

    with benchmark_tab:
        render_benchmark_tab()


if __name__ == "__main__":
    main()