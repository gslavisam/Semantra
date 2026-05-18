from __future__ import annotations

import json

from app.core.config import settings
from app.models.mapping import (
    CatalogReuseFitGenerationMetadata,
    CatalogReuseFitRequest,
    CatalogReuseFitResponse,
)
from app.services.llm_service import LLMProvider, request_bounded_llm_json


def build_catalog_reuse_fit(
    request: CatalogReuseFitRequest,
    provider: LLMProvider | None = None,
) -> CatalogReuseFitResponse:
    fallback = _build_fallback_fit(request)
    if provider is None:
        return fallback

    prompt = build_catalog_reuse_fit_prompt(request, fallback)
    response = request_bounded_llm_json(
        provider,
        prompt,
        "catalog_reuse_fit",
    )
    if response is None:
        return fallback

    _raw_response, parsed = response
    normalized = _normalize_fit(parsed, fallback)
    if normalized is None:
        return fallback
    return normalized


def build_catalog_reuse_fit_prompt(
    request: CatalogReuseFitRequest,
    fallback: CatalogReuseFitResponse,
) -> str:
    evidence = {
        "mapping_set_detail": request.mapping_set_detail.model_dump(mode="json"),
        "workspace_context": request.workspace_context.model_dump(mode="json"),
        "fallback_fit": fallback.model_dump(mode="json", exclude={"generation_metadata"}),
    }
    return (
        "You are assessing whether a saved mapping set is a good reuse candidate for the current workspace context. "
        "Stay strictly grounded in the provided mapping-set metadata, decision counts, systems, domain, artifact type, canonical coverage, unmatched-source context, and workspace context.\n\n"
        "Return JSON only. No markdown. No code fences. No extra prose.\n"
        "Do not tell the user to apply or persist automatically. Only explain fit, risks, and next controlled actions.\n"
        "Return exactly these top-level fields: title, fit_assessment, summary, key_matches, risks, next_actions, generation_metadata.\n\n"
        f"PAYLOAD:\n{json.dumps(evidence, ensure_ascii=True)}"
    )


