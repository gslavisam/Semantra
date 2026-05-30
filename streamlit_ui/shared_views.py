"""Reusable Streamlit rendering helpers shared across product surfaces."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import httpx
import streamlit as st

from streamlit_ui.api import admin_token_required, api_request, backend_is_reachable, request_mapping_analysis_summary, request_review_plan_summary
from streamlit_ui.governance import mapping_output_block_reason


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

WORKSPACE_COPILOT_GUIDE = {
    "setup": "Setup is where you upload source and target data, interpret files, and establish the dataset context that unlocks the rest of Workspace.",
    "review": "Review is where you inspect suggested mappings, trust signals, and field-level issues before turning them into final decisions.",
    "decisions": "Decisions is where you close open review work, accept or reject proposals, and stabilize the mapping set before output.",
    "output": "Output is where you preview mapped results and generate governed artifacts such as Pandas, PySpark, or dbt outputs.",
    "workspace": "Workspace is the main analyst flow: Setup -> Review -> Decisions -> Output.",
    "catalog": "Catalog is the reuse surface for searching mapping sets and inspecting reuse-fit, not the main decision authoring surface.",
    "system": "System is the runtime and observability surface. Use it for connection, runtime, and debugging state.",
    "governance": "Governance is the steward surface for canonical and knowledge registries, overlays, and audited glossary promotion.",
    "benchmarks": "Benchmarks measure quality and drift. They are telemetry, not the primary authoring flow for mapping work.",
    "runtime": "Connection, runtime, and session metrics live in the left sidebar under the System view.",
}

WORKSPACE_COPILOT_CHAT_QUICK_ASK_GROUPS = {
    "Setup": (
        (
            "Most useful now",
            (
                "What unlocks Review?",
                "What metadata would improve this run?",
                "What should I do next?",
            ),
        ),
        (
            "Explain this step",
            (
                "Should I enable LLM validation here?",
                "What does Review do?",
            ),
        ),
    ),
    "Review": (
        (
            "Most useful now",
            (
                "Summarize current mapping state",
                "What should I review first?",
                "Generate proposals for current review slice",
                "What should I do next?",
            ),
        ),
        (
            "Explain this step",
            (
                "What does Decisions do?",
                "What does Output do?",
            ),
        ),
    ),
    "Decisions": (
        (
            "Most useful now",
            (
                "Which proposals are safe to apply?",
                "What still needs a decision?",
                "Summarize current mapping state",
                "What should I do next?",
            ),
        ),
        (
            "Explain this step",
            (
                "What does Output do?",
            ),
        ),
    ),
    "Output": (
        (
            "Most useful now",
            (
                "Why is codegen blocked?",
                "Refine this artifact",
                "Summarize current mapping state",
                "What should I do next?",
            ),
        ),
        (
            "Explain this step",
            (
                "What does Output do?",
            ),
        ),
    ),
    "default": (
        (
            "Most useful now",
            (
                "What is blocking Workspace now?",
                "What should I do next?",
            ),
        ),
        (
            "Explain this step",
            (
                "What does Review do?",
                "What does Output do?",
            ),
        ),
    ),
}

WORKSPACE_COPILOT_QUICK_ASK_PLACEHOLDER = "Choose a suggested question"
WORKSPACE_COPILOT_CHAT_INPUT_KEY = "workspace_copilot_chat_input"
WORKSPACE_COPILOT_PENDING_RESET_KEY = "workspace_copilot_pending_widget_reset"

APP_ROOT = Path(__file__).resolve().parents[1]
ENGLISH_HELP_PATH = APP_ROOT / "help.en.md"
REFERENCE_DOCS_PATH = APP_ROOT / "docs" / "reference"
REFERENCE_EXTRA_DOCS = (
    APP_ROOT / "docs" / "presentation" / "Conceptualization.md",
    APP_ROOT / "docs" / "presentation" / "LIVE_DEMO_RUNBOOK.md",
    APP_ROOT / "docs" / "pilot" / "REAL_LIFE_PILOT_TEST_PLAN.md",
)
REFERENCE_KROKI_BASE_URL = os.getenv("SEMANTRA_KROKI_BASE_URL", "https://kroki.io")
MERMAID_FENCE_PATTERN = re.compile(r"```mermaid\s*\n(.*?)\n```", re.IGNORECASE | re.DOTALL)


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


def _workspace_copilot_quick_ask_groups(section: str | None) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Return grouped suggested prompts for the active workspace section."""

    normalized_section = str(section or "").strip().lower()
    for section_name, groups in WORKSPACE_COPILOT_CHAT_QUICK_ASK_GROUPS.items():
        if section_name != "default" and section_name.lower() == normalized_section:
            return groups
    return WORKSPACE_COPILOT_CHAT_QUICK_ASK_GROUPS["default"]


def _workspace_copilot_quick_asks(section: str | None) -> tuple[str, ...]:
    """Return the flattened suggested prompts for the active workspace section."""

    return tuple(prompt for _group, prompts in _workspace_copilot_quick_ask_groups(section) for prompt in prompts)


def _workspace_copilot_quick_ask_options(section: str | None) -> tuple[object, ...]:
    """Return selectbox options for the active workspace section."""

    options: list[object] = [WORKSPACE_COPILOT_QUICK_ASK_PLACEHOLDER]
    for group_name, prompts in _workspace_copilot_quick_ask_groups(section):
        options.extend((group_name, prompt) for prompt in prompts)
    return tuple(options)


def _workspace_copilot_quick_ask_label(option: object) -> str:
    """Return a human-readable selectbox label for one quick-ask option."""

    if isinstance(option, tuple) and len(option) == 2:
        group_name, prompt = option
        return f"{group_name}: {prompt}"
    return WORKSPACE_COPILOT_QUICK_ASK_PLACEHOLDER


def _workspace_copilot_quick_ask_prompt(option: object) -> str:
    """Extract the prompt text from one quick-ask option."""

    if isinstance(option, tuple) and len(option) == 2:
        return str(option[1] or "").strip()
    return ""


def _workspace_copilot_apply_selected_prompt(selection_key: str, session_state: dict | None = None) -> str:
    """Mirror the selected quick-ask prompt into the chat input field."""

    state = st.session_state if session_state is None else session_state
    prompt = _workspace_copilot_quick_ask_prompt(state.get(selection_key))
    if prompt:
        state[WORKSPACE_COPILOT_CHAT_INPUT_KEY] = prompt
    return prompt


def _workspace_copilot_queue_widget_reset(quick_ask_key: str, session_state: dict | None = None) -> None:
    """Queue a safe widget reset for the next rerun after question submission."""

    state = st.session_state if session_state is None else session_state
    state[WORKSPACE_COPILOT_PENDING_RESET_KEY] = {"quick_ask_key": str(quick_ask_key or "").strip()}


def _workspace_copilot_apply_pending_widget_reset(quick_ask_key: str, session_state: dict | None = None) -> bool:
    """Apply a queued widget reset before the widgets are instantiated."""

    state = st.session_state if session_state is None else session_state
    pending_reset = state.get(WORKSPACE_COPILOT_PENDING_RESET_KEY)
    if not isinstance(pending_reset, dict):
        return False

    pending_quick_ask_key = str(pending_reset.get("quick_ask_key") or quick_ask_key or "").strip() or quick_ask_key
    state[WORKSPACE_COPILOT_CHAT_INPUT_KEY] = ""
    state[pending_quick_ask_key] = WORKSPACE_COPILOT_QUICK_ASK_PLACEHOLDER
    state.pop(WORKSPACE_COPILOT_PENDING_RESET_KEY, None)
    return True


def _workspace_run_action(state: dict, action_key: str, *, focus_sources: list[str] | None = None, origin: str = "Workspace Copilot") -> bool:
    """Execute one bounded workspace action button request."""

    normalized_key = str(action_key or "").strip()
    selected_focus_sources = [str(item).strip() for item in (focus_sources or []) if str(item).strip()]
    if normalized_key == "open_setup":
        _workspace_copilot_handoff(state, target_section="Setup", message=f"{origin} handoff -> Setup.")
    elif normalized_key == "open_review":
        _workspace_copilot_handoff(state, target_section="Review", message=f"{origin} handoff -> Review.")
    elif normalized_key == "open_review_focus":
        _workspace_copilot_handoff(
            state,
            target_section="Review",
            message=f"{origin} handoff -> Review focused on {', '.join(selected_focus_sources)}.",
            focus_sources=selected_focus_sources,
        )
    elif normalized_key == "open_decisions":
        _workspace_copilot_handoff(state, target_section="Decisions", message=f"{origin} handoff -> Decisions.")
    elif normalized_key == "open_output":
        _workspace_copilot_handoff(state, target_section="Output", message=f"{origin} handoff -> Output.")
    else:
        return False
    return True


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


