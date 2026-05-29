"""Reusable Streamlit rendering helpers shared across product surfaces."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import httpx
import streamlit as st

from streamlit_ui.api import admin_token_required, backend_is_reachable, request_mapping_analysis_summary


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

WORKSPACE_COPILOT_CHAT_QUICK_ASKS = {
    "default": (
        "What is blocking Workspace now?",
        "What does Review do?",
    ),
    "mapping_ready": (
        "Summarize current mapping state",
        "What should I do next?",
    ),
}

APP_ROOT = Path(__file__).resolve().parents[1]
ENGLISH_HELP_PATH = APP_ROOT / "help.en.md"
REFERENCE_DOCS_PATH = APP_ROOT / "docs" / "reference"
REFERENCE_EXTRA_DOCS = (
    APP_ROOT / "docs" / "presentation" / "Conceptualization.md",
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


def workspace_copilot_chat_response(
    question: str,
    session_state: dict | None = None,
    *,
    request_mapping_analysis_summary_func=request_mapping_analysis_summary,
) -> dict:
    """Return one bounded chat response using workspace/app context only."""

    state = st.session_state if session_state is None else session_state
    context = workspace_copilot_sidebar_context(state)
    brief = workspace_copilot_sidebar_brief(state)
    normalized = str(question or "").strip().lower()
    if not normalized:
        return {
            "level": "info",
            "answer": "Ask about Workspace sections, runtime surfaces, or the current mapping state.",
            "kind": "empty",
        }

    for topic, answer in WORKSPACE_COPILOT_GUIDE.items():
        if topic in normalized:
            return {
                "level": "info",
                "answer": answer,
                "kind": "guide",
            }

    if any(token in normalized for token in ("block", "blocked", "next", "what now", "what should", "risk", "stuck")):
        risk_text = brief["risks"][0] if brief["risks"] else "No major blockers are visible in the current workspace snapshot."
        next_text = brief["next_actions"][0] if brief["next_actions"] else "No immediate action is required."
        return {
            "level": "info",
            "answer": f"{brief['now']} Risk: {risk_text} Next: {next_text}",
            "kind": "brief",
        }

    asks_for_mapping_state = any(
        token in normalized
        for token in ("mapping", "review", "decision", "proposal", "source", "target", "file", "dataset", "summary", "state")
    )
    if asks_for_mapping_state:
        if not context["mapping_ready"]:
            return {
                "level": "warning",
                "answer": "There is no active mapping result yet. Upload and profile the dataset pair in Setup, then generate mapping results before asking about mapping state.",
                "kind": "mapping-blocked",
            }

        summary = state.get("mapping_analysis_summary")
        if summary is None:
            try:
                summary = request_mapping_analysis_summary_func()
                state["mapping_analysis_summary"] = summary
            except Exception as error:
                return {
                    "level": "warning",
                    "answer": (
                        "Workspace has mapping results, but the analysis summary is not available yet. "
                        f"Reason: {error}"
                    ),
                    "kind": "mapping-summary-error",
                }

        overall = (summary or {}).get("overall_mapping_health") or {}
        accepted_count = int(overall.get("accepted_count") or context["accepted_items"])
        needs_review_count = int(overall.get("needs_review_count") or context["open_review_items"])
        unmatched_count = int(overall.get("unmatched_count") or 0)
        summary_text = str(overall.get("summary") or "").strip()
        if not summary_text:
            summary_text = (
                f"Current mapping state: {accepted_count} accepted, {needs_review_count} needs review, "
                f"{unmatched_count} unmatched."
            )
        return {
            "level": "success" if needs_review_count == 0 and unmatched_count == 0 else "info",
            "answer": (
                f"{summary_text} Target context: {context['target_intent']} / {context['projection_label']}."
            ),
            "kind": "mapping-summary",
        }

    return {
        "level": "info",
        "answer": (
            "I can help with Workspace navigation, section purpose, runtime surfaces, and the current mapping state. "
            "Ask things like 'What does Review do?', 'What is blocking Workspace now?', or 'Summarize current mapping state'."
        ),
        "kind": "fallback",
    }


def submit_workspace_copilot_chat_question(
    question: str,
    session_state: dict | None = None,
    *,
    request_mapping_analysis_summary_func=request_mapping_analysis_summary,
) -> dict:
    """Resolve one bounded copilot question and append it to sidebar chat history."""

    state = st.session_state if session_state is None else session_state
    response = workspace_copilot_chat_response(
        question,
        state,
        request_mapping_analysis_summary_func=request_mapping_analysis_summary_func,
    )
    history = list(state.get("workspace_copilot_chat_history") or [])
    history.append(
        {
            "question": str(question or "").strip(),
            "answer": str(response.get("answer") or "").strip(),
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
    """Render a sidebar-friendly, read-only view of the current Workspace Copilot context."""

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

    if context["latest_answer"]:
        st.caption("Latest answer")
        st.write(context["latest_answer"])

    st.divider()
    st.caption("Ask WS Copilot")
    quick_asks = WORKSPACE_COPILOT_CHAT_QUICK_ASKS["mapping_ready"] if context["mapping_ready"] else WORKSPACE_COPILOT_CHAT_QUICK_ASKS["default"]
    quick_columns = st.columns(2)
    for idx, prompt in enumerate(quick_asks):
        if quick_columns[idx].button(prompt, key=f"workspace_copilot_quick_ask_{idx}"):
            submit_workspace_copilot_chat_question(prompt, state)

    with st.form("workspace_copilot_chat_form", clear_on_submit=True):
        question = st.text_input("Ask about app flow or current mapping state")
        submitted = st.form_submit_button("Send")
    if submitted and str(question or "").strip():
        submit_workspace_copilot_chat_question(question, state)

    history = list(state.get("workspace_copilot_chat_history") or [])
    if history:
        st.caption("Conversation")
        for turn in history[-4:]:
            st.write(f"You: {turn['question']}")
            st.write(f"Copilot: {turn['answer']}")


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

    return reference_path.stem.replace("_", " ").replace("-", " ").title()


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