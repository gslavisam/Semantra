"""Bounded workspace-problem guidance for the WS Copilot sidebar."""

from __future__ import annotations

import json
import re

from app.core.config import settings
from app.models.mapping import (
    WorkspaceCopilotProblemGuidanceGenerationMetadata,
    WorkspaceCopilotProblemStatementRequest,
    WorkspaceCopilotProblemStatementResponse,
)
from app.services.llm_service import LLMProvider, request_bounded_llm_json


PROBLEM_STATEMENT_FIELDS = [
    "Goal",
    "Current stage in app",
    "Available files or metadata",
    "Expected output or artifact",
    "Constraints or business rules",
]

PROBLEM_STATEMENT_TEMPLATE = (
    "Goal: <what outcome you need>\n"
    "Current stage in app: <Setup | Review | Decisions | Output | Catalog | Governance | Benchmarks | System>\n"
    "Available files or metadata: <source file, target file, descriptions, sample values, draft session, none>\n"
    "Expected output or artifact: <mapping review, accepted decisions, transformation design, preview, codegen, reuse search, benchmark, runtime help>\n"
    "Constraints or business rules: <required transformations, quality checks, missing context, downstream rules>"
)

CAPABILITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Setup": ("upload", "source", "target", "schema", "metadata", "description", "profile", "interpret", "file"),
    "Review": ("review", "mapping", "match", "column", "field", "confidence", "queue"),
    "Decisions": ("decision", "accept", "reject", "proposal", "safe to apply", "close review"),
    "Output": ("output", "preview", "artifact", "codegen", "pandas", "pyspark", "dbt", "transform", "transformation", "target grain", "defaults"),
    "Catalog": ("catalog", "reuse", "reusable", "mapping set", "version", "compare"),
    "Governance": ("governance", "canonical", "knowledge", "glossary", "overlay", "steward"),
    "Benchmarks": ("benchmark", "drift", "quality", "evaluation", "score"),
    "System": ("runtime", "llm", "model", "connection", "status", "endpoint", "debug", "observability"),
}

CAPABILITY_DESCRIPTIONS: dict[str, str] = {
    "Setup": "upload source and target files, enrich them with companion metadata, and generate the initial mapping context",
    "Review": "inspect unresolved mapping rows, confidence signals, and queue-level risk before stabilizing decisions",
    "Decisions": "apply or reject proposals and close the decision surface before final output work",
    "Output": "define Transformation Design, preview the mapped result, and generate governed Pandas, PySpark, or dbt artifacts",
    "Catalog": "search reusable mapping sets and compare reuse fit",
    "Governance": "manage canonical and knowledge registries, overlays, and glossary promotion",
    "Benchmarks": "measure quality and drift using benchmark datasets",
    "System": "inspect runtime reachability, model status, and debug state",
}


def build_workspace_problem_guidance(
    request: WorkspaceCopilotProblemStatementRequest,
    provider: LLMProvider | None = None,
) -> WorkspaceCopilotProblemStatementResponse:
    """Build bounded action guidance for a free-form workspace problem statement."""

    fallback = _build_fallback_problem_guidance(request)
    if provider is None:
        return fallback

    prompt = build_workspace_problem_guidance_prompt(request, fallback)
    response = request_bounded_llm_json(provider, prompt, "workspace_problem_guidance")
    if response is None:
        return fallback

    _raw_response, parsed = response
    normalized = _normalize_problem_guidance(parsed, fallback)
    if normalized is None:
        return fallback
    return normalized