def _copilot_response(
    *,
    level: str,
    kind: str,
    answer: str,
    why: str = "",
    next_actions: list[str] | None = None,
    action_buttons: list[dict] | None = None,
    artifacts: dict | None = None,
) -> dict:
    return {
        "level": level,
        "kind": kind,
        "answer": answer,
        "why": why,
        "next_actions": list(next_actions or []),
        "action_buttons": list(action_buttons or []),
        "artifacts": dict(artifacts or {}),
    }


def _workspace_copilot_validator_badge(method: str) -> str:
    labels = {
        "llm_validated": "LLM validator",
        "multi_signal_heuristic": "Heuristic",
        "manual_review": "Manual",
    }
    return labels.get(method, str(method or "").replace("_", " ").title())


def _workspace_copilot_handoff(
    state: dict,
    *,
    target_section: str,
    message: str,
    focus_sources: list[str] | None = None,
) -> None:
    state["pending_top_level_area"] = "Workspace"
    state["active_top_level_area"] = "Workspace"
    state["pending_workspace_section"] = target_section
    state["active_workspace_section"] = target_section
    if target_section == "Review" and focus_sources:
        state["review_focus_sources"] = list(focus_sources)
    elif target_section != "Review":
        state.pop("review_focus_sources", None)
    state["last_action"] = {"level": "info", "message": message}
    st.rerun()


def _workspace_pin_output_context(state: dict) -> None:
    state["pending_top_level_area"] = "Workspace"
    state["active_top_level_area"] = "Workspace"
    state["pending_workspace_section"] = "Output"
    state["active_workspace_section"] = "Output"


def _workspace_target_context_message(state: dict) -> str:
    upload_response = state.get("upload_response") or {}
    mapping_response = state.get("mapping_response") or {}
    mapping_runtime = (mapping_response or {}).get("mapping_runtime") or {}
    mapping_mode = str(upload_response.get("mapping_mode") or "standard").strip().lower() or "standard"
    target_system = str(mapping_runtime.get("target_system") or upload_response.get("target_system") or "").strip().lower() or None
    projection_mode = str(mapping_runtime.get("target_projection_mode") or "").strip().lower()
    if not projection_mode:
        if mapping_mode == "canonical":
            projection_mode = "canonical_only" if target_system in {None, "canonical"} else "target_aware_canonical"
        else:
            projection_mode = "dataset_to_dataset"

    intent = "Uploaded target dataset"
    if mapping_mode == "canonical":
        intent = "SAP" if target_system == "sap" else "Canonical only"

    projection_label = {
        "canonical_only": "canonical-only",
        "target_aware_canonical": "target-aware canonical",
    }.get(projection_mode, "dataset-to-dataset")
    return f"{intent} / {projection_label}"


def _workspace_current_mapping_rows(state: dict) -> list[dict]:
    mapping_response = state.get("mapping_response") or {}
    if not mapping_response or not isinstance(mapping_response.get("ranked_mappings"), list):
        return []

    from streamlit_ui.mapping_helpers import current_mapping_rows

    return current_mapping_rows(
        mapping_response,
        state,
        validator_badge=_workspace_copilot_validator_badge,
    )


def _workspace_filtered_review_rows(state: dict) -> list[dict]:
    rows = _workspace_current_mapping_rows(state)
    status_filter = str(state.get("filter_status") or "All").strip() or "All"
    confidence_filter = str(state.get("filter_confidence") or "All").strip() or "All"
    source_filter = str(state.get("filter_source") or "All").strip() or "All"
    focused_sources = [str(item).strip() for item in (state.get("review_focus_sources") or []) if str(item).strip()]

    filtered = rows
    if status_filter != "All":
        filtered = [row for row in filtered if str(row.get("status") or "").strip() == status_filter]
    if confidence_filter != "All":
        filtered = [row for row in filtered if str(row.get("confidence_label") or "").strip() == confidence_filter]
    if source_filter != "All":
        filtered = [row for row in filtered if str(row.get("source") or "").strip() == source_filter]
    elif focused_sources:
        filtered = [row for row in filtered if str(row.get("source") or "").strip() in focused_sources]
    return filtered


def _workspace_review_plan_payload(state: dict) -> tuple[list[dict], list[dict], dict[str, str]]:
    from streamlit_ui.workspace_review_views import _review_attention_summary_rows

    filtered_rows = _workspace_filtered_review_rows(state)
    attention_summary_rows = _review_attention_summary_rows(filtered_rows)
    filters = {
        "status": str(state.get("filter_status") or "All").strip() or "All",
        "confidence": str(state.get("filter_confidence") or "All").strip() or "All",
        "source": str(state.get("filter_source") or (", ".join(state.get("review_focus_sources") or []) if state.get("review_focus_sources") else "All")).strip() or "All",
    }
    return filtered_rows, attention_summary_rows, filters


def _workspace_review_priority_score(row: dict) -> int:
    score = 0
    if not str(row.get("target") or "").strip():
        score += 5

    status = str(row.get("status") or "needs_review").strip().lower() or "needs_review"
    if status != "accepted":
        score += 3
    if status == "needs_review":
        score += 2

    confidence_label = str(row.get("confidence_label") or "low_confidence").strip().lower() or "low_confidence"
    if confidence_label == "low_confidence":
        score += 3
    elif confidence_label == "medium_confidence":
        score += 1

    canonical_status = str(row.get("canonical_status") or "").strip().lower()
    if canonical_status in {"source_target_mismatch", "source_only", "target_only", "no_canonical_match"}:
        score += 2

    if row.get("llm_consulted"):
        score += 1
    return score


def _workspace_review_priority_rows(state: dict, *, limit: int = 3) -> list[dict]:
    filtered_rows = [
        row for row in _workspace_filtered_review_rows(state)
        if str(row.get("status") or "needs_review").strip().lower() != "accepted"
    ]
    prioritized = sorted(
        filtered_rows,
        key=lambda row: (-_workspace_review_priority_score(row), str(row.get("source") or "").strip().lower()),
    )
    return prioritized[:limit]


def _workspace_review_row_detail(row: dict) -> str:
    source = str(row.get("source") or "unknown_source").strip() or "unknown_source"
    target = str(row.get("target") or "unmapped").strip() or "unmapped"
    status = str(row.get("status") or "needs_review").strip().replace("_", " ") or "needs review"
    confidence = str(row.get("confidence_label") or "low_confidence").strip().replace("_", " ") or "low confidence"
    validator = str(row.get("validator") or "").strip()
    detail = f"{source} -> {target} (status: {status}, confidence: {confidence}"
    if validator:
        detail += f", validator: {validator}"
    detail += ")"
    canonical_path = str(row.get("canonical_path") or "").strip()
    if canonical_path:
        detail += f". Canonical path: {canonical_path}."
    return detail


def _workspace_codegen_language_label(language: str | None) -> str:
    normalized = str(language or "").strip().lower()
    if normalized == "python-pyspark":
        return "PySpark"
    if normalized == "sql-dbt":
        return "dbt SQL"
    if normalized == "python":
        return "Python"
    return normalized or "generated"


def _workspace_artifact_summary(state: dict) -> dict:
    codegen_response = state.get("codegen_response") or {}
    refinement_response = state.get("codegen_refinement_response") or {}
    current_code = str(codegen_response.get("code") or "").strip()
    refinement_code = str(refinement_response.get("code") or "").strip()
    warnings = codegen_response.get("warnings") or []
    warning_codes = [
        str(item.get("code") or "warning").strip()
        for item in warnings
        if isinstance(item, dict) and str(item.get("code") or "").strip()
    ]
    refinement_reasoning = [str(item).strip() for item in (refinement_response.get("reasoning") or []) if str(item).strip()]
    refinement_warnings = refinement_response.get("warnings") or []

    current_summary = ""
    if current_code:
        current_summary = f"{_workspace_codegen_language_label(codegen_response.get('language'))} artifact"
        if warnings:
            current_summary += f" with {len(warnings)} warning(s)"
        else:
            current_summary += " with no reported warnings"
    return {
        "has_artifact": bool(current_code),
        "artifact_language": _workspace_codegen_language_label(codegen_response.get("language")),
        "warning_count": len(warnings),
        "warning_codes": warning_codes,
        "current_summary": current_summary,
        "refinement_pending": bool(refinement_code),
        "refinement_reasoning_count": len(refinement_reasoning),
        "refinement_warning_count": len(refinement_warnings),
        "refinement_reasoning": refinement_reasoning,
        "refinement_warnings": refinement_warnings,
    }


