from __future__ import annotations

import streamlit as st

from streamlit_ui.api import admin_token_required, backend_is_reachable


STATUS_STYLES = {
    "done": ("Done", "#0f766e", "#ccfbf1"),
    "active": ("Active", "#9a3412", "#ffedd5"),
    "pending": ("Pending", "#475569", "#e2e8f0"),
}


def status_banner(level: str, message: str) -> None:
    renderers = {
        "success": st.success,
        "error": st.error,
        "warning": st.warning,
        "info": st.info,
    }
    renderers.get(level, st.info)(message)


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
        width="stretch",
        hide_index=True,
    )


def render_last_action_status() -> None:
    last_action = st.session_state.get("last_action")
    if last_action:
        status_banner(last_action.get("level", "info"), last_action.get("message", ""))
    if not backend_is_reachable():
        status_banner("warning", "Backend observability check failed. Verify API Base URL or backend availability.")