def build_workspace_problem_guidance_prompt(
    request: WorkspaceCopilotProblemStatementRequest,
    fallback: WorkspaceCopilotProblemStatementResponse,
) -> str:
    """Build the bounded prompt used to convert one problem statement into product-aware action guidance."""

    evidence = {
        "problem_statement": request.problem_statement,
        "workspace": request.workspace.model_dump(mode="json"),
        "capability_snapshot": request.capability_snapshot,
        "capability_descriptions": CAPABILITY_DESCRIPTIONS,
        "fallback_guidance": fallback.model_dump(mode="json", exclude={"generation_metadata"}),
        "required_input_format_fields": PROBLEM_STATEMENT_FIELDS,
        "prompt_template": PROBLEM_STATEMENT_TEMPLATE,
    }
    return (
        "You are a bounded Workspace Copilot planner for Semantra. "
        "First decide whether the user's problem statement is in scope for the application's current capabilities. "
        "Stay grounded in the provided workspace state, capability snapshot, and product surfaces only.\n\n"
        "Return JSON only. No markdown. No code fences. No extra prose.\n"
        "Do not invent product features. Do not promise automation the app does not have.\n"
        "If the request is only partly aligned, explain how to restate it using the provided input format.\n"
        "Return exactly these top-level fields: title, disposition, normalized_problem, scope_reason, answer, capability_hits, recommended_sections, recommended_steps, prompt_template, input_format_fields, generation_metadata.\n"
        "recommended_sections must only contain values from Setup, Review, Decisions, Output, Catalog, Governance, Benchmarks, System.\n"
        "recommended_steps must be concrete actions the user can take inside Semantra.\n\n"
        f"PAYLOAD:\n{json.dumps(evidence, ensure_ascii=True)}"
    )


def _build_fallback_problem_guidance(
    request: WorkspaceCopilotProblemStatementRequest,
) -> WorkspaceCopilotProblemStatementResponse:
    problem_statement = str(request.problem_statement or "").strip()
    normalized_problem = " ".join(problem_statement.split())
    lowered = normalized_problem.lower()
    snapshot = request.capability_snapshot or {}
    has_upload = bool(snapshot.get("has_upload"))
    mapping_ready = bool(snapshot.get("mapping_ready"))
    pending_proposals = int(snapshot.get("pending_proposals") or 0)
    open_review_items = int(snapshot.get("open_review_items") or 0)
    transformation_state = str(snapshot.get("transformation_state") or "").strip().lower()
    transformation_title = str(snapshot.get("transformation_title") or "").strip()
    transformation_proposal_pending = bool(snapshot.get("transformation_proposal_pending"))
    artifact_ready = bool(snapshot.get("artifact_ready"))
    active_draft_session_id = int(snapshot.get("active_draft_session_id") or 0)
    active_draft_session_name = str(snapshot.get("active_draft_session_name") or "").strip()
    active_draft_section = str(snapshot.get("active_draft_section") or "").strip()
    active_section = str(snapshot.get("section") or "").strip() or "Setup"

    capability_hits = _detect_capability_hits(lowered)
    app_domain_terms = (
        "workspace",
        "mapping",
        "source",
        "target",
        "review",
        "decision",
        "output",
        "catalog",
        "governance",
        "benchmark",
        "runtime",
        "metadata",
        "transform",
        "transformation",
        "artifact",
    )
    app_domain_match = any(term in lowered for term in app_domain_terms)

    if not capability_hits and not app_domain_match:
        return WorkspaceCopilotProblemStatementResponse(
            title="Restate the problem in Semantra terms",
            disposition="out_of_scope",
            normalized_problem=normalized_problem,
            scope_reason=(
                "The request does not clearly map to Semantra's current surfaces: Setup, Review, Decisions, Output, Catalog, Governance, Benchmarks, or System."
            ),
            answer="Rewrite the problem as an in-app task so Copilot can turn it into concrete steps.",
            recommended_steps=[
                "Use the suggested format below and describe the goal, current stage, available inputs, expected artifact, and constraints.",
                "Reference an app surface such as upload/setup, review, decisions, output transformation design, catalog reuse, governance, benchmarks, or runtime.",
            ],
            prompt_template=PROBLEM_STATEMENT_TEMPLATE,
            input_format_fields=list(PROBLEM_STATEMENT_FIELDS),
            generation_metadata=WorkspaceCopilotProblemGuidanceGenerationMetadata(
                used_llm=False,
                fallback_used=True,
            ),
        )

    if not capability_hits and app_domain_match:
        capability_hits = [active_section]

    recommended_sections = _recommended_sections(capability_hits, has_upload=has_upload, mapping_ready=mapping_ready)
    recommended_steps = _recommended_steps(
        recommended_sections,
        has_upload=has_upload,
        mapping_ready=mapping_ready,
        open_review_items=open_review_items,
        pending_proposals=pending_proposals,
        transformation_state=transformation_state,
        transformation_title=transformation_title,
        transformation_proposal_pending=transformation_proposal_pending,
        artifact_ready=artifact_ready,
        active_draft_session_id=active_draft_session_id,
        active_draft_session_name=active_draft_session_name,
        active_draft_section=active_draft_section,
    )
    disposition = "in_scope" if capability_hits else "partial"
    if disposition == "in_scope" and not recommended_steps:
        disposition = "partial"

    top_sections = ", ".join(recommended_sections[:2]) if recommended_sections else active_section
    answer = f"This problem is addressable through Semantra's {top_sections} flow."
    if active_draft_session_id:
        answer = (
            f"This problem is in scope and should continue from the active draft session #{active_draft_session_id}"
            + (f" ({active_draft_session_name})" if active_draft_session_name else "")
            + "."
        )
    elif recommended_sections[:1] == ["Setup"] and not has_upload:
        answer = "This problem starts in Setup because the workspace still needs an active source/target context."
    elif "Output" in recommended_sections and transformation_state in {"invalid", "incomplete"}:
        answer = "This problem is in scope, but Output depends on completing the current Transformation Design before treating the artifact as stable."
    elif "Output" in recommended_sections and transformation_proposal_pending:
        answer = "This problem is in scope, but Output still has a pending Transformation Design proposal that should be reviewed before finalization."

    capability_notes = [CAPABILITY_DESCRIPTIONS[section] for section in recommended_sections[:2] if section in CAPABILITY_DESCRIPTIONS]
    scope_reason = (
        f"Matched capabilities: {', '.join(capability_hits)}. "
        + (capability_notes[0].capitalize() + "." if capability_notes else "")
    ).strip()
    if active_draft_session_id:
        scope_reason += (
            f" Active draft session: #{active_draft_session_id}"
            + (f" / {active_draft_session_name}" if active_draft_session_name else "")
            + (f" / {active_draft_section}" if active_draft_section else "")
            + "."
        )
    if transformation_proposal_pending:
        scope_reason += " A pending Transformation Design proposal is already cached in the workspace."

    return WorkspaceCopilotProblemStatementResponse(
        title="Workspace problem guidance",
        disposition=disposition,
        normalized_problem=normalized_problem,
        scope_reason=scope_reason,
        answer=answer,
        capability_hits=capability_hits,
        recommended_sections=recommended_sections,
        recommended_steps=recommended_steps,
        prompt_template=PROBLEM_STATEMENT_TEMPLATE,
        input_format_fields=list(PROBLEM_STATEMENT_FIELDS),
        generation_metadata=WorkspaceCopilotProblemGuidanceGenerationMetadata(
            used_llm=False,
            fallback_used=True,
        ),
    )


