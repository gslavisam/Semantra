from __future__ import annotations

import json
import re

from app.core.config import settings
from app.models.mapping import (
    AutoMappingResponse,
    MappingAnalysisNarrationRequest,
    MappingAnalysisNarrationResponse,
    MappingAnalysisCanonicalCoverageSummary,
    MappingAnalysisConfidenceDistribution,
    MappingAnalysisGenerationMetadata,
    MappingAnalysisNeedsReviewItem,
    MappingAnalysisOptions,
    MappingAnalysisOverallMappingHealth,
    MappingAnalysisRequest,
    MappingAnalysisStrongestMatch,
    MappingAnalysisSummaryResponse,
    MappingAnalysisTransformationHotspot,
    MappingAnalysisUnmatchedSource,
    MappingAnalysisWorkspaceContext,
    MappingCandidate,
)
from app.services.llm_service import LLMProvider, normalize_llm_list_field, request_bounded_llm_json


def build_mapping_analysis_summary(
    request: MappingAnalysisRequest,
    provider: LLMProvider | None = None,
) -> MappingAnalysisSummaryResponse:
    fallback_summary = _build_deterministic_summary(
        request.mapping_response,
        request.workspace,
        request.options,
    )
    if provider is None:
        return fallback_summary

    prompt = build_mapping_analysis_prompt(
        request.mapping_response,
        request.workspace,
        request.options,
        fallback_summary,
    )
    response = request_bounded_llm_json(
        provider,
        prompt,
        "mapping_analysis",
    )
    if response is None:
        return fallback_summary

    _raw_response, parsed = response
    llm_summary = _normalize_llm_summary_payload(parsed, fallback_summary)
    if llm_summary is None:
        return fallback_summary
    return llm_summary


def build_mapping_analysis_narration(
    request: MappingAnalysisNarrationRequest,
    provider: LLMProvider | None = None,
) -> MappingAnalysisNarrationResponse:
    fallback_script = _fallback_spoken_script(request.summary)
    if provider is None:
        return MappingAnalysisNarrationResponse(
            spoken_script=fallback_script,
            generation_metadata=MappingAnalysisGenerationMetadata(
                used_llm=False,
                fallback_used=True,
            ),
        )

    prompt = build_mapping_analysis_narration_prompt(request.summary)
    try:
        response_text = provider.generate(prompt, settings.llm_timeout_seconds)
    except Exception:
        response_text = ""

    spoken_script = _normalize_spoken_script(response_text, fallback_script)
    used_llm = bool(response_text.strip()) and spoken_script != fallback_script
    return MappingAnalysisNarrationResponse(
        spoken_script=spoken_script,
        generation_metadata=MappingAnalysisGenerationMetadata(
            used_llm=used_llm,
            fallback_used=not used_llm,
            llm_provider=settings.llm_provider if used_llm else None,
            llm_model=settings.llm_model if used_llm else None,
        ),
    )


def build_mapping_analysis_prompt(
    mapping_response: AutoMappingResponse,
    workspace: MappingAnalysisWorkspaceContext,
    options: MappingAnalysisOptions,
    fallback_summary: MappingAnalysisSummaryResponse,
) -> str:
    evidence_payload = {
        "workspace": workspace.model_dump(mode="json"),
        "options": options.model_dump(mode="json"),
        "derived_overview": fallback_summary.model_dump(mode="json", exclude={"generation_metadata"}),
        "mapping_evidence": [_compact_mapping_evidence(mapping) for mapping in mapping_response.mappings[:20]],
        "canonical_coverage": mapping_response.canonical_coverage.model_dump(mode="json"),
    }
    return (
        "You are a senior data integration analyst preparing a technical mapping handoff for a data engineer. "
        "You must summarize only the evidence present in the provided payload. "
        "Do not invent business rules, source semantics, target semantics, or transformations that are not supported by the payload.\n\n"
        "Analyze the provided mapping response and workspace context. Produce one technical mapping overview for a technical implementor. "
        "Focus on mapping quality, ambiguity, canonical alignment, transformation hotspots, and next engineering actions.\n\n"
        "Return JSON only. No markdown. No prose outside JSON. No code fences.\n"
        "Use only the provided payload. If evidence is missing, state that explicitly.\n"
        "Do not restate every mapping. Prioritize strongest validated mappings, needs-review rows, unmatched rows, canonical findings, and implementation hotspots.\n"
        "Every risk and recommendation must be grounded in confidence, status, canonical coverage, signals, explanation lines, llm recommendation, or transformation presence.\n"
        "If a field has no evidence, return an empty array or empty string instead of inventing content.\n"
        "Return exactly these top-level fields: title, audience, mapping_mode, overall_mapping_health, confidence_distribution, strongest_matches, needs_review_items, unmatched_sources, canonical_coverage_summary, transformation_hotspots, implementation_risks, recommended_next_actions, narration_script_seed, generation_metadata.\n"
        "Treat unmatched rows, low-confidence rows, and global-assignment conflicts as the primary review queue.\n"
        "Treat canonical coverage as semantic evidence, not final proof of implementation readiness.\n"
        "Treat transformation presence as an implementation hotspot, especially when confidence is not high.\n"
        "If llm_recommendation differs from the final target, surface that as a review signal.\n\n"
        f"PAYLOAD:\n{json.dumps(evidence_payload, ensure_ascii=True)}"
    )


