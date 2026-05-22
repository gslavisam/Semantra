"""Reusable Streamlit rendering helpers shared across product surfaces."""

from __future__ import annotations

import streamlit as st

from streamlit_ui.api import admin_token_required, backend_is_reachable


STATUS_STYLES = {
    "done": ("Done", "#0f766e", "#ccfbf1"),
    "active": ("Active", "#9a3412", "#ffedd5"),
    "pending": ("Pending", "#475569", "#e2e8f0"),
}

DECISION_STATUS_BADGES = {
    "accepted": ("Accepted", "#065f46", "#d1fae5"),
    "needs_review": ("Needs Review", "#92400e", "#fef3c7"),
    "rejected": ("Rejected", "#991b1b", "#fee2e2"),
    "llm_proposal": ("LLM Proposal", "#1e3a8a", "#dbeafe"),
}

ONBOARDING_HINTS = {
    "Workspace": (
        "Workspace flow",
        "Run Setup -> Review -> Decisions -> Output in sequence. Preview stays advisory, while code generation remains governance-gated.",
    ),
    "Governance": (
        "Governance flow",
        "Canonical and Knowledge registries are steward surfaces. Overlay actions are reversible, but glossary promotion is durable and audited.",
    ),
    "Catalog": (
        "Catalog flow",
        "Use Catalog after decisions are reviewed to search reusable mapping sets and inspect reuse-fit explanations.",
    ),
    "Benchmarks": (
        "Benchmark flow",
        "Benchmarks measure mapping quality and drift. Treat them as quality telemetry, not as the decision authoring surface.",
    ),
    "System": (
        "System flow",
        "System tab is for runtime observability and debug traces. Keep analyst decision work in Workspace and Governance.",
    ),
}


def status_banner(level: str, message: str) -> None:
    """Render a Streamlit status banner using the requested severity level."""

    renderers = {
        "success": st.success,
        "error": st.error,
        "warning": st.warning,
        "info": st.info,
    }
    renderers.get(level, st.info)(message)


def current_step() -> int:
    """Return the current high-level workspace step from session state."""

    if st.session_state.get("mapping_response"):
        return 3
    if st.session_state.get("upload_response"):
        return 2
    return 1


def render_step_status() -> None:
    """Render the upload/profile/review progress cards for the workspace."""

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


def render_status_badge_legend(*, title: str = "Decision Status Legend", compact: bool = False) -> None:
    """Render one consistent status-badge legend for review/governance surfaces."""

    padding = "3px 8px" if compact else "4px 10px"
    font_size = "11px" if compact else "12px"
    badges: list[str] = []
    for _status, (label, text_color, background) in DECISION_STATUS_BADGES.items():
        badges.append(
            (
                f"<span style='display:inline-block;padding:{padding};border-radius:999px;"
                f"background:{background};color:{text_color};font-size:{font_size};font-weight:700;margin-right:6px;margin-bottom:6px;'>"
                f"{label}</span>"
            )
        )
    st.caption(title)
    st.markdown("".join(badges), unsafe_allow_html=True)


def render_operation_strip(*, compact: bool = False) -> None:
    """Render a compact operational KPI strip for the current session."""

    editor_state = st.session_state.get("mapping_editor_state") or {}
    active_decisions = 0
    open_reviews = 0
    for entry in editor_state.values():
        target = str(entry.get("target") or "").strip()
        status = str(entry.get("status") or "needs_review").strip().lower() or "needs_review"
        if target and status != "rejected":
            active_decisions += 1
        if status != "accepted" or not target:
            open_reviews += 1

    pending_llm_proposals = len(st.session_state.get("llm_decision_proposals") or [])
    canonical_concepts = len(st.session_state.get("debug_canonical_concepts") or [])
    knowledge_concepts = len(st.session_state.get("debug_knowledge_concepts") or [])

    if compact:
        st.caption("Operations")
        grid_row_1 = st.columns(2)
        grid_row_2 = st.columns(2)
        grid_row_3 = st.columns(2)
        grid_row_1[0].metric("Active decisions", active_decisions)
        grid_row_1[1].metric("Open review items", open_reviews)
        grid_row_2[0].metric("Pending LLM proposals", pending_llm_proposals)
        grid_row_2[1].metric("Canonical concepts", canonical_concepts)
        grid_row_3[0].metric("Knowledge concepts", knowledge_concepts)
        grid_row_3[1].metric("Session", "Live")
        return

    operation_columns = st.columns(5)
    operation_columns[0].metric("Active decisions", active_decisions)
    operation_columns[1].metric("Open review items", open_reviews)
    operation_columns[2].metric("Pending LLM proposals", pending_llm_proposals)
    operation_columns[3].metric("Canonical concepts", canonical_concepts)
    operation_columns[4].metric("Knowledge concepts", knowledge_concepts)