def _workspace_has_reachable_llm(state: dict) -> bool:
    runtime = state.get("runtime_config_snapshot") or {}
    provider = str(runtime.get("llm_provider", "none")).strip().lower() or "none"
    status = str(runtime.get("llm_status", "configured")).strip().lower() or "configured"
    return provider != "none" and status == "reachable"


def _workspace_generate_proposals(state: dict) -> list[dict]:
    mapping_response = state.get("mapping_response") or {}
    if not mapping_response:
        raise ValueError("Generate mapping results before preparing decision proposals.")

    from streamlit_ui.workspace_review_views import _llm_decision_proposals_for_filtered_rows

    filtered_rows = _workspace_filtered_review_rows(state)
    proposals = _llm_decision_proposals_for_filtered_rows(
        filtered_rows,
        mapping_response,
        state.get("mapping_editor_state", {}),
        include_live_llm_fill=False,
        request_llm_mapping_refinement=None,
        llm_runtime_available=_workspace_has_reachable_llm(state),
    )
    state["llm_decision_proposals"] = proposals
    return proposals


def _workspace_apply_safe_proposals(state: dict) -> tuple[int, list[str]]:
    from streamlit_ui.workspace_decision_views import _apply_llm_decision_proposal

    proposals = list(state.get("llm_decision_proposals") or [])
    editor_state = state.setdefault("mapping_editor_state", {})
    applied_sources: list[str] = []
    remaining_proposals: list[dict] = []
    for proposal in proposals:
        if proposal.get("safe_to_apply") and _apply_llm_decision_proposal(editor_state, proposal):
            applied_sources.append(str(proposal.get("source") or ""))
            continue
        remaining_proposals.append(proposal)
    state["mapping_editor_state"] = editor_state
    state["llm_decision_proposals"] = remaining_proposals
    return len(applied_sources), applied_sources


def _workspace_selected_proposal(state: dict) -> dict | None:
    proposals = list(state.get("llm_decision_proposals") or [])
    if not proposals:
        return None
    selected_source = str(state.get("workspace_copilot_selected_proposal_source") or proposals[0].get("source") or "").strip()
    proposal = next((item for item in proposals if str(item.get("source") or "").strip() == selected_source), None)
    return proposal or proposals[0]


def _workspace_execute_artifact_refinement(state: dict) -> dict:
    codegen_response = state.get("codegen_refinement_response") or state.get("codegen_response") or {}
    current_code = str(codegen_response.get("code") or "").strip()
    if not current_code:
        raise ValueError("Generate an output artifact before asking Copilot to refine it.")

    instruction = str(state.get("workspace_copilot_refinement_instruction") or "").strip()
    if not instruction:
        raise ValueError("Add a refinement instruction before running artifact refinement.")

    language = str(codegen_response.get("language") or "").strip().lower()
    mode = "pyspark" if language == "python-pyspark" else "dbt" if language == "sql-dbt" else "pandas"
    refinement_response = api_request(
        "POST",
        "/mapping/codegen/refine",
        json={
            "mode": mode,
            "current_code": current_code,
            "instruction": instruction,
            "edge_cases": str(state.get("workspace_copilot_refinement_edge_cases") or "").strip(),
            "reference_excerpt": str(state.get("workspace_copilot_refinement_reference") or "").strip(),
        },
        timeout=90.0,
    )
    _workspace_pin_output_context(state)
    state["codegen_refinement_response"] = refinement_response
    state["last_action"] = {
        "level": "success",
        "message": "Generated a refinement candidate from the provided copilot instructions.",
    }
    return refinement_response


def _workspace_accept_refinement(state: dict) -> None:
    refinement_response = state.get("codegen_refinement_response") or {}
    if not refinement_response:
        return
    _workspace_pin_output_context(state)
    state["codegen_response"] = refinement_response
    state.pop("codegen_refinement_response", None)
    state["last_action"] = {
        "level": "success",
        "message": "Accepted the refined artifact as the current generated code.",
    }
    st.rerun()


def _workspace_discard_refinement(state: dict) -> None:
    _workspace_pin_output_context(state)
    state.pop("codegen_refinement_response", None)
    state["last_action"] = {
        "level": "info",
        "message": "Discarded the pending refinement and kept the original generated code.",
    }
    st.rerun()


def _workspace_output_block_reason(state: dict) -> str:
    mapping_rows = _workspace_current_mapping_rows(state)
    decisions = [
        {"source": row.get("source"), "status": row.get("status")}
        for row in mapping_rows
        if str(row.get("target") or "").strip()
    ]
    mode = str(state.get("output_codegen_mode", "pandas") or "pandas")
    return mapping_output_block_reason(decisions, action_label={
        "pyspark": "PySpark code generation",
        "dbt": "dbt model generation",
    }.get(mode, "Pandas code generation"))