def build_mapping_analysis_narration_prompt(summary: MappingAnalysisSummaryResponse) -> str:
    compact_payload = {
        "title": summary.title,
        "mapping_mode": summary.mapping_mode,
        "overall_mapping_health": summary.overall_mapping_health.model_dump(mode="json"),
        "confidence_distribution": summary.confidence_distribution.model_dump(mode="json"),
        "strongest_matches": [item.model_dump(mode="json") for item in summary.strongest_matches[:4]],
        "needs_review_items": [item.model_dump(mode="json") for item in summary.needs_review_items[:5]],
        "canonical_coverage_summary": summary.canonical_coverage_summary.model_dump(mode="json"),
        "transformation_hotspots": [item.model_dump(mode="json") for item in summary.transformation_hotspots[:5]],
        "implementation_risks": list(summary.implementation_risks[:5]),
        "recommended_next_actions": list(summary.recommended_next_actions[:4]),
        "narration_script_seed": summary.narration_script_seed,
    }
    return (
        "You are a technical presenter explaining mapping analysis to a data engineer. "
        "Your script must sound natural when read aloud and must stay faithful to the supplied overview.\n\n"
        "Convert the provided technical mapping overview into one concise spoken walkthrough for a technical implementor. "
        "Focus on the current mapping state, strongest alignments, the review queue, canonical findings, transformation hotspots, and the next engineering actions.\n\n"
        "Return exactly one final spoken script and nothing else.\n"
        "Forbidden in the output: markdown, headings, bullet points, tables, JSON, speaker labels, stage directions, commentary about the script, multiple alternatives, or implementation notes.\n"
        "Do not add facts that are not present in the overview.\n"
        "Keep the tone technical, calm, and direct.\n"
        "Target length: about 90 to 150 seconds when spoken.\n"
        "Wrap the final answer only inside <final_script> and </final_script>.\n\n"
        f"OVERVIEW:\n{json.dumps(compact_payload, ensure_ascii=True)}"
    )


