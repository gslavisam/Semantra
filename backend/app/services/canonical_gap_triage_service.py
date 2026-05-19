"""Queue-level canonical-gap triage summaries and risk guidance generation."""

from __future__ import annotations

import json

from app.core.config import settings
from app.models.mapping import (
    CanonicalGapSuggestion,
    CanonicalGapTriageGenerationMetadata,
    CanonicalGapTriageGroup,
    CanonicalGapTriageSummaryRequest,
    CanonicalGapTriageSummaryResponse,
)
from app.services.llm_service import LLMProvider, request_llm_json


def build_canonical_gap_triage_summary(
    request: CanonicalGapTriageSummaryRequest,
    provider: LLMProvider | None = None,
) -> CanonicalGapTriageSummaryResponse:
    """Build queue-level canonical-gap triage guidance with deterministic fallback and optional LLM summarization."""

    fallback = _build_fallback_summary(request)
    if provider is None:
        return fallback

    prompt = build_canonical_gap_triage_prompt(request, fallback)
    response = request_llm_json(
        provider,
        prompt,
        settings.llm_timeout_seconds,
        settings.llm_max_retries,
        "canonical_gap_triage",
    )
    if response is None:
        return fallback

    _raw_response, parsed = response
    normalized = _normalize_summary(parsed, fallback)
    if normalized is None:
        return fallback
    return normalized


def build_canonical_gap_triage_prompt(
    request: CanonicalGapTriageSummaryRequest,
    fallback: CanonicalGapTriageSummaryResponse,
) -> str:
    """Build the bounded prompt used to summarize repeated canonical-gap queue patterns."""

    evidence = {
        "candidates": [item.model_dump(mode="json") for item in request.candidates[:20]],
        "suggestions": {
            key: value.model_dump(mode="json") for key, value in list((request.suggestions or {}).items())[:20]
        },
        "proposal_states": dict(request.proposal_states or {}),
        "fallback_summary": fallback.model_dump(mode="json", exclude={"generation_metadata"}),
    }
    return (
        "You are triaging a canonical-gap review queue for human stewardship. "
        "Stay strictly grounded in the provided candidates, cached suggestion payloads, and proposal states.\n\n"
        "Return JSON only. No markdown. No code fences. No extra prose.\n"
        "Do not approve, reject, or invent canonical concepts. Only summarize repeated queue patterns, risks, and next actions.\n"
        "Return exactly these top-level fields: title, summary, groups, risks, next_actions, generation_metadata.\n\n"
        f"PAYLOAD:\n{json.dumps(evidence, ensure_ascii=True)}"
    )


def _build_fallback_summary(request: CanonicalGapTriageSummaryRequest) -> CanonicalGapTriageSummaryResponse:
    groups = _build_groups(request)
    candidate_count = len(request.candidates or [])
    approve_ready = sum(1 for group in groups if group.proposal_state == "ready_for_approval")
    summary = (
        f"Canonical gap queue contains {candidate_count} open candidates across {len(groups)} grouped triage patterns. "
        f"Approve-ready groups: {approve_ready}."
    )
    risks = _build_risks(request, groups)
    next_actions = _build_next_actions(groups)
    return CanonicalGapTriageSummaryResponse(
        title="Canonical gap batch triage",
        summary=summary,
        groups=groups,
        risks=risks,
        next_actions=next_actions,
        generation_metadata=CanonicalGapTriageGenerationMetadata(
            used_llm=False,
            fallback_used=True,
        ),
    )


def _build_groups(request: CanonicalGapTriageSummaryRequest) -> list[CanonicalGapTriageGroup]:
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    for candidate in request.candidates or []:
        candidate_key = _candidate_key(candidate.source, candidate.target)
        suggestion = (request.suggestions or {}).get(candidate_key)
        action = _suggestion_action(suggestion)
        proposal_state = str((request.proposal_states or {}).get(candidate_key) or "new").strip() or "new"
        focus = _group_focus(candidate, suggestion)
        group_key = (action, proposal_state, focus)
        group = grouped.setdefault(
            group_key,
            {
                "action": action,
                "proposal_state": proposal_state,
                "focus": focus,
                "count": 0,
                "source_examples": [],
            },
        )
        group["count"] = int(group["count"]) + 1
        source_examples = group["source_examples"]
        if candidate.source not in source_examples and len(source_examples) < 4:
            source_examples.append(candidate.source)

    rows: list[CanonicalGapTriageGroup] = []
    for item in grouped.values():
        action = str(item["action"])
        proposal_state = str(item["proposal_state"])
        focus = str(item["focus"])
        count = int(item["count"])
        priority = _priority_for_group(action, proposal_state)
        rows.append(
            CanonicalGapTriageGroup(
                priority=priority,
                focus=focus,
                count=count,
                suggestion_action=action,
                proposal_state=proposal_state,
                source_examples=list(item["source_examples"]),
                summary=_group_summary(action, proposal_state, focus, count),
                recommended_follow_up=_group_follow_up(action, proposal_state),
            )
        )
    return sorted(rows, key=lambda item: (_priority_rank(item.priority), -item.count, item.focus.lower()))