def workspace_copilot_chat_response(
    question: str,
    session_state: dict | None = None,
    *,
    request_mapping_analysis_summary_func=request_mapping_analysis_summary,
    request_review_plan_summary_func=request_review_plan_summary,
) -> dict:
    """Return one bounded copilot response using workspace/app context only."""

    state = st.session_state if session_state is None else session_state
    context = workspace_copilot_sidebar_context(state)
    brief = workspace_copilot_sidebar_brief(state)
    normalized = str(question or "").strip().lower()
    if not normalized:
        return _copilot_response(
            level="info",
            kind="empty",
            answer="Ask about Workspace sections, queue order, proposal safety, output gating, or artifact refinement.",
            why="WS Copilot stays bounded to the current Workspace context and existing product flows.",
        )

    if "unlock" in normalized and "review" in normalized:
        if not context["has_upload"]:
            return _copilot_response(
                level="info",
                kind="setup-unlock",
                answer="Review unlocks only after you upload the active source/target context and generate mapping results.",
                why="Without an upload payload and mapping response, Review has no row-level mapping surface to work with.",
                next_actions=["Upload and profile the dataset pair in Setup.", "Run mapping generation from Setup."],
                action_buttons=[{"label": "Open Setup", "action": "open_setup"}],
            )
        if not context["mapping_ready"]:
            return _copilot_response(
                level="warning",
                kind="setup-unlock",
                answer="The upload is ready, but Review stays locked until you generate mapping from Setup.",
                why="Review depends on an active mapping response, not only uploaded files.",
                next_actions=["Run Generate mapping or Generate canonical mapping."],
            )
        return _copilot_response(
            level="success",
            kind="setup-unlock",
            answer="Review is already unlocked for this workspace state.",
            why="An active mapping response exists for the current upload context.",
            next_actions=["Open Review and inspect unresolved rows."],
            action_buttons=[{"label": "Open Review", "action": "open_review"}],
        )

    if "llm validation" in normalized:
        if not _workspace_has_reachable_llm(state):
            return _copilot_response(
                level="warning",
                kind="setup-llm-validation",
                answer="Do not enable LLM validation here unless LM Studio is reachable.",
                why="The ambiguity-band validator only adds value when the configured LLM runtime is live.",
                next_actions=["Keep the toggle off until runtime shows reachable.", "Use source descriptions and companion metadata to improve heuristic matching."],
            )
        return _copilot_response(
            level="info",
            kind="setup-llm-validation",
            answer="Enable LLM validation when you expect ambiguous fields and want bounded second-pass validation in the ambiguity band.",
            why="It is most useful when heuristics alone will not be strong enough for borderline matches.",
            next_actions=["Keep it off for clean, obvious mappings.", "Combine it with source descriptions when field names are technical or opaque."],
        )

    if "metadata" in normalized:
        return _copilot_response(
            level="info",
            kind="setup-metadata",
            answer="Companion metadata helps most when source or target files have technical names, thin descriptions, or row-data uploads with weak semantic clues.",
            why="Descriptions, types, and sample values give the mapping engine more semantic evidence before bounded LLM help is needed.",
            next_actions=["Add source companion metadata first.", "Add target companion metadata too for standard source-to-target runs."],
        )

    if (
        any(token in normalized for token in ("block", "blocked", "what now", "risk", "stuck"))
        or "what should i do next" in normalized
        or normalized == "next"
    ) and "codegen" not in normalized:
        risk_text = brief["risks"][0] if brief["risks"] else "No major blockers are visible in the current workspace snapshot."
        next_text = brief["next_actions"][0] if brief["next_actions"] else "No immediate action is required."
        buttons: list[dict] = []
        if context["section"] != "Review" and context["mapping_ready"]:
            buttons.append({"label": "Open Review", "action": "open_review"})
        return _copilot_response(
            level="info",
            kind="brief",
            answer=brief["now"],
            why=f"Primary risk: {risk_text}",
            next_actions=[next_text],
            action_buttons=buttons,
        )

    if "summarize" in normalized and "mapping" in normalized or "current mapping state" in normalized:
        if not context["mapping_ready"]:
            return _copilot_response(
                level="warning",
                kind="mapping-blocked",
                answer="There is no active mapping result yet.",
                why="Mapping Analysis Overview reuses the current workspace mapping response.",
                next_actions=["Generate mapping from Setup first."],
                action_buttons=[{"label": "Open Setup", "action": "open_setup"}],
            )
        try:
            summary = request_mapping_analysis_summary_func()
            state["mapping_analysis_summary"] = summary
        except Exception as error:
            return _copilot_response(
                level="warning",
                kind="mapping-summary-error",
                answer="Workspace has mapping results, but the technical overview is unavailable right now.",
                why=f"Mapping Analysis Overview failed: {error}",
                next_actions=["Check runtime availability and retry from Review."],
            )

        overall = (summary or {}).get("overall_mapping_health") or {}
        accepted_count = int(overall.get("accepted_count") or context["accepted_items"])
        needs_review_count = int(overall.get("needs_review_count") or context["open_review_items"])
        unmatched_count = int(overall.get("unmatched_count") or 0)
        summary_text = str(overall.get("summary") or "").strip() or (
            f"Current mapping state: {accepted_count} accepted, {needs_review_count} needs review, {unmatched_count} unmatched."
        )
        action_buttons = [{"label": "Open Review", "action": "open_review"}]
        if needs_review_count == 0 and unmatched_count == 0:
            action_buttons.append({"label": "Open Decisions", "action": "open_decisions"})
        return _copilot_response(
            level="success" if needs_review_count == 0 and unmatched_count == 0 else "info",
            kind="mapping-summary",
            answer=f"{summary_text} Target context: {_workspace_target_context_message(state)}.",
            why=f"Accepted: {accepted_count} | Needs review: {needs_review_count} | Unmatched: {unmatched_count}.",
            next_actions=[
                f"Review {needs_review_count} unresolved row(s)." if needs_review_count else "Move into Decisions or Output for the next bounded step.",
            ],
            action_buttons=action_buttons,
        )

    if "review first" in normalized:
        if not context["mapping_ready"]:
            return _copilot_response(
                level="warning",
                kind="review-plan-blocked",
                answer="Review planning is unavailable until mapping exists.",
                why="Review Queue Plan operates on the current filtered review slice.",
                next_actions=["Generate mapping from Setup first."],
                action_buttons=[{"label": "Open Setup", "action": "open_setup"}],
            )
        filtered_rows, attention_summary_rows, filters = _workspace_review_plan_payload(state)
        try:
            plan_summary = request_review_plan_summary_func(
                filtered_rows,
                attention_summary_rows,
                status_filter=filters["status"],
                confidence_filter=filters["confidence"],
                source_filter=filters["source"],
            )
            state["review_plan_summary"] = plan_summary
        except Exception as error:
            return _copilot_response(
                level="error",
                kind="review-plan-error",
                answer="Review queue planning failed for the current slice.",
                why=str(error),
                next_actions=["Retry from Review after checking the active filters and runtime state."],
            )
        queue_summary = str(plan_summary.get("queue_summary") or "").strip() or "Generated a bounded review queue plan for the current review slice."
        risks = [str(item).strip() for item in (plan_summary.get("risks") or []) if str(item).strip()]
        next_actions = [str(item).strip() for item in (plan_summary.get("next_actions") or []) if str(item).strip()]
        priority_rows = _workspace_review_priority_rows(state)
        focus_sources = [str(row.get("source") or "").strip() for row in priority_rows if str(row.get("source") or "").strip()]
        focus_details = [_workspace_review_row_detail(row) for row in priority_rows]
        if not next_actions:
            next_actions = ["Open Review and work the highest-priority unresolved rows first."]
        action_buttons = [{"label": "Open Review", "action": "open_review"}]
        if focus_sources:
            action_buttons.insert(
                0,
                {"label": "Focus top review rows", "action": "open_review_focus", "focus_sources": focus_sources},
            )
            next_actions = [f"Focus Review on: {', '.join(focus_sources)}.", *next_actions]
        return _copilot_response(
            level="info",
            kind="review-plan",
            answer=f"{queue_summary} First focus: {focus_details[0]}" if focus_details else queue_summary,
            why=(
                f"{risks[0]} Priority rows: {'; '.join(focus_details[:2])}"
                if risks and focus_details
                else risks[0] if risks
                else f"Priority rows: {'; '.join(focus_details[:2])}" if focus_details
                else "Review Queue Plan is a read-only queue guidance surface for the current filtered rows."
            ),
            next_actions=next_actions,
            action_buttons=action_buttons,
            artifacts={"risks": risks, "next_actions_detail": next_actions, "focus_sources": focus_sources, "focus_details": focus_details},
        )

    if "generate proposals" in normalized:
        if not context["mapping_ready"]:
            return _copilot_response(
                level="warning",
                kind="proposal-blocked",
                answer="Decision proposal generation is unavailable until mapping exists.",
                why="Proposal generation runs on the current needs-review slice.",
                next_actions=["Generate mapping from Setup first."],
                action_buttons=[{"label": "Open Setup", "action": "open_setup"}],
            )
        proposals = _workspace_generate_proposals(state)
        safe_proposals = [proposal for proposal in proposals if proposal.get("safe_to_apply")]
        next_actions = [
            f"Review {len(proposals)} generated proposal(s) in Decisions." if proposals else "No proposals were generated for the current review slice.",
        ]
        action_buttons = [{"label": "Open Decisions", "action": "open_decisions"}] if proposals else [{"label": "Open Review", "action": "open_review"}]
        if safe_proposals:
            action_buttons.insert(0, {"label": "Apply safe proposals", "action": "apply_safe_proposals"})
        return _copilot_response(
            level="success" if proposals else "info",
            kind="proposal-generation",
            answer=(
                f"Prepared {len(proposals)} LLM decision proposal(s) for the current review slice."
                if proposals
                else "No proposal candidates were available for the current review slice."
            ),
            why=(
                f"{len(safe_proposals)} proposal(s) are currently marked safe_to_apply."
                if proposals
                else "The current slice may already be closed, filtered too tightly, or missing cached proposition evidence."
            ),
            next_actions=next_actions,
            action_buttons=action_buttons,
        )

    if "safe to apply" in normalized or "still needs a decision" in normalized:
        proposals = list(state.get("llm_decision_proposals") or [])
        if not proposals:
            return _copilot_response(
                level="info",
                kind="proposal-summary",
                answer="There are no pending LLM decision proposals right now.",
                why="Decisions can still contain manual overrides, but there is no cached proposal queue to summarize.",
                next_actions=["Generate proposals from Review if you want bounded LLM proposal help."],
                action_buttons=[{"label": "Open Review", "action": "open_review"}],
            )
        safe_proposals = [proposal for proposal in proposals if proposal.get("safe_to_apply")]
        selected = _workspace_selected_proposal(state)
        selected_summary = str((selected or {}).get("summary") or "").strip()
        next_actions = [f"{len(safe_proposals)} proposal(s) can be applied conservatively."]
        if len(proposals) != len(safe_proposals):
            next_actions.append(f"{len(proposals) - len(safe_proposals)} proposal(s) still need manual review.")
        buttons = [{"label": "Open Decisions", "action": "open_decisions"}]
        if safe_proposals:
            buttons.insert(0, {"label": "Apply safe proposals", "action": "apply_safe_proposals"})
        return _copilot_response(
            level="warning" if len(proposals) != len(safe_proposals) else "info",
            kind="proposal-summary",
            answer=f"There are {len(proposals)} pending proposal(s), and {len(safe_proposals)} are marked safe_to_apply.",
            why=selected_summary or "Proposal safety is derived from bounded evidence and current editor-state compatibility checks.",
            next_actions=next_actions,
            action_buttons=buttons,
        )

    if "codegen blocked" in normalized or ("blocked" in normalized and "codegen" in normalized):
        if not context["mapping_ready"]:
            return _copilot_response(
                level="warning",
                kind="output-blocked",
                answer="Code generation is unavailable until mapping exists.",
                why="Output depends on the active mapping decisions.",
                next_actions=["Generate mapping from Setup first."],
                action_buttons=[{"label": "Open Setup", "action": "open_setup"}],
            )
        block_reason = _workspace_output_block_reason(state)
        artifact_summary = _workspace_artifact_summary(state)
        priority_rows = _workspace_review_priority_rows(state, limit=2)
        if block_reason:
            why_parts = ["Output gating follows active review status governance."]
            if priority_rows:
                why_parts.append(f"Current blockers: {'; '.join(_workspace_review_row_detail(row) for row in priority_rows)}")
            if artifact_summary["has_artifact"]:
                why_parts.append(f"Current artifact: {artifact_summary['current_summary']}.")
            return _copilot_response(
                level="warning",
                kind="output-blocked",
                answer=block_reason,
                why=" ".join(why_parts),
                next_actions=["Accept or close remaining review statuses before generating code.", "Use preview only as an inspection aid until review statuses are closed."],
                action_buttons=[{"label": "Open Decisions", "action": "open_decisions"}, {"label": "Open Review", "action": "open_review"}],
            )
        mode = str(state.get("output_codegen_mode", "pandas") or "pandas")
        why_parts = ["All active mapping decisions are in a codegen-compatible state."]
        next_actions = ["Open Output and generate the artifact when you are ready."]
        if artifact_summary["has_artifact"]:
            why_parts.append(f"Current artifact: {artifact_summary['current_summary']}.")
            if artifact_summary["warning_codes"]:
                why_parts.append(f"Warning codes: {', '.join(artifact_summary['warning_codes'])}.")
                next_actions = ["Inspect the current artifact warnings before finalizing or sharing the output."]
            if artifact_summary["refinement_pending"]:
                why_parts.append(
                    f"A refinement candidate is pending with {artifact_summary['refinement_reasoning_count']} reasoning note(s) and {artifact_summary['refinement_warning_count']} warning(s)."
                )
                next_actions.append("Compare the pending refinement candidate before accepting it.")
        return _copilot_response(
            level="success",
            kind="output-ready",
            answer=f"{mode.title() if mode != 'dbt' else 'dbt'} code generation is currently unblocked.",
            why=" ".join(why_parts),
            next_actions=next_actions,
            action_buttons=[{"label": "Open Output", "action": "open_output"}],
        )

    if "refine this artifact" in normalized or "refine artifact" in normalized:
        codegen_response = state.get("codegen_refinement_response") or state.get("codegen_response") or {}
        if not str(codegen_response.get("code") or "").strip():
            return _copilot_response(
                level="info",
                kind="artifact-refinement-blocked",
                answer="Artifact refinement is unavailable until a generated artifact exists.",
                why="Refinement reuses the current Output artifact as its source.",
                next_actions=["Generate preview or code from Output first."],
                action_buttons=[{"label": "Open Output", "action": "open_output"}],
            )
        artifact_summary = _workspace_artifact_summary(state)
        why_parts = []
        if artifact_summary["current_summary"]:
            why_parts.append(f"Current artifact: {artifact_summary['current_summary']}.")
        if artifact_summary["warning_codes"]:
            why_parts.append(f"Current warning codes: {', '.join(artifact_summary['warning_codes'])}.")
        if artifact_summary["refinement_pending"]:
            why_parts.append(
                f"Pending refinement candidate: {artifact_summary['refinement_reasoning_count']} reasoning note(s), {artifact_summary['refinement_warning_count']} warning(s)."
            )
        next_actions = ["Describe the refinement you want.", "Run refinement.", "Explicitly accept or discard the generated candidate."]
        if artifact_summary["warning_count"]:
            next_actions.insert(0, "Use the existing warnings to target the refinement request.")
        return _copilot_response(
            level="info",
            kind="artifact-refinement",
            answer=f"Artifact refinement is ready for the current {artifact_summary['artifact_language']} artifact. Add an instruction, edge cases, or reference excerpt below, then run refinement.",
            why=" ".join(why_parts) or "This reuses the existing bounded `/mapping/codegen/refine` workflow and still requires explicit accept/discard after a candidate is generated.",
            next_actions=next_actions,
            action_buttons=[{"label": "Open Output", "action": "open_output"}],
        )

    for topic, answer in WORKSPACE_COPILOT_GUIDE.items():
        if topic in normalized:
            return _copilot_response(
                level="info",
                kind="guide",
                answer=answer,
                why="This answer comes from the bounded Workspace guidance map, not an open-ended chat path.",
            )

    return _copilot_response(
        level="info",
        kind="fallback",
        answer="I can help with Workspace navigation, queue order, proposal safety, codegen blockers, and artifact refinement.",
        why="Ask things like 'What unlocks Review?', 'What should I review first?', 'Which proposals are safe to apply?', or 'Refine this artifact'.",
    )