def _build_fallback_fit(request: CatalogReuseFitRequest) -> CatalogReuseFitResponse:
    mapping_set = request.mapping_set_detail
    workspace = request.workspace_context
    key_matches: list[str] = []
    risks: list[str] = []
    next_actions: list[str] = []
    score = 0
    mapping_concepts = {str(concept).strip() for concept in mapping_set.canonical_concepts if str(concept).strip()}
    workspace_shared_concepts = {
        str(concept).strip() for concept in workspace.current_shared_concepts if str(concept).strip()
    }
    shared_concepts = sorted(mapping_concepts & workspace_shared_concepts)
    workspace_unmatched = {
        str(source).strip() for source in workspace.current_unmatched_sources if str(source).strip()
    }
    mapping_unmatched = {str(source).strip() for source in mapping_set.unmatched_sources if str(source).strip()}
    repeated_unmatched = sorted(workspace_unmatched & mapping_unmatched)
    needs_review_count = int(workspace.current_status_counts.get("needs_review") or 0)

    if _same(mapping_set.source_system, workspace.source_system):
        key_matches.append(f"Source system matches the current workspace context: {mapping_set.source_system}.")
        score += 1
    if _same(mapping_set.target_system, workspace.target_system):
        key_matches.append(f"Target system matches the current workspace context: {mapping_set.target_system}.")
        score += 1
    if shared_concepts:
        key_matches.append(
            f"Catalog and workspace share canonical concepts: {', '.join(shared_concepts[:3])}."
        )
        score += 1
    if needs_review_count:
        key_matches.append(
            f"Workspace still has {needs_review_count} needs-review items, so reuse can be checked against an active unresolved queue."
        )
    if _same(mapping_set.business_domain, workspace.business_domain):
        key_matches.append(f"Business domain matches the current workspace context: {mapping_set.business_domain}.")
        score += 1
    if workspace.workspace_loaded and workspace.current_decision_count:
        key_matches.append(
            f"Workspace already has {workspace.current_decision_count} active decisions, so this reuse candidate can be compared against a live review context."
        )
        score += 1

    if mapping_set.artifact_type == "canonical-only" and str(workspace.mapping_mode or "").lower() == "canonical":
        key_matches.append("Artifact type and workspace mode are both canonical-oriented.")
        score += 1
    elif mapping_set.artifact_type == "standard" and str(workspace.mapping_mode or "").lower() == "standard":
        key_matches.append("Artifact type and workspace mode are both standard mapping flows.")
        score += 1
    else:
        risks.append(
            f"Artifact type '{mapping_set.artifact_type}' does not cleanly align with workspace mode '{workspace.mapping_mode or 'unknown'}'."
        )

    if mapping_set.status != "approved":
        risks.append(f"This mapping set is currently {mapping_set.status}, so it is not a governance-ready reuse candidate yet.")
    if workspace.workspace_loaded and not _same(mapping_set.source_system, workspace.source_system):
        risks.append("Source-system mismatch means reuse may carry hidden semantics or transformation differences.")
    if workspace.workspace_loaded and not _same(mapping_set.target_system, workspace.target_system):
        risks.append("Target-system mismatch means reuse may require remapping even if field names look similar.")
    if workspace.workspace_loaded and not _same(mapping_set.business_domain, workspace.business_domain):
        risks.append("Business-domain mismatch reduces confidence that canonical concepts and review outcomes are portable.")
    if repeated_unmatched:
        risks.append(
            f"Workspace and catalog both leave some sources unresolved: {', '.join(repeated_unmatched[:3])}."
        )
    elif mapping_unmatched and workspace.workspace_loaded:
        risks.append("Saved mapping set has unresolved source fields that should be checked against the current workspace review queue.")
    if not workspace.workspace_loaded:
        risks.append("No active workspace context is loaded, so reuse fit is based on catalog metadata only.")

    fit_assessment = "strong_fit" if score >= 4 else "partial_fit" if score >= 2 else "low_fit"
    next_actions.append("Inspect mapping decisions and unmatched sources before reusing this mapping set in Workspace.")
    if needs_review_count:
        next_actions.append("Compare this candidate against the current needs-review queue before applying reuse.")
    if repeated_unmatched:
        next_actions.append("Check whether the repeated unmatched sources need canonical coverage or transformation work rather than direct reuse.")
    if fit_assessment == "strong_fit" and mapping_set.status == "approved":
        next_actions.append("This candidate is strong enough for manual reuse review in Workspace under the current governance gate.")
    elif fit_assessment == "partial_fit":
        next_actions.append("Compare source/target systems and domain assumptions before treating this mapping set as reusable.")
    else:
        next_actions.append("Keep this candidate as reference material only unless the workspace context becomes closer to the saved integration.")

    summary_risk = risks[0] if risks else "No major reuse-fit risk is highlighted by the current metadata."
    summary = (
        f"Catalog reuse fit is assessed as {fit_assessment.replace('_', ' ')} for mapping set '{mapping_set.name}'. "
        f"Matched signals: {len(key_matches)}. Primary risk: {summary_risk}"
    )
    return CatalogReuseFitResponse(
        title=f"Reuse fit for {mapping_set.name}",
        fit_assessment=fit_assessment,
        summary=summary,
        key_matches=key_matches[:4] or ["No strong workspace-to-catalog fit signals were detected."],
        risks=risks[:4] or ["No major reuse-fit risk is highlighted by the current metadata."],
        next_actions=next_actions[:4],
        generation_metadata=CatalogReuseFitGenerationMetadata(
            used_llm=False,
            fallback_used=True,
        ),
    )


def _normalize_fit(parsed: dict, fallback: CatalogReuseFitResponse) -> CatalogReuseFitResponse | None:
    fit_assessment = _normalize_assessment(parsed.get("fit_assessment") or fallback.fit_assessment)
    summary = str(parsed.get("summary") or fallback.summary).strip() or fallback.summary
    title = str(parsed.get("title") or fallback.title).strip() or fallback.title
    key_matches = _normalize_string_list(parsed.get("key_matches"), fallback.key_matches)
    risks = _normalize_string_list(parsed.get("risks"), fallback.risks)
    next_actions = _normalize_string_list(parsed.get("next_actions"), fallback.next_actions)
    try:
        return CatalogReuseFitResponse(
            title=title,
            fit_assessment=fit_assessment,
            summary=summary,
            key_matches=key_matches,
            risks=risks,
            next_actions=next_actions,
            generation_metadata=CatalogReuseFitGenerationMetadata(
                used_llm=True,
                fallback_used=False,
                llm_provider=settings.llm_provider,
                llm_model=settings.llm_model,
            ),
        )
    except Exception:
        return None


def _same(left: str | None, right: str | None) -> bool:
    return str(left or "").strip().lower() and str(left or "").strip().lower() == str(right or "").strip().lower()


def _normalize_assessment(value: object) -> str:
    normalized = str(value or "partial_fit").strip().lower() or "partial_fit"
    if normalized not in {"strong_fit", "partial_fit", "low_fit"}:
        return "partial_fit"
    return normalized


def _normalize_string_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            return normalized[:4]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback[:4])