def _detect_capability_hits(lowered_problem: str) -> list[str]:
    token_set = set(re.findall(r"[a-z0-9_]+", lowered_problem))
    hits: list[str] = []
    for section, keywords in CAPABILITY_KEYWORDS.items():
        if any(
            (keyword in lowered_problem if " " in keyword else keyword in token_set)
            for keyword in keywords
        ):
            hits.append(section)
    return hits


def _recommended_sections(capability_hits: list[str], *, has_upload: bool, mapping_ready: bool) -> list[str]:
    ordered_hits = list(dict.fromkeys(capability_hits))
    if not has_upload and any(section in ordered_hits for section in ("Review", "Decisions", "Output")):
        ordered_hits.insert(0, "Setup")
    elif has_upload and not mapping_ready and any(section in ordered_hits for section in ("Review", "Decisions", "Output")):
        ordered_hits.insert(0, "Setup")
    preferred_order = ["Setup", "Review", "Decisions", "Output", "Catalog", "Governance", "Benchmarks", "System"]
    return [section for section in preferred_order if section in ordered_hits][:4]


def _recommended_steps(
    recommended_sections: list[str],
    *,
    has_upload: bool,
    mapping_ready: bool,
    open_review_items: int,
    pending_proposals: int,
    transformation_state: str,
    transformation_title: str,
    transformation_proposal_pending: bool,
    artifact_ready: bool,
    active_draft_session_id: int,
    active_draft_session_name: str,
    active_draft_section: str,
) -> list[str]:
    steps: list[str] = []
    if active_draft_session_id:
        steps.append(
            f"Resume from the active draft session #{active_draft_session_id}"
            + (f" ({active_draft_session_name})" if active_draft_session_name else "")
            + (f" and continue in {active_draft_section}." if active_draft_section else ".")
        )
    for section in recommended_sections:
        if section == "Setup":
            if not has_upload:
                steps.append("Open Setup, upload the source and target files, then add companion descriptions or schema metadata if the field names are weak or technical.")
            elif not mapping_ready:
                steps.append("Stay in Setup and run mapping generation after the upload context is confirmed.")
        elif section == "Review":
            if open_review_items:
                steps.append(f"Open Review and close the remaining {open_review_items} open review item(s) before moving on.")
            else:
                steps.append("Open Review and work the low-confidence, unmatched, or transformation-heavy rows before moving on.")
        elif section == "Decisions":
            if pending_proposals:
                steps.append(f"Open Decisions and resolve the remaining {pending_proposals} pending proposal(s) before treating the mapping state as stable.")
            else:
                steps.append("Use Decisions to accept or reject the remaining proposals and lock the mapping surface before Output.")
        elif section == "Output":
            if transformation_proposal_pending:
                steps.append("In Output, review the pending Transformation Design proposal and explicitly apply or discard it before treating the output as stable.")
            if transformation_state in {"invalid", "incomplete"}:
                steps.append("In Output, complete Transformation Design first: define target grain, add field rules or defaults, then generate preview or code.")
            else:
                steps.append("In Output, describe the Transformation Design in business terms, then generate preview or the governed code artifact you need.")
            if artifact_ready:
                steps.append("Inspect the existing preview or generated artifact before regenerating, so the next prompt can target a concrete gap instead of starting over.")
            elif transformation_title:
                steps.append(f"Use the current Transformation Design status as the next checkpoint: {transformation_title}.")
        elif section == "Catalog":
            steps.append("Open Catalog to search reusable mapping sets and inspect reuse-fit before rebuilding the same integration manually.")
        elif section == "Governance":
            steps.append("Open Governance if the problem depends on canonical concepts, glossary coverage, or knowledge overlay stewardship.")
        elif section == "Benchmarks":
            steps.append("Open Benchmarks to validate mapping quality or detect drift on benchmark datasets.")
        elif section == "System":
            steps.append("Open System to verify runtime reachability, model availability, or debug status before relying on LLM-backed steps.")
    return steps[:6]