def submit_workspace_copilot_chat_question(
    question: str,
    session_state: dict | None = None,
    *,
    request_mapping_analysis_summary_func=request_mapping_analysis_summary,
    request_review_plan_summary_func=request_review_plan_summary,
) -> dict:
    """Resolve one bounded copilot question and append it to sidebar chat history."""

    state = st.session_state if session_state is None else session_state
    response = workspace_copilot_chat_response(
        question,
        state,
        request_mapping_analysis_summary_func=request_mapping_analysis_summary_func,
        request_review_plan_summary_func=request_review_plan_summary_func,
    )
    history = list(state.get("workspace_copilot_chat_history") or [])
    history.append(
        {
            "question": str(question or "").strip(),
            "answer": str(response.get("answer") or "").strip(),
            "why": str(response.get("why") or "").strip(),
            "level": str(response.get("level") or "info").strip(),
            "kind": str(response.get("kind") or "info").strip(),
        }
    )
    state["workspace_copilot_chat_history"] = history[-6:]
    state["workspace_copilot_chat_last_response"] = response
    return response


def workspace_copilot_sidebar_context(session_state: dict | None = None) -> dict:
    """Return a compact, read-only Workspace Copilot context snapshot for sidebar rendering."""

    state = st.session_state if session_state is None else session_state
    upload_response = state.get("upload_response") or {}
    mapping_response = state.get("mapping_response") or {}
    mapping_runtime = (mapping_response or {}).get("mapping_runtime") or {}
    preview_response = state.get("preview_response") or {}
    codegen_response = state.get("codegen_refinement_response") or state.get("codegen_response") or {}
    mapping_editor_state = state.get("mapping_editor_state") or {}
    runtime_config = state.get("runtime_config_snapshot") or {}
    result = state.get("workspace_copilot_result") or {}

    active_area = str(state.get("active_top_level_area") or "Workspace").strip() or "Workspace"
    section = str(state.get("active_workspace_section") or "Setup").strip() or "Setup"
    mapping_mode = str(upload_response.get("mapping_mode") or "standard").strip().lower() or "standard"
    target_system = str(mapping_runtime.get("target_system") or upload_response.get("target_system") or "").strip().lower() or None
    projection_mode = str(mapping_runtime.get("target_projection_mode") or "").strip().lower()
    if not projection_mode:
        if mapping_mode == "canonical":
            projection_mode = "canonical_only" if target_system in {None, "canonical"} else "target_aware_canonical"
        else:
            projection_mode = "dataset_to_dataset"

    if mapping_mode != "canonical":
        target_intent = "Uploaded target dataset"
    elif target_system == "sap":
        target_intent = "SAP"
    else:
        target_intent = "Canonical only"

    projection_label = {
        "canonical_only": "canonical-only",
        "target_aware_canonical": "target-aware canonical",
    }.get(projection_mode, "dataset-to-dataset")

    provider = str(runtime_config.get("llm_provider", "none")).strip() or "none"
    runtime_status = str(runtime_config.get("llm_status", "configured")).strip().lower() or "configured"
    resolved_model = str(runtime_config.get("llm_resolved_model", "")).strip() or str(runtime_config.get("llm_model", "")).strip() or "n/a"
    if provider.lower() == "none":
        runtime_message = "LLM unavailable"
    elif runtime_status == "reachable":
        runtime_message = f"LLM ready: {provider} / {resolved_model}"
    elif runtime_status == "disabled":
        runtime_message = "LLM disabled"
    elif runtime_status == "misconfigured":
        runtime_message = f"LLM misconfigured: {provider} / {resolved_model}"
    elif runtime_status == "unreachable":
        runtime_message = f"LLM unreachable: {provider} / {resolved_model}"
    else:
        runtime_message = f"LLM configured: {provider} / {resolved_model}"

    active_decisions = 0
    open_review_items = 0
    accepted_items = 0
    for entry in mapping_editor_state.values():
        target = str((entry or {}).get("target") or "").strip()
        if not target:
            continue
        active_decisions += 1
        status = str((entry or {}).get("status") or "needs_review").strip().lower() or "needs_review"
        if status == "accepted":
            accepted_items += 1
        else:
            open_review_items += 1

    pending_proposals = len(state.get("llm_decision_proposals") or [])
    latest_answer = str(result.get("answer") or "").strip() or None
    has_upload = bool(upload_response)
    mapping_ready = bool(mapping_response)
    preview_ready = bool(preview_response)
    output_ready = bool(codegen_response)
    area_note = "" if active_area == "Workspace" else f"Viewing {active_area} while this sidebar mirrors the latest Workspace state."

    if not has_upload:
        readiness_level = "info"
        readiness_message = "Setup is waiting for source and target upload context."
    elif not mapping_ready:
        readiness_level = "warning"
        readiness_message = "Upload is ready, but Review stays locked until mapping is generated."
    elif open_review_items > 0 or pending_proposals > 0:
        readiness_level = "warning"
        readiness_message = (
            f"Workspace still has {open_review_items} open review item(s) and {pending_proposals} pending proposal(s)."
        )
    else:
        readiness_level = "success"
        readiness_message = "Workspace state is stable enough for output follow-up."

    return {
        "active_area": active_area,
        "section": section,
        "target_intent": target_intent,
        "projection_label": projection_label,
        "runtime_message": runtime_message,
        "active_decisions": active_decisions,
        "accepted_items": accepted_items,
        "open_review_items": open_review_items,
        "pending_proposals": pending_proposals,
        "has_upload": has_upload,
        "mapping_ready": mapping_ready,
        "preview_ready": preview_ready,
        "output_ready": output_ready,
        "latest_answer": latest_answer,
        "area_note": area_note,
        "readiness_level": readiness_level,
        "readiness_message": readiness_message,
    }


