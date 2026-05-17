from __future__ import annotations

import json

from app.core.config import settings
from app.models.mapping import ReviewPlanCluster, ReviewPlanGenerationMetadata, ReviewPlanRequest, ReviewPlanResponse
from app.services.llm_service import LLMProvider, request_llm_json


def build_review_plan(
    request: ReviewPlanRequest,
    provider: LLMProvider | None = None,
) -> ReviewPlanResponse:
    fallback = _build_fallback_review_plan(request)
    if provider is None:
        return fallback

    prompt = build_review_plan_prompt(request, fallback)
    response = request_llm_json(
        provider,
        prompt,
        settings.llm_timeout_seconds,
        settings.llm_max_retries,
        "review_plan",
    )
    if response is None:
        return fallback

    _raw_response, parsed = response
    normalized = _normalize_review_plan(parsed, fallback)
    if normalized is None:
        return fallback
    return normalized


def build_review_plan_prompt(
    request: ReviewPlanRequest,
    fallback: ReviewPlanResponse,
) -> str:
    evidence = {
        "filters": request.filters,
        "filtered_rows": request.filtered_rows[:30],
        "attention_summary_rows": request.attention_summary_rows[:12],
        "fallback_plan": fallback.model_dump(mode="json", exclude={"generation_metadata"}),
    }
    return (
        "You are planning a bounded mapping-review triage workflow for a human reviewer. "
        "Stay strictly grounded in the provided filtered rows, issue groups, statuses, confidence labels, and canonical states.\n\n"
        "Return JSON only. No markdown. No code fences. No extra prose.\n"
        "Do not propose target mappings. Do not change statuses. Do not invent glossary concepts.\n"
        "Return exactly these top-level fields: title, queue_summary, clusters, risks, next_actions, generation_metadata.\n"
        "Each cluster should describe a repeated review pattern with priority, count, summary, and recommended_follow_up.\n\n"
        f"PAYLOAD:\n{json.dumps(evidence, ensure_ascii=True)}"
    )


def _build_fallback_review_plan(request: ReviewPlanRequest) -> ReviewPlanResponse:
    filters = request.filters or {}
    attention_rows = list(request.attention_summary_rows or [])
    filtered_rows = list(request.filtered_rows or [])
    clusters = [_cluster_from_attention_row(item) for item in attention_rows[:6]]

    if not clusters and filtered_rows:
        unmatched_count = sum(1 for row in filtered_rows if not str(row.get("target") or "").strip())
        low_confidence_count = sum(1 for row in filtered_rows if str(row.get("confidence_label") or "") == "low_confidence")
        if unmatched_count:
            clusters.append(
                ReviewPlanCluster(
                    issue_type="unmatched",
                    focus="unmatched targets",
                    canonical_status="mixed",
                    priority="high",
                    count=unmatched_count,
                    summary="Unmatched rows still need either viable target candidates or glossary coverage.",
                    recommended_follow_up="Check missing glossary coverage or absent viable target candidates before forcing manual target choices.",
                )
            )
        if low_confidence_count:
            clusters.append(
                ReviewPlanCluster(
                    issue_type="low_confidence",
                    focus="ambiguous ranking",
                    canonical_status="mixed",
                    priority="medium",
                    count=low_confidence_count,
                    summary="Low-confidence rows still need ranking review or stronger business-context evidence.",
                    recommended_follow_up="Inspect explanation lines, canonical status, and source metadata before accepting low-confidence rows.",
                )
            )

    total_rows = len(filtered_rows)
    queue_summary = (
        f"Review queue currently contains {total_rows} filtered rows and {len(clusters)} repeated issue groups. "
        f"Status filter: {filters.get('status', 'All') or 'All'}, confidence filter: {filters.get('confidence_label', 'All') or 'All'}."
    )

    risks = _build_risks(filtered_rows, clusters)
    next_actions = _build_next_actions(filters, filtered_rows, clusters)
    return ReviewPlanResponse(
        title="Review triage plan",
        queue_summary=queue_summary,
        clusters=clusters,
        risks=risks,
        next_actions=next_actions,
        generation_metadata=ReviewPlanGenerationMetadata(
            used_llm=False,
            fallback_used=True,
        ),
    )