def _build_deterministic_summary(
    mapping_response: AutoMappingResponse,
    workspace: MappingAnalysisWorkspaceContext,
    options: MappingAnalysisOptions,
) -> MappingAnalysisSummaryResponse:
    mappings = list(mapping_response.mappings)
    total = len(mappings)
    accepted_count = sum(1 for mapping in mappings if mapping.status == "accepted" and mapping.target)
    needs_review_candidates = [mapping for mapping in mappings if _is_review_item(mapping)]
    rejected_count = sum(1 for mapping in mappings if mapping.status == "rejected")
    unmatched_mappings = [mapping for mapping in mappings if not (mapping.target or "").strip()]
    high_confidence_count = sum(1 for mapping in mappings if mapping.confidence_label == "high_confidence")
    medium_confidence_count = sum(1 for mapping in mappings if mapping.confidence_label == "medium_confidence")
    low_confidence_count = sum(1 for mapping in mappings if mapping.confidence_label == "low_confidence")
    transformation_hotspots = _build_transformation_hotspots(mappings)
    overall_risk = _determine_overall_risk(
        total=total,
        needs_review_count=len(needs_review_candidates),
        unmatched_count=len(unmatched_mappings),
        low_confidence_count=low_confidence_count,
        transformation_hotspot_count=len(transformation_hotspots),
    )
    canonical_summary = _build_canonical_coverage_summary(mapping_response)
    overall_mapping_health = MappingAnalysisOverallMappingHealth(
        summary=_build_health_summary(
            accepted_count=accepted_count,
            needs_review_count=len(needs_review_candidates),
            unmatched_count=len(unmatched_mappings),
            overall_risk=overall_risk,
            canonical_summary=canonical_summary,
        ),
        accepted_count=accepted_count,
        needs_review_count=len(needs_review_candidates),
        rejected_count=rejected_count,
        unmatched_count=len(unmatched_mappings),
        high_confidence_count=high_confidence_count,
        medium_confidence_count=medium_confidence_count,
        low_confidence_count=low_confidence_count,
        overall_risk=overall_risk,
    )
    confidence_distribution = _build_confidence_distribution(
        total,
        high_confidence_count,
        medium_confidence_count,
        low_confidence_count,
    )
    strongest_matches = _build_strongest_matches(mappings)
    needs_review_items = _build_needs_review_items(needs_review_candidates)
    unmatched_sources = _build_unmatched_sources(unmatched_mappings)
    implementation_risks = _build_implementation_risks(
        overall_mapping_health,
        canonical_summary,
        transformation_hotspots,
    )
    recommended_next_actions = _build_next_actions(
        needs_review_items,
        unmatched_sources,
        transformation_hotspots,
        canonical_summary,
    )

    return MappingAnalysisSummaryResponse(
        title=_build_title(workspace),
        audience=options.audience,
        mapping_mode=workspace.mapping_mode,
        overall_mapping_health=overall_mapping_health,
        confidence_distribution=confidence_distribution,
        strongest_matches=strongest_matches,
        needs_review_items=needs_review_items,
        unmatched_sources=unmatched_sources,
        canonical_coverage_summary=canonical_summary,
        transformation_hotspots=transformation_hotspots,
        implementation_risks=implementation_risks,
        recommended_next_actions=recommended_next_actions,
        narration_script_seed=_build_narration_seed(
            workspace,
            overall_mapping_health,
            strongest_matches,
            needs_review_items,
            transformation_hotspots,
            recommended_next_actions,
        ),
        generation_metadata=MappingAnalysisGenerationMetadata(
            used_llm=False,
            fallback_used=True,
        ),
    )


def _normalize_llm_summary_payload(
    parsed: dict,
    fallback_summary: MappingAnalysisSummaryResponse,
) -> MappingAnalysisSummaryResponse | None:
    payload = fallback_summary.model_dump(mode="json")
    for key in payload:
        if key == "generation_metadata":
            continue
        if key in parsed:
            payload[key] = parsed[key]

    generation_metadata = payload.get("generation_metadata") or {}
    generation_metadata.update(
        {
            "used_llm": True,
            "fallback_used": False,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
        }
    )
    payload["generation_metadata"] = generation_metadata

    try:
        return MappingAnalysisSummaryResponse(**payload)
    except Exception:
        return None


def _build_title(workspace: MappingAnalysisWorkspaceContext) -> str:
    source_name = (workspace.source_dataset_name or "Source").strip()
    target_name = (workspace.target_dataset_name or "Target").strip()
    if workspace.mapping_mode == "canonical":
        return f"Canonical mapping analysis: {source_name}"
    return f"Mapping analysis: {source_name} -> {target_name}"


def _fallback_spoken_script(summary: MappingAnalysisSummaryResponse) -> str:
    seed = (summary.narration_script_seed or "").strip()
    if seed:
        return seed
    return (
        f"This mapping overview covers {summary.title or 'the current integration mapping'}. "
        f"{summary.overall_mapping_health.summary or 'A detailed mapping summary is available for review.'}"
    ).strip()