def render_workspace_copilot_sidebar_context(session_state: dict | None = None) -> None:
    """Render the full Workspace Copilot sidebar shell."""

    state = st.session_state if session_state is None else session_state
    context = workspace_copilot_sidebar_context(state)
    st.subheader("WS Copilot Context")
    st.caption("Read-only workspace context mirrored into the sidebar.")
    st.caption(f"Area: {context['active_area']} | Section: {context['section']}")
    st.caption(f"Target: {context['target_intent']} | Projection: {context['projection_label']}")
    st.caption(context["runtime_message"])

    if context["area_note"]:
        st.info(context["area_note"])

    if context["readiness_level"] == "success":
        st.success(context["readiness_message"])
    elif context["readiness_level"] == "warning":
        st.warning(context["readiness_message"])
    else:
        st.info(context["readiness_message"])

    metric_row_1 = st.columns(2)
    metric_row_2 = st.columns(2)
    metric_row_1[0].metric("Active decisions", int(context["active_decisions"]))
    metric_row_1[1].metric("Accepted", int(context["accepted_items"]))
    metric_row_2[0].metric("Open review", int(context["open_review_items"]))
    metric_row_2[1].metric("Proposals", int(context["pending_proposals"]))

    st.divider()
    st.caption("Ask")
    section = str(context.get("section") or "Setup")
    quick_ask_key = f"workspace_copilot_quick_ask_{section.lower()}"
    _workspace_copilot_apply_pending_widget_reset(quick_ask_key, state)
    if quick_ask_key not in state:
        state[quick_ask_key] = WORKSPACE_COPILOT_QUICK_ASK_PLACEHOLDER
    st.caption("Choose a suggestion to prefill the question box below.")
    st.selectbox(
        "Suggested questions",
        _workspace_copilot_quick_ask_options(section),
        key=quick_ask_key,
        format_func=_workspace_copilot_quick_ask_label,
        on_change=_workspace_copilot_apply_selected_prompt,
        args=(quick_ask_key,),
    )

    with st.form("workspace_copilot_chat_form", clear_on_submit=True):
        question = st.text_input("Ask about this Workspace step", key=WORKSPACE_COPILOT_CHAT_INPUT_KEY)
        submitted = st.form_submit_button("Send")
    if submitted and str(question or "").strip():
        submit_workspace_copilot_chat_question(question, state)
        _workspace_copilot_queue_widget_reset(quick_ask_key, state)
        st.rerun()

    response = state.get("workspace_copilot_chat_last_response") or {}
    if response:
        st.divider()
        st.caption("Answer")
        level = str(response.get("level") or "info").strip().lower() or "info"
        answer = str(response.get("answer") or "").strip()
        why = str(response.get("why") or "").strip()
        next_actions = [str(item).strip() for item in (response.get("next_actions") or []) if str(item).strip()]
        action_buttons = [item for item in (response.get("action_buttons") or []) if isinstance(item, dict)]

        if level == "error":
            st.error(answer)
        elif level == "warning":
            st.warning(answer)
        elif level == "success":
            st.success(answer)
        else:
            st.info(answer)

        if why:
            st.caption("Why")
            st.write(why)
        if next_actions:
            st.caption("Next actions")
            for item in next_actions:
                st.write(f"- {item}")

        if action_buttons:
            st.caption("Actions")
            action_columns = st.columns(len(action_buttons))
            for idx, action in enumerate(action_buttons):
                label = str(action.get("label") or "Run action").strip() or "Run action"
                action_key = str(action.get("action") or f"action_{idx}").strip() or f"action_{idx}"
                focus_sources = [str(item).strip() for item in (action.get("focus_sources") or []) if str(item).strip()]
                if action_columns[idx].button(label, key=f"workspace_copilot_action_{action_key}_{idx}", width="stretch"):
                    if _workspace_run_action(state, action_key, focus_sources=focus_sources, origin="Workspace Copilot"):
                        return
                    elif action_key == "apply_safe_proposals":
                        applied_count, applied_sources = _workspace_apply_safe_proposals(state)
                        if applied_count:
                            state["workspace_copilot_chat_last_response"] = _copilot_response(
                                level="success",
                                kind="proposal-apply",
                                answer=f"Applied {applied_count} safe proposal(s).",
                                why=f"Applied sources: {', '.join(applied_sources)}.",
                                next_actions=["Review remaining proposals or move into Output if decision state is now closed."],
                                action_buttons=[{"label": "Open Decisions", "action": "open_decisions"}],
                            )
                            state["last_action"] = {
                                "level": "success",
                                "message": f"Applied {applied_count} safe LLM proposal(s): {', '.join(applied_sources)}.",
                            }
                        else:
                            state["workspace_copilot_chat_last_response"] = _copilot_response(
                                level="warning",
                                kind="proposal-apply",
                                answer="No safe proposals were applied.",
                                why="The workspace state may have changed since the proposals were prepared.",
                                next_actions=["Regenerate proposals from Review if needed."],
                                action_buttons=[{"label": "Open Review", "action": "open_review"}],
                            )
                        st.rerun()

    proposals = list(state.get("llm_decision_proposals") or [])
    if proposals:
        st.divider()
        st.caption("Proposal actions")
        proposal_sources = [str(proposal.get("source") or "").strip() for proposal in proposals if str(proposal.get("source") or "").strip()]
        if proposal_sources:
            selected_source = st.selectbox(
                "Proposal source",
                proposal_sources,
                key="workspace_copilot_selected_proposal_source",
            )
            selected_proposal = next((proposal for proposal in proposals if str(proposal.get("source") or "").strip() == selected_source), None) or {}
            st.caption(str(selected_proposal.get("summary") or "LLM proposed a bounded follow-up decision for this row."))
            safe_reason = str(selected_proposal.get("safe_reason") or "").strip()
            if safe_reason:
                st.write(safe_reason)
            proposal_action_columns = st.columns(2)
            if proposal_action_columns[0].button("Apply selected", key="workspace_copilot_apply_selected_proposal", width="stretch"):
                from streamlit_ui.workspace_decision_views import _apply_llm_decision_proposal

                editor_state = state.setdefault("mapping_editor_state", {})
                if _apply_llm_decision_proposal(editor_state, selected_proposal):
                    state["mapping_editor_state"] = editor_state
                    state["llm_decision_proposals"] = [proposal for proposal in proposals if str(proposal.get("source") or "").strip() != selected_source]
                    state["last_action"] = {"level": "success", "message": f"Applied the LLM decision proposal for {selected_source}."}
                else:
                    state["last_action"] = {"level": "warning", "message": f"Could not apply the LLM proposal for {selected_source}."}
                st.rerun()
            if proposal_action_columns[1].button("Dismiss selected", key="workspace_copilot_dismiss_selected_proposal", width="stretch"):
                state["llm_decision_proposals"] = [proposal for proposal in proposals if str(proposal.get("source") or "").strip() != selected_source]
                state["last_action"] = {"level": "info", "message": f"Dismissed the cached LLM decision proposal for {selected_source}."}
                st.rerun()

    codegen_response = state.get("codegen_refinement_response") or state.get("codegen_response") or {}
    refinement_candidate = state.get("codegen_refinement_response") or {}
    if str(codegen_response.get("code") or "").strip() or str((response or {}).get("kind") or "") == "artifact-refinement":
        st.divider()
        st.caption("Artifact refinement")
        artifact_summary = _workspace_artifact_summary(state)
        if artifact_summary["has_artifact"]:
            st.caption(f"Current artifact: {artifact_summary['current_summary']}")
            if artifact_summary["warning_codes"]:
                st.caption(f"Warning codes: {', '.join(artifact_summary['warning_codes'])}")
        if artifact_summary["refinement_pending"]:
            st.info(
                f"Pending refinement candidate: {artifact_summary['refinement_reasoning_count']} reasoning note(s), {artifact_summary['refinement_warning_count']} warning(s)."
            )
        st.text_area("Instruction", key="workspace_copilot_refinement_instruction", placeholder="Refine the artifact for clarity, safety, or implementation style.")
        st.text_area("Edge cases", key="workspace_copilot_refinement_edge_cases", placeholder="Optional edge cases or constraints")
        st.text_area("Reference excerpt", key="workspace_copilot_refinement_reference", placeholder="Optional reference excerpt or implementation note")
        refine_disabled = not _workspace_has_reachable_llm(state) or not str(codegen_response.get("code") or "").strip()
        if st.button("Run refinement", key="workspace_copilot_run_refinement", width="stretch", disabled=refine_disabled):
            try:
                _workspace_execute_artifact_refinement(state)
                state["workspace_copilot_chat_last_response"] = _copilot_response(
                    level="success",
                    kind="artifact-refinement-candidate",
                    answer="Generated a refinement candidate.",
                    why="The bounded artifact refinement workflow completed successfully.",
                    next_actions=["Inspect the candidate below.", "Explicitly accept or discard it."],
                    action_buttons=[{"label": "Open Output", "action": "open_output"}],
                )
                st.rerun()
            except (ValueError, httpx.HTTPError) as error:
                state["workspace_copilot_chat_last_response"] = _copilot_response(
                    level="error",
                    kind="artifact-refinement-error",
                    answer="Artifact refinement failed.",
                    why=str(error),
                    next_actions=["Adjust the refinement instruction and retry."],
                )
                st.rerun()
        if refine_disabled:
            st.caption("LLM refinement is unavailable until a reachable runtime provider is configured and an artifact exists.")
        if refinement_candidate:
            st.caption("Refined candidate")
            st.code(str(refinement_candidate.get("code") or ""), language="sql" if str(refinement_candidate.get("language") or "").strip().lower() == "sql-dbt" else "python")
            refinement_reasoning = [str(item).strip() for item in (refinement_candidate.get("reasoning") or []) if str(item).strip()]
            if refinement_reasoning:
                st.caption("Refinement reasoning")
                for item in refinement_reasoning:
                    st.write(f"- {item}")
            refinement_warnings = refinement_candidate.get("warnings") or []
            if refinement_warnings:
                st.caption("Refinement warnings")
                for warning in refinement_warnings:
                    if isinstance(warning, dict):
                        code = str(warning.get("code") or "warning").strip() or "warning"
                        message = str(warning.get("message") or "").strip()
                        st.warning(f"{code}: {message}" if message else code)
                    else:
                        st.warning(str(warning))
            accept_col, discard_col = st.columns(2)
            if accept_col.button("Accept refined version", key="workspace_copilot_accept_refinement", width="stretch"):
                _workspace_accept_refinement(state)
            if discard_col.button("Discard refinement", key="workspace_copilot_discard_refinement", width="stretch"):
                _workspace_discard_refinement(state)

    history = list(state.get("workspace_copilot_chat_history") or [])
    if history:
        st.caption("Conversation")
        for turn in history[-4:]:
            st.write(f"You: {turn['question']}")
            st.write(f"Copilot: {turn['answer']}")
            if str(turn.get("why") or "").strip():
                st.caption(f"Why: {turn['why']}")


