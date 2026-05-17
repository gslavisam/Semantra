from __future__ import annotations

import json

from app.core.config import settings
from app.models.mapping import (
    BenchmarkExplanationGenerationMetadata,
    BenchmarkExplanationRequest,
    BenchmarkExplanationResponse,
)
from app.services.llm_service import LLMProvider, request_llm_json


def build_benchmark_explanation(
    request: BenchmarkExplanationRequest,
    provider: LLMProvider | None = None,
) -> BenchmarkExplanationResponse:
    fallback = _build_fallback_explanation(request)
    if provider is None:
        return fallback

    prompt = build_benchmark_explanation_prompt(request, fallback)
    response = request_llm_json(
        provider,
        prompt,
        settings.llm_timeout_seconds,
        settings.llm_max_retries,
        "benchmark_explanation",
    )
    if response is None:
        return fallback

    _raw_response, parsed = response
    normalized = _normalize_benchmark_explanation(parsed, fallback)
    if normalized is None:
        return fallback
    return normalized


def build_benchmark_explanation_prompt(
    request: BenchmarkExplanationRequest,
    fallback: BenchmarkExplanationResponse,
) -> str:
    evidence = {
        "dataset_name": request.dataset_name,
        "benchmark_result": request.benchmark_result.model_dump(mode="json") if request.benchmark_result else None,
        "correction_impact": request.correction_impact.model_dump(mode="json") if request.correction_impact else None,
        "profile_comparison": request.profile_comparison.model_dump(mode="json") if request.profile_comparison else None,
        "fallback_explanation": fallback.model_dump(mode="json", exclude={"generation_metadata"}),
    }
    return (
        "You are explaining benchmark evidence for a mapping-engine tuning workflow. "
        "Stay strictly grounded in the provided metrics and recommendation fields.\n\n"
        "Return JSON only. No markdown. No code fences. No extra prose.\n"
        "Summarize what the benchmark evidence says, what the main risks are, and what the next controlled actions should be.\n"
        "Do not invent causes that are not supported by the payload.\n"
        "Return exactly these top-level fields: title, summary, key_findings, risks, next_actions, generation_metadata.\n"
        "Keep lists short and specific.\n\n"
        f"PAYLOAD:\n{json.dumps(evidence, ensure_ascii=True)}"
    )