def render_onboarding_hint(area: str) -> None:
    """Render a dismissible onboarding hint for one top-level area."""

    hint = ONBOARDING_HINTS.get(area)
    if hint is None:
        return

    dismissed = st.session_state.setdefault("dismissed_onboarding_hints", {})
    if dismissed.get(area):
        return

    hint_title, hint_body = hint
    hint_columns = st.columns([10, 2])
    with hint_columns[0]:
        st.info(f"{hint_title}: {hint_body}")
    with hint_columns[1]:
        if st.button("Dismiss", key=f"dismiss_onboarding_{area}", width="stretch"):
            dismissed[area] = True
            st.session_state["dismissed_onboarding_hints"] = dismissed
            st.rerun()


def render_llm_runtime_status() -> None:
    """Render the current LLM and TTS runtime status visible to the user."""

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
    llm_status = str(config.get("llm_status", "configured")).strip().lower() or "configured"
    llm_status_detail = str(config.get("llm_status_detail", "")).strip()
    resolved_model = str(config.get("llm_resolved_model", "")).strip() or llm_model
    llm_endpoint = str(config.get("lmstudio_base_url", "")).strip()
    gate_min = config.get("llm_gate_min_score", "?")
    gate_max = config.get("llm_gate_max_score", "?")
    app_version = str(config.get("app_version", "")).strip() or "n/a"
    backend_build = str(config.get("backend_build", "")).strip() or "n/a"
    scoring_profile = str(config.get("scoring_profile", "balanced")).strip() or "balanced"
    tts_provider = str(config.get("tts_provider", "none")).strip() or "none"
    tts_timeout = config.get("tts_timeout_seconds", "?")
    tts_endpoint = str(config.get("lmstudio_tts_base_url", "")).strip()
    tts_model = str(config.get("lmstudio_orpheus_model", "")).strip() or "n/a"
    tts_voice = str(config.get("lmstudio_orpheus_voice", "")).strip() or "n/a"

    st.write("**Backend**")
    st.caption(f"Version: {app_version}")
    st.caption(f"Build: {backend_build}")
    st.caption(f"Scoring profile: {scoring_profile}")

    st.write("**LLM**")
    if llm_provider.lower() == "none":
        st.warning("LLM is currently disabled.")
    elif llm_status == "reachable":
        st.success(f"LLM reachable: {llm_provider} / {resolved_model}")
    elif llm_status == "misconfigured":
        st.error(f"LLM reachable, but configured model is unavailable: {llm_provider} / {llm_model}")
    elif llm_status == "unreachable":
        st.error(f"LLM configured but unreachable: {llm_provider} / {llm_model}")
    else:
        st.info(f"LLM configured: {llm_provider} / {llm_model}")
    if llm_status_detail:
        st.caption(llm_status_detail)
    if llm_provider.lower() == "lmstudio" and llm_endpoint:
        st.caption(f"LLM endpoint: {llm_endpoint}")
    st.caption(f"Ambiguity gate: {gate_min} - {gate_max}")

    st.write("**TTS**")
    if tts_provider.lower() == "none":
        st.info("TTS is currently disabled.")
    elif tts_provider.lower().startswith("lmstudio"):
        st.success(f"TTS configured: {tts_provider} / {tts_model}")
    else:
        st.info(f"TTS configured: {tts_provider}")
    if tts_provider.lower() != "none":
        if tts_provider.lower().startswith("lmstudio") and tts_endpoint:
            st.caption(f"TTS endpoint: {tts_endpoint}")
        st.caption(f"TTS voice: {tts_voice} | timeout={tts_timeout}s")


def render_dataset_summary(label: str, handle: dict) -> None:
    """Render one uploaded dataset's schema summary and detected column patterns."""

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
    """Render the last session action message and a backend reachability warning if needed."""

    last_action = st.session_state.get("last_action")
    if last_action:
        status_banner(last_action.get("level", "info"), last_action.get("message", ""))
    if not backend_is_reachable():
        status_banner("warning", "Backend observability check failed. Verify API Base URL or backend availability.")