def workspace_copilot_sidebar_brief(session_state: dict | None = None) -> dict:
    """Return a concise briefing view for the current Workspace Copilot state."""

    state = st.session_state if session_state is None else session_state
    context = workspace_copilot_sidebar_context(state)
    last_action = state.get("last_action") or {}
    last_action_message = str(last_action.get("message") or "").strip() or None

    if context["active_area"] != "Workspace":
        now = f"Workspace is not the active area. The latest tracked section is {context['section']}."
    elif not context["has_upload"]:
        now = "Collect source and target upload context in Setup."
    elif not context["mapping_ready"]:
        now = "Generate mapping from Setup so Review can open with a real mapping surface."
    elif context["open_review_items"] > 0:
        now = f"Work the remaining {int(context['open_review_items'])} review item(s) in {context['section']}."
    elif context["pending_proposals"] > 0:
        now = f"Resolve {int(context['pending_proposals'])} pending proposal(s) before moving on."
    elif not context["output_ready"]:
        now = "Review is stable enough to move into Output for preview or code generation."
    else:
        now = "An output artifact already exists; inspect or refine it from Output."

    risks: list[str] = []
    next_actions: list[str] = []
    top_blocker: str | None = None
    primary_action: dict[str, object] | None = None

    if not context["has_upload"]:
        top_blocker = "No dataset pair is loaded yet, so the workspace flow cannot leave Setup."
        primary_action = {"label": "Open Setup", "action": "open_setup"}
    elif not context["mapping_ready"]:
        top_blocker = "Upload context exists, but mapping has not been generated yet."
        primary_action = {"label": "Open Setup", "action": "open_setup"}
    elif context["open_review_items"] > 0:
        priority_rows = _workspace_review_priority_rows(state, limit=1)
        if priority_rows:
            focus_source = str(priority_rows[0].get("source") or "").strip()
            top_blocker = _workspace_review_row_detail(priority_rows[0])
            primary_action = {
                "label": "Focus top blocker",
                "action": "open_review_focus",
                "focus_sources": [focus_source] if focus_source else [],
            }
        else:
            editor_state = state.get("mapping_editor_state") or {}
            unresolved_items = [
                (source, value)
                for source, value in sorted(editor_state.items())
                if isinstance(value, dict) and str(value.get("status") or "needs_review").strip().lower() != "accepted"
            ]
            if unresolved_items:
                source, value = unresolved_items[0]
                target = str(value.get("target") or "unmapped").strip() or "unmapped"
                status = str(value.get("status") or "needs_review").strip().replace("_", " ") or "needs review"
                top_blocker = f"{source} -> {target} is {status}."
                primary_action = {
                    "label": "Focus top blocker",
                    "action": "open_review_focus",
                    "focus_sources": [str(source)],
                }
            else:
                top_blocker = f"There are {int(context['open_review_items'])} unresolved review item(s) blocking stable output."
                primary_action = {"label": "Open Review", "action": "open_review"}
    elif context["pending_proposals"] > 0:
        top_blocker = f"There are {int(context['pending_proposals'])} pending proposal(s) still waiting for a decision."
        primary_action = {"label": "Open Decisions", "action": "open_decisions"}
    else:
        primary_action = {"label": "Open Output", "action": "open_output"}

    if context["active_area"] != "Workspace":
        risks.append(f"The main surface is currently {context['active_area']}, so workspace edits are out of view.")
        next_actions.append("Return to Workspace when you want to act on mapping state.")
    if not context["has_upload"]:
        risks.append("No dataset pair is loaded yet, so Review, Decisions, and Output stay blocked.")
        next_actions.append("Upload and profile the active dataset pair in Setup.")
    elif not context["mapping_ready"]:
        risks.append("Upload exists, but there is still no mapping result to review.")
        next_actions.append("Run mapping generation from Setup.")
    if context["open_review_items"] > 0:
        risks.append(f"There are {int(context['open_review_items'])} open review item(s) still unresolved.")
        next_actions.append("Close or accept the remaining review items.")
    if context["pending_proposals"] > 0:
        risks.append(f"There are {int(context['pending_proposals'])} pending proposal(s) that can drift decisions.")
        next_actions.append("Resolve pending proposals before final output steps.")
    if context["mapping_ready"] and context["open_review_items"] == 0 and context["pending_proposals"] == 0 and not context["output_ready"]:
        next_actions.append("Open Output and generate a preview or code artifact.")
    if context["output_ready"]:
        next_actions.append("Inspect the current artifact and refine it only if needed.")

    if not risks:
        risks.append("No major blockers are visible in the current workspace snapshot.")

    deduped_actions: list[str] = []
    for item in next_actions:
        if item not in deduped_actions:
            deduped_actions.append(item)

    return {
        "context": context,
        "now": now,
        "top_blocker": top_blocker,
        "primary_action": dict(primary_action or {}),
        "risks": risks,
        "next_actions": deduped_actions,
        "latest_answer": context["latest_answer"],
        "last_action_message": last_action_message,
    }