def _normalize_spoken_script(text: str, fallback: str) -> str:
    candidate = text or ""
    tagged_match = re.search(r"<final_script>\s*(.*?)\s*</final_script>", candidate, flags=re.IGNORECASE | re.DOTALL)
    if tagged_match:
        candidate = tagged_match.group(1)

    cleaned_lines: list[str] = []
    for raw_line in candidate.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"[*_#`>\-\s]+", line):
            continue
        if re.fullmatch(r"\*\*?\(.*\)\*\*?", line):
            continue
        if re.fullmatch(r"\[.*\]", line):
            continue
        line = re.sub(r"^\*\*(.*?)\*\*$", r"\1", line)
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"`([^`]*)`", r"\1", line)
        line = re.sub(r"^(?:Host|Narrator|Speaker|Voiceover)\s*:\s*", "", line, flags=re.IGNORECASE)
        cleaned_lines.append(line)

    cleaned = "\n".join(cleaned_lines).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if cleaned.startswith('"') and cleaned.endswith('"') and len(cleaned) >= 2:
        cleaned = cleaned[1:-1].strip()
    return cleaned or fallback.strip()


def _build_health_summary(
    *,
    accepted_count: int,
    needs_review_count: int,
    unmatched_count: int,
    overall_risk: str,
    canonical_summary: MappingAnalysisCanonicalCoverageSummary,
) -> str:
    return (
        f"{accepted_count} mappings are accepted, {needs_review_count} require review, and {unmatched_count} remain unmatched. "
        f"Overall delivery risk is {overall_risk}. Canonical coverage is {canonical_summary.coverage_strength}."
    )


def _build_confidence_distribution(
    total: int,
    high_confidence_count: int,
    medium_confidence_count: int,
    low_confidence_count: int,
) -> MappingAnalysisConfidenceDistribution:
    safe_total = max(total, 1)
    high_ratio = round(high_confidence_count / safe_total, 4)
    medium_ratio = round(medium_confidence_count / safe_total, 4)
    low_ratio = round(low_confidence_count / safe_total, 4)

    if low_ratio >= 0.35:
        interpretation = "Low-confidence mappings make up a material share of the review workload."
    elif high_ratio >= 0.6:
        interpretation = "Most mappings are high confidence, with a smaller focused review queue."
    else:
        interpretation = "Confidence is mixed, so engineering review should focus on ambiguous and unmatched rows first."

    return MappingAnalysisConfidenceDistribution(
        high_confidence_count=high_confidence_count,
        medium_confidence_count=medium_confidence_count,
        low_confidence_count=low_confidence_count,
        high_confidence_ratio=high_ratio,
        medium_confidence_ratio=medium_ratio,
        low_confidence_ratio=low_ratio,
        interpretation=interpretation,
    )


def _build_strongest_matches(mappings: list[MappingCandidate]) -> list[MappingAnalysisStrongestMatch]:
    candidates = [mapping for mapping in mappings if mapping.target and mapping.status == "accepted"]
    ranked = sorted(
        candidates,
        key=lambda mapping: (
            mapping.confidence,
            len(_supporting_signals(mapping)),
            len(_shared_concepts(mapping)),
        ),
        reverse=True,
    )
    strongest_matches: list[MappingAnalysisStrongestMatch] = []
    for mapping in ranked[:5]:
        supporting_signals = _supporting_signals(mapping)
        strongest_matches.append(
            MappingAnalysisStrongestMatch(
                source=mapping.source,
                target=mapping.target or "",
                confidence=round(float(mapping.confidence or 0.0), 4),
                why_it_is_strong=_build_strong_match_reason(mapping, supporting_signals),
                supporting_signals=supporting_signals,
                canonical_path=_canonical_path(mapping),
            )
        )
    return strongest_matches


def _build_needs_review_items(mappings: list[MappingCandidate]) -> list[MappingAnalysisNeedsReviewItem]:
    ranked = sorted(
        mappings,
        key=lambda mapping: (
            not _has_llm_conflict(mapping),
            mapping.target is not None,
            mapping.confidence,
        ),
    )
    review_items: list[MappingAnalysisNeedsReviewItem] = []
    for mapping in ranked[:8]:
        review_items.append(
            MappingAnalysisNeedsReviewItem(
                source=mapping.source,
                proposed_target=mapping.target or "",
                confidence=round(float(mapping.confidence or 0.0), 4),
                review_reason=_build_review_reason(mapping),
                competing_targets=list(mapping.alternatives[:3]),
                canonical_status=_canonical_status(mapping),
                recommended_check=_recommended_check(mapping),
            )
        )
    return review_items