def _cluster_from_attention_row(item: dict) -> ReviewPlanCluster:
    issue_type = str(item.get("issue_type") or "review_attention").strip() or "review_attention"
    count = int(item.get("count") or 0)
    canonical_status = str(item.get("canonical_status") or "").strip()
    focus = str(item.get("focus") or "review cluster").strip() or "review cluster"
    source_examples = [part.strip() for part in str(item.get("source_examples") or "").split(",") if part.strip()]
    priority = "high" if issue_type == "unmatched" or count >= 3 else "medium"
    return ReviewPlanCluster(
        issue_type=issue_type,
        focus=focus,
        canonical_status=canonical_status,
        priority=priority,
        count=count,
        source_examples=source_examples[:4],
        summary=(
            f"{count} rows are grouped under {issue_type.replace('_', ' ')} with focus '{focus}'."
            if count
            else f"Review cluster for {focus}."
        ),
        recommended_follow_up=str(item.get("follow_up") or "Review the repeated evidence before changing row-level decisions.").strip(),
    )


def _build_risks(filtered_rows: list[dict], clusters: list[ReviewPlanCluster]) -> list[str]:
    risks: list[str] = []
    unmatched_count = sum(1 for row in filtered_rows if not str(row.get("target") or "").strip())
    low_confidence_count = sum(1 for row in filtered_rows if str(row.get("confidence_label") or "") == "low_confidence")
    if unmatched_count:
        risks.append(f"There are still {unmatched_count} unmatched rows in the filtered review queue.")
    if low_confidence_count:
        risks.append(f"There are {low_confidence_count} low-confidence rows, so acceptance would still carry ranking ambiguity risk.")
    if not clusters:
        risks.append("No repeated review clusters are visible yet, so triage should stay row-by-row until more evidence accumulates.")
    return risks[:4] or ["No major review risk is highlighted by the current filtered queue."]


def _build_next_actions(filters: dict[str, str], filtered_rows: list[dict], clusters: list[ReviewPlanCluster]) -> list[str]:
    actions: list[str] = []
    if clusters:
        first_cluster = clusters[0]
        actions.append(f"Start with the highest-priority cluster: {first_cluster.focus} ({first_cluster.count} rows).")
    if any(cluster.issue_type == "unmatched" for cluster in clusters):
        actions.append("Resolve unmatched rows before polishing lower-risk ranking ambiguities.")
    if any(cluster.issue_type == "low_confidence" for cluster in clusters):
        actions.append("Use explanation lines and canonical signals to separate true ambiguity from missing metadata context.")
    if not filtered_rows:
        actions.append("Relax the current filters or rerun mapping to load a non-empty review queue.")
    if filters.get("source") and filters.get("source") != "All":
        actions.append(f"Keep the source filter on {filters['source']} until that row family is fully triaged.")
    return actions[:4] or ["Review row-level evidence directly in the current filtered queue."]


def _normalize_review_plan(parsed: dict, fallback: ReviewPlanResponse) -> ReviewPlanResponse | None:
    title = str(parsed.get("title") or fallback.title).strip() or fallback.title
    queue_summary = str(parsed.get("queue_summary") or fallback.queue_summary).strip() or fallback.queue_summary
    risks = _normalize_string_list(parsed.get("risks"), fallback.risks)
    next_actions = _normalize_string_list(parsed.get("next_actions"), fallback.next_actions)
    raw_clusters = parsed.get("clusters")
    clusters = fallback.clusters
    if isinstance(raw_clusters, list):
        normalized_clusters: list[ReviewPlanCluster] = []
        for item in raw_clusters[:6]:
            if not isinstance(item, dict):
                continue
            normalized_clusters.append(
                ReviewPlanCluster(
                    issue_type=str(item.get("issue_type") or "review_attention").strip() or "review_attention",
                    focus=str(item.get("focus") or "review cluster").strip() or "review cluster",
                    canonical_status=str(item.get("canonical_status") or "").strip(),
                    priority=_normalize_priority(item.get("priority")),
                    count=int(item.get("count") or 0),
                    source_examples=[str(value).strip() for value in item.get("source_examples", []) if str(value).strip()][:4],
                    summary=str(item.get("summary") or "").strip(),
                    recommended_follow_up=str(item.get("recommended_follow_up") or "").strip(),
                )
            )
        if normalized_clusters:
            clusters = normalized_clusters

    try:
        return ReviewPlanResponse(
            title=title,
            queue_summary=queue_summary,
            clusters=clusters,
            risks=risks,
            next_actions=next_actions,
            generation_metadata=ReviewPlanGenerationMetadata(
                used_llm=True,
                fallback_used=False,
                llm_provider=settings.llm_provider,
                llm_model=settings.llm_model,
            ),
        )
    except Exception:
        return None


def _normalize_priority(value: object) -> str:
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