def _group_focus(candidate, suggestion: CanonicalGapSuggestion | None) -> str:
    if suggestion and str(suggestion.concept_id or "").strip():
        return str(suggestion.concept_id or "").strip()
    concepts = getattr(candidate.canonical_details, "shared_concepts", []) or []
    if concepts:
        first = concepts[0]
        concept_id = getattr(first, "concept_id", None)
        if concept_id:
            return str(concept_id).strip()
    return str(candidate.reason or "missing canonical path").strip() or "missing canonical path"


def _group_summary(action: str, proposal_state: str, focus: str, count: int) -> str:
    return (
        f"{count} candidates are grouped under action '{action}' with proposal state '{proposal_state}' and focus '{focus}'."
    )


def _group_follow_up(action: str, proposal_state: str) -> str:
    if proposal_state == "ready_for_approval" and action != "no_action":
        return "Review the cached suggestion once more, then approve these candidates from the queue in order."
    if action == "no_action":
        return "Inspect why the cached suggestion is missing or returned no_action before forcing glossary changes."
    if proposal_state == "needs_review":
        return "Move repeated candidates to ready_for_approval only after checking aliases, confidence, and risk notes."
    return "Use the cached suggestion payload to decide whether this candidate family should advance or be ignored."


def _build_risks(request: CanonicalGapTriageSummaryRequest, groups: list[CanonicalGapTriageGroup]) -> list[str]:
    risks: list[str] = []
    missing_suggestions = sum(1 for candidate in request.candidates or [] if _candidate_key(candidate.source, candidate.target) not in (request.suggestions or {}))
    no_action_groups = sum(1 for group in groups if group.suggestion_action == "no_action")
    if missing_suggestions:
        risks.append(f"{missing_suggestions} candidates still have no cached suggestion payload, so the queue is only partially triaged.")
    if no_action_groups:
        risks.append(f"{no_action_groups} grouped patterns currently resolve to no_action, so glossary coverage may still be incomplete or ambiguous.")
    if not groups:
        risks.append("No canonical-gap groups are available yet because no candidates are loaded.")
    return risks[:4] or ["No major canonical-gap triage risk is highlighted by the current queue."]


def _build_next_actions(groups: list[CanonicalGapTriageGroup]) -> list[str]:
    actions: list[str] = []
    if groups:
        actions.append(f"Start with the top-priority group: {groups[0].focus} ({groups[0].count} candidates).")
    if any(group.proposal_state == "ready_for_approval" and group.suggestion_action != "no_action" for group in groups):
        actions.append("Process approve-ready groups before generating new suggestions for lower-maturity candidates.")
    if any(group.suggestion_action == "no_action" for group in groups):
        actions.append("Review no_action groups separately so they do not block clean approve-ready families.")
    if not groups:
        actions.append("Load canonical gap candidates first, then generate suggestions for the highest-confidence rows.")
    return actions[:4]


def _normalize_summary(parsed: dict, fallback: CanonicalGapTriageSummaryResponse) -> CanonicalGapTriageSummaryResponse | None:
    title = str(parsed.get("title") or fallback.title).strip() or fallback.title
    summary = str(parsed.get("summary") or fallback.summary).strip() or fallback.summary
    risks = _normalize_string_list(parsed.get("risks"), fallback.risks)
    next_actions = _normalize_string_list(parsed.get("next_actions"), fallback.next_actions)
    groups = fallback.groups
    raw_groups = parsed.get("groups")
    if isinstance(raw_groups, list):
        normalized_groups: list[CanonicalGapTriageGroup] = []
        for item in raw_groups[:8]:
            if not isinstance(item, dict):
                continue
            normalized_groups.append(
                CanonicalGapTriageGroup(
                    priority=_priority(item.get("priority")),
                    focus=str(item.get("focus") or "queue cluster").strip() or "queue cluster",
                    count=int(item.get("count") or 0),
                    suggestion_action=str(item.get("suggestion_action") or "").strip(),
                    proposal_state=str(item.get("proposal_state") or "").strip(),
                    source_examples=[str(value).strip() for value in item.get("source_examples", []) if str(value).strip()][:4],
                    summary=str(item.get("summary") or "").strip(),
                    recommended_follow_up=str(item.get("recommended_follow_up") or "").strip(),
                )
            )
        if normalized_groups:
            groups = normalized_groups

    try:
        return CanonicalGapTriageSummaryResponse(
            title=title,
            summary=summary,
            groups=groups,
            risks=risks,
            next_actions=next_actions,
            generation_metadata=CanonicalGapTriageGenerationMetadata(
                used_llm=True,
                fallback_used=False,
                llm_provider=settings.llm_provider,
                llm_model=settings.llm_model,
            ),
        )
    except Exception:
        return None


def _candidate_key(source: str, target: str) -> str:
    return f"canonical_gap_{source or 'unknown'}_{target or 'unknown'}".replace(" ", "_")


def _suggestion_action(suggestion: CanonicalGapSuggestion | None) -> str:
    return str((suggestion.action if suggestion else "no_suggestion") or "no_suggestion").strip() or "no_suggestion"


def _priority_for_group(action: str, proposal_state: str) -> str:
    if proposal_state == "ready_for_approval" and action not in {"no_action", "no_suggestion"}:
        return "high"
    if action in {"no_action", "no_suggestion"}:
        return "medium"
    return "low"


def _priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 1)


def _priority(value: object) -> str:
    priority = str(value or "medium").strip().lower() or "medium"
    if priority not in {"high", "medium", "low"}:
        return "medium"
    return priority


def _normalize_string_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            return normalized[:4]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback[:4])