def _build_unmatched_sources(mappings: list[MappingCandidate]) -> list[MappingAnalysisUnmatchedSource]:
    rows: list[MappingAnalysisUnmatchedSource] = []
    for mapping in mappings:
        rows.append(
            MappingAnalysisUnmatchedSource(
                source=mapping.source,
                reason=_first_explanation_line(mapping) or "No target was assigned from the current candidate set.",
                recommended_follow_up=_recommended_follow_up_for_unmatched(mapping),
            )
        )
    return rows


def _build_canonical_coverage_summary(
    mapping_response: AutoMappingResponse,
) -> MappingAnalysisCanonicalCoverageSummary:
    project = mapping_response.canonical_coverage.project
    strength = "low"
    if project.coverage_ratio >= 0.75:
        strength = "strong"
    elif project.coverage_ratio >= 0.4:
        strength = "moderate"

    interpretation = (
        f"Project coverage is {round(project.coverage_ratio * 100)}% with {project.shared_concept_count} shared concepts."
    )
    if strength == "low":
        interpretation += " Canonical support is partial, so unresolved or weak mappings need closer semantic review."
    elif strength == "strong":
        interpretation += " Canonical grounding is strong, but implementation readiness still depends on confidence and transformation effort."
    else:
        interpretation += " Canonical grounding is useful but not strong enough to remove the need for targeted review."

    return MappingAnalysisCanonicalCoverageSummary(
        source_coverage=round(float(mapping_response.canonical_coverage.source.coverage_ratio or 0.0), 4),
        target_coverage=round(float(mapping_response.canonical_coverage.target.coverage_ratio or 0.0), 4),
        project_coverage=round(float(project.coverage_ratio or 0.0), 4),
        shared_concepts=list(project.shared_concepts),
        source_only_concepts=list(project.source_only_concepts),
        target_only_concepts=list(project.target_only_concepts),
        coverage_strength=strength,
        coverage_interpretation=interpretation,
    )


def _build_transformation_hotspots(mappings: list[MappingCandidate]) -> list[MappingAnalysisTransformationHotspot]:
    hotspots: list[MappingAnalysisTransformationHotspot] = []
    for mapping in mappings:
        if not (mapping.transformation_code or "").strip():
            continue
        risk = "low"
        if mapping.status != "accepted" or mapping.confidence_label == "low_confidence":
            risk = "high"
        elif mapping.confidence_label == "medium_confidence":
            risk = "medium"
        hotspots.append(
            MappingAnalysisTransformationHotspot(
                source=mapping.source,
                target=mapping.target or "",
                transformation_required=True,
                transformation_risk=risk,
                reason=_build_transformation_reason(mapping),
            )
        )
    return hotspots[:8]


def _build_implementation_risks(
    health: MappingAnalysisOverallMappingHealth,
    canonical_summary: MappingAnalysisCanonicalCoverageSummary,
    transformation_hotspots: list[MappingAnalysisTransformationHotspot],
) -> list[str]:
    risks: list[str] = []
    if health.unmatched_count:
        risks.append(
            f"{health.unmatched_count} source fields are still unmatched, so downstream implementation cannot be considered complete."
        )
    if health.needs_review_count:
        risks.append(
            f"{health.needs_review_count} mappings remain in review, which creates selection ambiguity for implementation and testing."
        )
    if canonical_summary.coverage_strength == "low":
        risks.append(
            "Canonical grounding is limited, so name similarity may be carrying more weight than shared business concepts."
        )
    if transformation_hotspots:
        risks.append(
            f"{len(transformation_hotspots)} mappings already require transformation logic, increasing implementation and validation effort."
        )
    if not risks:
        risks.append("No major implementation blockers are visible in the current mapping payload, but accepted mappings still need normal downstream testing.")
    return risks[:5]