def _normalize_problem_guidance(
    parsed: dict,
    fallback: WorkspaceCopilotProblemStatementResponse,
) -> WorkspaceCopilotProblemStatementResponse | None:
    disposition = str(parsed.get("disposition") or fallback.disposition).strip().lower() or fallback.disposition
    if disposition not in {"in_scope", "partial", "out_of_scope"}:
        disposition = fallback.disposition

    capability_hits = _normalize_named_list(parsed.get("capability_hits"), fallback.capability_hits)
    recommended_sections = [
        section
        for section in _normalize_named_list(parsed.get("recommended_sections"), fallback.recommended_sections)
        if section in CAPABILITY_DESCRIPTIONS
    ]
    input_format_fields = _normalize_named_list(parsed.get("input_format_fields"), fallback.input_format_fields)
    recommended_steps = _normalize_named_list(parsed.get("recommended_steps"), fallback.recommended_steps)
    prompt_template = str(parsed.get("prompt_template") or fallback.prompt_template).strip() or fallback.prompt_template

    try:
        return WorkspaceCopilotProblemStatementResponse(
            title=str(parsed.get("title") or fallback.title).strip() or fallback.title,
            disposition=disposition,
            normalized_problem=str(parsed.get("normalized_problem") or fallback.normalized_problem).strip() or fallback.normalized_problem,
            scope_reason=str(parsed.get("scope_reason") or fallback.scope_reason).strip() or fallback.scope_reason,
            answer=str(parsed.get("answer") or fallback.answer).strip() or fallback.answer,
            capability_hits=capability_hits or fallback.capability_hits,
            recommended_sections=recommended_sections or fallback.recommended_sections,
            recommended_steps=recommended_steps or fallback.recommended_steps,
            prompt_template=prompt_template,
            input_format_fields=input_format_fields or fallback.input_format_fields,
            generation_metadata=WorkspaceCopilotProblemGuidanceGenerationMetadata(
                used_llm=True,
                fallback_used=False,
                llm_provider=settings.llm_provider,
                llm_model=settings.llm_model,
            ),
        )
    except Exception:
        return None


def _normalize_named_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            return normalized[:6]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback[:6])