def render_workspace_copilot_sidebar_brief(session_state: dict | None = None) -> None:
    """Render a concise Workspace Copilot briefing in the sidebar."""

    brief = workspace_copilot_sidebar_brief(st.session_state if session_state is None else session_state)
    context = brief["context"]

    st.subheader("WS Brief")
    st.caption("Concise readout of what matters now in Workspace.")
    st.caption(f"Area: {context['active_area']} | Section: {context['section']}")

    st.caption("Now")
    st.info(brief["now"])

    top_blocker = str(brief.get("top_blocker") or "").strip()
    if top_blocker:
        st.caption("Top blocker")
        st.warning(top_blocker)

    primary_action = brief.get("primary_action") if isinstance(brief.get("primary_action"), dict) else {}
    action_label = str((primary_action or {}).get("label") or "").strip()
    action_key = str((primary_action or {}).get("action") or "").strip()
    focus_sources = [str(item).strip() for item in ((primary_action or {}).get("focus_sources") or []) if str(item).strip()]
    if action_label and action_key:
        st.caption("Primary action")
        if st.button(action_label, key=f"workspace_brief_action_{action_key}", width="stretch"):
            _workspace_run_action(st.session_state if session_state is None else session_state, action_key, focus_sources=focus_sources, origin="WS Brief")

    st.caption("Risks")
    for item in brief["risks"]:
        st.write(f"- {item}")

    st.caption("Next actions")
    for item in brief["next_actions"]:
        st.write(f"- {item}")

    if brief["last_action_message"]:
        st.caption("Latest system action")
        st.write(brief["last_action_message"])

    if brief["latest_answer"]:
        st.caption("Latest copilot answer")
        st.write(brief["latest_answer"])


def load_english_help_markdown(help_path: Path | None = None) -> str:
    """Load the English sidebar help markdown from the repository help file."""

    path = help_path or ENGLISH_HELP_PATH
    return path.read_text(encoding="utf-8")


def available_reference_documents(
    reference_dir: Path | None = None,
    extra_documents: tuple[Path, ...] | None = None,
) -> list[Path]:
    """Return available markdown reference documents for the sidebar reference view."""

    path = reference_dir or REFERENCE_DOCS_PATH
    documents: list[Path] = []
    if path.exists():
        documents.extend(
            [candidate for candidate in path.iterdir() if candidate.is_file() and candidate.suffix.lower() == ".md"]
        )

    configured_extra_documents = REFERENCE_EXTRA_DOCS if extra_documents is None else extra_documents
    for candidate in configured_extra_documents:
        if candidate.exists() and candidate.is_file() and candidate.suffix.lower() == ".md":
            documents.append(candidate)

    unique_documents: dict[str, Path] = {}
    for candidate in documents:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        unique_documents[key] = candidate

    return sorted(unique_documents.values(), key=lambda candidate: candidate.name.lower())


def load_reference_markdown(reference_path: Path) -> str:
    """Load a selected sidebar reference markdown file."""

    return reference_path.read_text(encoding="utf-8")


def reference_markdown_blocks(markdown_text: str) -> list[tuple[str, str]]:
    """Split a markdown document into normal markdown and mermaid diagram blocks."""

    blocks: list[tuple[str, str]] = []
    last_index = 0
    for match in MERMAID_FENCE_PATTERN.finditer(markdown_text):
        preceding_markdown = markdown_text[last_index:match.start()].strip()
        if preceding_markdown:
            blocks.append(("markdown", preceding_markdown))

        mermaid_source = match.group(1).strip()
        if mermaid_source:
            blocks.append(("mermaid", mermaid_source))
        last_index = match.end()

    trailing_markdown = markdown_text[last_index:].strip()
    if trailing_markdown:
        blocks.append(("markdown", trailing_markdown))
    return blocks


@lru_cache(maxsize=32)
def mermaid_svg_markup(diagram_source: str, kroki_base_url: str | None = None) -> str | None:
    """Render Mermaid source to SVG markup using a server-side Kroki endpoint."""

    base_url = (kroki_base_url or REFERENCE_KROKI_BASE_URL).rstrip("/")
    try:
        response = httpx.post(
            f"{base_url}/mermaid/svg",
            content=diagram_source.encode("utf-8"),
            headers={"Content-Type": "text/plain", "Accept": "image/svg+xml"},
            timeout=15.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    svg_markup = response.text.strip()
    if "<svg" not in svg_markup:
        return None
    return svg_markup


def reference_document_label(reference_path: Path) -> str:
    """Format a reference filename into a readable sidebar label."""

    base_label = reference_path.stem.replace("_", " ").replace("-", " ").title()
    try:
        relative_parts = reference_path.resolve().relative_to(APP_ROOT).parts
    except ValueError:
        relative_parts = ()

    if len(relative_parts) >= 2 and relative_parts[0] == "docs":
        section = relative_parts[1]
        if section == "pilot":
            return f"Pilot: {base_label}"
        if section == "presentation":
            return f"Presentation: {base_label}"

    return base_label


def reference_document_display_path(reference_path: Path) -> str:
    """Return a readable repository-relative path for a reference document."""

    try:
        return reference_path.resolve().relative_to(APP_ROOT).as_posix()
    except ValueError:
        return reference_path.as_posix()


def render_reference_markdown(
    markdown_text: str,
    mermaid_renderer=mermaid_svg_markup,
) -> None:
    """Render a reference markdown document, converting Mermaid blocks to static SVG when possible."""

    for block_type, block_content in reference_markdown_blocks(markdown_text):
        if block_type == "markdown":
            st.markdown(block_content)
            continue

        svg_markup = mermaid_renderer(block_content)
        if svg_markup is None:
            st.warning("Mermaid rendering is temporarily unavailable, so the raw diagram source is shown instead.")
            st.markdown(f"```mermaid\n{block_content}\n```")
            continue
        st.markdown(svg_markup, unsafe_allow_html=True)


def render_sidebar_help() -> None:
    """Render the English help reference in the sidebar."""

    st.subheader("Help")
    st.caption("English reference guide for the Semantra UI.")
    st.markdown(load_english_help_markdown())


def render_sidebar_reference() -> None:
    """Render detailed reference documents in the sidebar."""

    st.subheader("Reference")
    st.caption("Detailed technical references for Semantra behavior, scoring, and workflows.")

    documents = available_reference_documents()
    if not documents:
        st.info("No reference documents are available.")
        return

    document_paths = [reference_document_display_path(document) for document in documents]
    documents_by_path = {reference_document_display_path(document): document for document in documents}

    selected_name = str(st.session_state.get("sidebar_reference_file") or document_paths[0])
    if selected_name not in document_paths:
        legacy_match = next((path for path, document in documents_by_path.items() if document.name == selected_name), None)
        selected_name = legacy_match or document_paths[0]

    selected_name = st.selectbox(
        "Reference file",
        document_paths,
        index=document_paths.index(selected_name),
        key="sidebar_reference_file",
        format_func=lambda name: reference_document_label(documents_by_path[name]),
    )
    selected_document = documents_by_path[selected_name]
    st.caption(f"Showing {selected_name}")
    render_reference_markdown(load_reference_markdown(selected_document))


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
    tts_status = str(config.get("tts_status", "configured")).strip().lower() or "configured"
    tts_status_detail = str(config.get("tts_status_detail", "")).strip()
    tts_timeout = config.get("tts_timeout_seconds", "?")
    tts_endpoint = str(config.get("lmstudio_tts_base_url", "")).strip()
    tts_model = str(config.get("lmstudio_orpheus_model", "")).strip() or "n/a"
    tts_voice = str(config.get("lmstudio_orpheus_voice", "")).strip() or "n/a"
    tts_display_provider = "lmstudio" if tts_provider.lower().startswith("lmstudio") else tts_provider

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
    elif tts_status == "reachable":
        st.success(f"TTS reachable: {tts_display_provider} / {tts_model}")
    elif tts_status == "misconfigured":
        st.error(f"TTS reachable, but configured model is unavailable: {tts_display_provider} / {tts_model}")
    elif tts_status == "unreachable":
        st.error(f"TTS configured but unreachable: {tts_display_provider} / {tts_model}")
    elif tts_provider.lower().startswith("lmstudio"):
        st.info(f"TTS configured: {tts_display_provider} / {tts_model}")
    else:
        st.info(f"TTS configured: {tts_provider}")
    if tts_status_detail:
        st.caption(tts_status_detail)
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