def _build_next_actions(
    needs_review_items: list[MappingAnalysisNeedsReviewItem],
    unmatched_sources: list[MappingAnalysisUnmatchedSource],
    transformation_hotspots: list[MappingAnalysisTransformationHotspot],
    canonical_summary: MappingAnalysisCanonicalCoverageSummary,
) -> list[str]:
    actions: list[str] = []
    if needs_review_items:
        actions.append("Review the ambiguous mappings first, starting with rows that have low confidence or LLM-to-final target disagreement.")
    if unmatched_sources:
        actions.append("Resolve unmatched source fields by checking missing glossary coverage, absent targets, or schema context gaps.")
    if canonical_summary.coverage_strength != "strong":
        actions.append("Inspect canonical coverage gaps before forcing weak target selections that lack semantic support.")
    if transformation_hotspots:
        actions.append("Validate transformation hotspots with preview data and targeted tests before generating final implementation artifacts.")
    if not actions:
        actions.append("Proceed to preview and code generation, then validate the accepted mappings against representative data samples.")
    return actions[:5]


def _build_narration_seed(
    workspace: MappingAnalysisWorkspaceContext,
    health: MappingAnalysisOverallMappingHealth,
    strongest_matches: list[MappingAnalysisStrongestMatch],
    needs_review_items: list[MappingAnalysisNeedsReviewItem],
    transformation_hotspots: list[MappingAnalysisTransformationHotspot],
    next_actions: list[str],
) -> str:
    strongest_line = ""
    if strongest_matches:
        top = strongest_matches[0]
        strongest_line = (
            f"The strongest confirmed alignment is {top.source} to {top.target} at {round(top.confidence * 100)} percent confidence. "
        )
    review_line = ""
    if needs_review_items:
        review_line = (
            f"The current review queue contains {len(needs_review_items)} high-priority items, led by {needs_review_items[0].source}. "
        )
    transformation_line = ""
    if transformation_hotspots:
        transformation_line = (
            f"There are {len(transformation_hotspots)} transformation hotspots that need implementation attention. "
        )
    next_action_line = next_actions[0] if next_actions else "Proceed with standard downstream validation."
    return (
        f"This overview covers the current Semantra mapping state for {workspace.source_dataset_name} "
        f"against {workspace.target_dataset_name}. {health.summary} {strongest_line}{review_line}{transformation_line}"
        f"The next engineering priority is: {next_action_line}"
    ).strip()


def _determine_overall_risk(
    *,
    total: int,
    needs_review_count: int,
    unmatched_count: int,
    low_confidence_count: int,
    transformation_hotspot_count: int,
) -> str:
    if total <= 0:
        return "high"

    review_ratio = needs_review_count / total
    low_ratio = low_confidence_count / total
    if unmatched_count > 0 or review_ratio >= 0.35 or low_ratio >= 0.35:
        return "high"
    if transformation_hotspot_count > 0 or review_ratio >= 0.15 or low_ratio >= 0.15:
        return "medium"
    return "low"


def _compact_mapping_evidence(mapping: MappingCandidate) -> dict[str, object]:
    return {
        "source": mapping.source,
        "target": mapping.target,
        "confidence": round(float(mapping.confidence or 0.0), 4),
        "confidence_label": mapping.confidence_label,
        "status": mapping.status,
        "method": mapping.method,
        "signals": mapping.signals.model_dump(mode="json"),
        "explanation": list(mapping.explanation[:4]),
        "alternatives": list(mapping.alternatives[:4]),
        "has_transformation": bool((mapping.transformation_code or "").strip()),
        "canonical_details": mapping.canonical_details.model_dump(mode="json"),
        "llm_recommendation": mapping.llm_recommendation.model_dump(mode="json") if mapping.llm_recommendation else None,
    }


def _is_review_item(mapping: MappingCandidate) -> bool:
    return (
        mapping.status != "accepted"
        or not (mapping.target or "").strip()
        or mapping.confidence_label == "low_confidence"
        or _has_llm_conflict(mapping)
    )


def _has_llm_conflict(mapping: MappingCandidate) -> bool:
    llm_recommendation = mapping.llm_recommendation
    if llm_recommendation is None:
        return False
    recommended_target = (llm_recommendation.selected_target or "").strip()
    final_target = (mapping.target or "").strip()
    if recommended_target == "no_match":
        return bool(final_target)
    return bool(recommended_target and recommended_target != final_target)