def _build_fallback_explanation(request: BenchmarkExplanationRequest) -> BenchmarkExplanationResponse:
    dataset_name = str(request.dataset_name or "").strip() or "selected benchmark dataset"
    title = f"Benchmark explanation for {dataset_name}"
    benchmark_result = request.benchmark_result
    correction_impact = request.correction_impact
    profile_comparison = request.profile_comparison

    key_findings: list[str] = []
    risks: list[str] = []
    next_actions: list[str] = []

    if benchmark_result is not None:
        key_findings.append(
            "Benchmark accuracy is "
            f"{_percent(benchmark_result.accuracy)} with {benchmark_result.correct_matches} correct matches across {benchmark_result.total_fields} fields."
        )
        key_findings.append(
            f"Top-1 ranking accuracy is {_percent(benchmark_result.top1_accuracy)}, which shows how often the first candidate is already correct."
        )
        low_confidence_accuracy = float(benchmark_result.confidence_by_bucket.get("low_confidence", 0.0) or 0.0)
        if low_confidence_accuracy > 0 or benchmark_result.confidence_by_bucket:
            key_findings.append(
                "Confidence buckets are strongest at high-confidence = "
                f"{_percent(benchmark_result.confidence_by_bucket.get('high_confidence', 0.0))} and weakest at low-confidence = {_percent(low_confidence_accuracy)}."
            )
        if benchmark_result.accuracy < 1.0:
            missed = benchmark_result.total_fields - benchmark_result.correct_matches
            risks.append(f"The current benchmark still misses {missed} mapped fields, so deterministic tuning is not complete.")
        if benchmark_result.top1_accuracy + 0.05 < benchmark_result.accuracy:
            risks.append("Ranking quality is weaker than final selected-match accuracy, which suggests candidate ordering still needs work.")

    if correction_impact is not None:
        accuracy_delta = float(correction_impact.accuracy_delta or 0.0)
        top1_delta = float(correction_impact.top1_accuracy_delta or 0.0)
        if accuracy_delta > 0:
            key_findings.append(
                f"Correction history improves overall accuracy by {_percent(accuracy_delta)} and top-1 accuracy by {_percent(top1_delta)} on this dataset."
            )
            next_actions.append("Preserve and expand governed correction feedback for the same ambiguity patterns seen in this benchmark.")
        elif accuracy_delta == 0:
            key_findings.append("Correction-aware evaluation does not change the benchmark outcome on this fixture set.")
            risks.append("Existing correction history is not materially changing this benchmark, so coverage may be too narrow or the fixture is already saturated.")
        else:
            risks.append("Correction-aware evaluation performs worse than the baseline on this benchmark, so correction influence should be inspected before wider rollout.")

    if profile_comparison is not None:
        profiles = list(profile_comparison.profiles or [])
        if profiles:
            top_profile = max(profiles, key=lambda item: (item.accuracy, item.top1_accuracy, item.correct_matches))
            key_findings.append(
                f"Best compared profile is {top_profile.profile} with accuracy {_percent(top_profile.accuracy)} and top-1 accuracy {_percent(top_profile.top1_accuracy)}."
            )
        if profile_comparison.recommended_profile:
            key_findings.append(
                f"Current recommendation is to keep {profile_comparison.recommended_profile} as the default profile."
            )
        if profile_comparison.recommendation_reason:
            next_actions.append(profile_comparison.recommendation_reason)
        if not profile_comparison.recommended_profile:
            risks.append("Profile comparison does not show a decisive winner, so broader fixtures are needed before changing the default scoring profile.")

    if not key_findings:
        key_findings.append("No benchmark result payload is loaded yet, so there is no evaluation evidence to interpret.")
    if not risks:
        risks.append("No critical benchmark-specific risk is currently highlighted by the loaded payloads.")
    if not next_actions:
        next_actions.append("Run at least one benchmark, correction-impact check, or profile comparison before drawing tuning conclusions.")
    if benchmark_result is not None and benchmark_result.confidence_by_bucket.get("low_confidence", 0.0) < 0.75:
        next_actions.append("Add more benchmark cases for low-confidence or ambiguous source-target naming patterns.")

    summary = " ".join([
        key_findings[0],
        risks[0],
        next_actions[0],
    ])
    return BenchmarkExplanationResponse(
        title=title,
        summary=summary,
        key_findings=key_findings[:4],
        risks=risks[:4],
        next_actions=next_actions[:4],
        generation_metadata=BenchmarkExplanationGenerationMetadata(
            used_llm=False,
            fallback_used=True,
        ),
    )


def _normalize_benchmark_explanation(
    parsed: dict,
    fallback: BenchmarkExplanationResponse,
) -> BenchmarkExplanationResponse | None:
    payload = fallback.model_dump(mode="json")
    for key in ("title", "summary", "key_findings", "risks", "next_actions"):
        if key in parsed:
            payload[key] = parsed[key]

    try:
        title = str(payload.get("title") or "").strip() or fallback.title
        summary = str(payload.get("summary") or "").strip() or fallback.summary
        key_findings = _normalize_string_list(payload.get("key_findings"), fallback.key_findings)
        risks = _normalize_string_list(payload.get("risks"), fallback.risks)
        next_actions = _normalize_string_list(payload.get("next_actions"), fallback.next_actions)
        return BenchmarkExplanationResponse(
            title=title,
            summary=summary,
            key_findings=key_findings,
            risks=risks,
            next_actions=next_actions,
            generation_metadata=BenchmarkExplanationGenerationMetadata(
                used_llm=True,
                fallback_used=False,
                llm_provider=settings.llm_provider,
                llm_model=settings.llm_model,
            ),
        )
    except Exception:
        return None


def _normalize_string_list(value: object, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if normalized:
            return normalized[:4]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback[:4])


def _percent(value: float | int | None) -> str:
    return f"{round(float(value or 0.0) * 100)}%"