def _supporting_signals(mapping: MappingCandidate) -> list[str]:
    signal_pairs = list(mapping.signals.model_dump().items())
    active = [name for name, value in signal_pairs if float(value or 0.0) >= 0.2]
    if active:
        return active[:4]
    fallback = [name for name, value in sorted(signal_pairs, key=lambda item: item[1], reverse=True) if float(value or 0.0) > 0]
    return fallback[:4]


def _shared_concepts(mapping: MappingCandidate) -> list[str]:
    return [item.display_name for item in mapping.canonical_details.shared_concepts if item.display_name]


def _canonical_path(mapping: MappingCandidate) -> str:
    shared = _shared_concepts(mapping)
    if shared and mapping.target:
        return f"{mapping.source} -> {', '.join(shared)} -> {mapping.target}"
    if shared:
        return f"{mapping.source} -> {', '.join(shared)}"
    return ""


def _build_strong_match_reason(mapping: MappingCandidate, supporting_signals: list[str]) -> str:
    reasons: list[str] = []
    if supporting_signals:
        reasons.append("signal support from " + ", ".join(supporting_signals))
    if _shared_concepts(mapping):
        reasons.append("shared canonical concepts")
    if mapping.status == "accepted":
        reasons.append("accepted final assignment")
    if not reasons:
        reasons.append("consistent ranking evidence")
    return f"This match is strong because it combines {', '.join(reasons)}."


def _build_review_reason(mapping: MappingCandidate) -> str:
    reasons: list[str] = []
    if not (mapping.target or "").strip():
        reasons.append("no target is currently assigned")
    if mapping.confidence_label == "low_confidence":
        reasons.append("confidence is low")
    if mapping.status != "accepted":
        reasons.append(f"status is {mapping.status}")
    if _has_llm_conflict(mapping):
        reasons.append("LLM recommendation differs from the final target")
    explanation = _first_explanation_line(mapping)
    if explanation:
        reasons.append(explanation)
    return "; ".join(reasons[:3]) or "Manual review is still required for this mapping."


def _recommended_check(mapping: MappingCandidate) -> str:
    if not (mapping.target or "").strip():
        return "Check whether the source field is missing glossary coverage or whether no viable target exists in the current dataset."
    if _has_llm_conflict(mapping):
        return "Compare the final assignment against the LLM recommendation and the top competing targets before accepting it."
    if mapping.confidence_label == "low_confidence":
        return "Review metadata descriptions, sample values, and canonical evidence before locking the target."
    if (mapping.transformation_code or "").strip():
        return "Validate the transformation logic on sample rows before generating final output artifacts."
    return "Review the ranked alternatives and confirm that the chosen target matches the intended business meaning."


def _canonical_status(mapping: MappingCandidate) -> str:
    shared = len(mapping.canonical_details.shared_concepts)
    source_only = len(mapping.canonical_details.source_concepts)
    target_only = len(mapping.canonical_details.target_concepts)
    if shared:
        return "shared canonical match"
    if source_only and target_only:
        return "different canonical concepts"
    if source_only:
        return "source-only canonical match"
    if target_only:
        return "target-only canonical match"
    return "no canonical match"


def _recommended_follow_up_for_unmatched(mapping: MappingCandidate) -> str:
    if len(mapping.alternatives) > 0:
        return "Review the ranked alternatives and confirm whether a weak target should be promoted or the field should remain unmatched."
    if len(mapping.canonical_details.source_concepts) > 0:
        return "Inspect glossary coverage or target schema completeness because the source has canonical grounding but no assigned target."
    return "Check missing schema context, glossary coverage, or whether this field should be excluded from the current integration scope."


def _build_transformation_reason(mapping: MappingCandidate) -> str:
    reasons = []
    if mapping.confidence_label != "high_confidence":
        reasons.append(f"mapping confidence is {mapping.confidence_label}")
    if mapping.status != "accepted":
        reasons.append(f"mapping status is {mapping.status}")
    if mapping.llm_recommendation is not None:
        reasons.append("transformation logic was proposed alongside LLM review")
    explanation = _first_explanation_line(mapping)
    if explanation:
        reasons.append(explanation)
    return "; ".join(reasons[:3]) or "Transformation code is present and should be validated before implementation."


def _first_explanation_line(mapping: MappingCandidate) -> str:
    explanation = normalize_llm_list_field(mapping.explanation)
    return str(explanation[0]).strip() if explanation else ""