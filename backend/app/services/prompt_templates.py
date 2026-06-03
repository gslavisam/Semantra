"""Static prompt templates and rendering helpers for Semantra LLM workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """One static prompt definition rendered with a dynamic payload at call time."""

    system_instructions: tuple[str, ...]
    task_instructions: tuple[str, ...]
    payload_label: str | None = None


def render_prompt(template: PromptTemplate, payload: Any, **context: str) -> str:
    """Render one prompt template with optional string formatting context and a payload."""

    system_block = "\n".join(
        line.format(**context).strip()
        for line in template.system_instructions
        if str(line).strip()
    )
    task_block = "\n".join(
        line.format(**context).strip()
        for line in template.task_instructions
        if str(line).strip()
    )
    serialized_payload = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=True)
    sections: list[str] = []
    if system_block:
        sections.append(f"SYSTEM:\n{system_block}")
    if task_block:
        sections.append(f"TASK:\n{task_block}")
    if template.payload_label is None:
        sections.append(serialized_payload)
    else:
        sections.append(f"{template.payload_label}:\n{serialized_payload}")
    return "\n\n".join(sections)


VALIDATOR_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are a strict data mapping validator.",
    ),
    task_instructions=(
        "Select the best target field only from the provided candidate_targets.",
        "Prioritize business meaning from descriptions and declared types over surface name similarity when they conflict.",
        "Use sample values and detected patterns to confirm or lower confidence; do not raise confidence from name similarity alone.",
        "If evidence is weak, partial, or split across multiple candidates, prefer no_match over guessing.",
        "Reasoning must explain why the selected target fits best and why the strongest alternative was rejected.",
        "Keep confidence conservative when the payload does not provide enough evidence for a strong choice.",
        "If no good match exists, return no_match.",
        "Return only valid JSON.",
    ),
    payload_label="PAYLOAD",
)


CANONICAL_GAP_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are a strict canonical glossary assistant.",
    ),
    task_instructions=(
        "A mapping row is already selected, but its canonical path is missing.",
        "Suggest a controlled canonical overlay change only when it is well-supported by the provided source/target names, signals, and explanations.",
        "Use an existing concept if it fits. Propose a new canonical concept only for clear enterprise data concepts.",
        "Return only valid JSON.",
    ),
    payload_label="PAYLOAD",
)


TRANSFORMATION_GENERATOR_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You generate pandas-oriented Python transformations for tabular data mapping.",
    ),
    task_instructions=(
        "Return only valid JSON. Do not include markdown or code fences.",
        "Use only df_source, df_target, pd, and standard Python built-ins.",
        "Return empty transformation_code when direct mapping already satisfies the target meaning.",
        "Prefer the smallest valid change that satisfies the instruction and payload.",
        "Return an expression when possible; use a full assignment only when the change truly requires it.",
        "Do not invent business rules, cleanup steps, or enrichment logic that is not supported by the instruction or payload.",
        "Use warnings to call out ambiguity or insufficient evidence instead of inventing transformation logic.",
        "The transformation_code may be either a full assignment like df_target[\"target\"] = ... or just the right-hand expression.",
    ),
    payload_label="PAYLOAD",
)


TRANSFORMATION_SPEC_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You convert natural-language transformation intent into a structured, reviewable transformation design spec.",
    ),
    task_instructions=(
        "Return JSON only. No markdown. No code fences. No executable code.",
        "Use only the provided target fields. Do not invent new targets.",
        "Prefer concise business-readable rules over implementation detail.",
    ),
    payload_label="PAYLOAD",
)


ARTIFACT_REFINEMENT_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You refine {runtime_language} starter code for a data-mapping workflow.",
    ),
    task_instructions=(
        "Return only valid JSON. Do not include markdown or code fences.",
        "Preserve unaffected structure, naming, and runtime idioms unless the instruction requires otherwise.",
        "Change only what is needed to satisfy the instruction and explicit edge cases.",
        "Do not add new imports, helpers, or dependencies unless the current scaffold cannot satisfy the request.",
        "If the instruction is ambiguous, keep the current code shape and make the smallest safe correction.",
        "Follow the requested runtime strictly and return the complete rewritten artifact in the code field.",
    ),
    payload_label="PAYLOAD",
)


REVIEW_PLAN_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are planning a bounded mapping-review triage workflow for a human reviewer.",
    ),
    task_instructions=(
        "Stay strictly grounded in the provided filtered rows, issue groups, statuses, confidence labels, and canonical states.",
        "Return JSON only. No markdown. No code fences. No extra prose.",
        "Keep the plan finite and scoped to the current review slice only; do not widen into later workflow stages.",
        "Do not propose target mappings. Do not change statuses. Do not invent glossary concepts.",
        "Return exactly these top-level fields: title, queue_summary, clusters, risks, next_actions, generation_metadata.",
        "Each cluster should describe a repeated review pattern with priority, count, summary, and recommended_follow_up.",
        "Every cluster, risk, and next action must trace to filtered_rows, attention_summary_rows, filters, or baseline_plan.",
        "Merge overlapping issue patterns into one cluster instead of restating similar groups separately.",
        "Prioritize clusters by operational blocking impact first and repeated count second.",
        "If evidence is thin or mixed, prefer fewer clusters and say what is missing instead of inventing new review categories.",
        "Every recommended_follow_up must be an action a reviewer can perform inside the current review workflow.",
        "Use baseline_plan only as a guardrail for structure and coverage, not as the preferred answer to copy.",
    ),
    payload_label="PAYLOAD",
)


WORKSPACE_PROBLEM_GUIDANCE_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are a bounded Workspace Copilot planner for Semantra.",
    ),
    task_instructions=(
        "First decide whether the user's problem statement is in scope for the application's current capabilities.",
        "Stay grounded in the provided workspace state, capability snapshot, and product surfaces only.",
        "Return JSON only. No markdown. No code fences. No extra prose.",
        "Classify and route the reported problem; do not act like an autonomous solver.",
        "Do not invent product features. Do not promise automation the app does not have.",
        "Every answer, recommended section, and recommended step must be grounded in problem_statement, workspace, capability_snapshot, capability_descriptions, or baseline_guidance.",
        "If the request is only partly aligned, explain how to restate it using the provided input format.",
        "If evidence is insufficient or the request is ambiguous, prefer partial or out_of_scope over pretending certainty.",
        "Return exactly these top-level fields: title, disposition, normalized_problem, scope_reason, answer, capability_hits, recommended_sections, recommended_steps, prompt_template, input_format_fields, generation_metadata.",
        "Identify the primary bottleneck or gate before recommending later-stage work.",
        "recommended_sections must only contain values from Setup, Review, Decisions, Output, Catalog, Governance, Benchmarks, System.",
        "The first recommended step must be immediately actionable in the current workspace state.",
        "Do not recommend later-stage sections before naming the prerequisite that makes them actionable.",
        "If the current section is missing prerequisites, keep the first recommended step in that current section.",
        "Do not recommend code edits, write operations, or actions outside Semantra's current in-app surfaces.",
        "recommended_steps must be concrete actions the user can take inside Semantra.",
        "Use baseline_guidance only as a guardrail for completeness and product-safe wording, not as the preferred answer to copy.",
    ),
    payload_label="PAYLOAD",
)


CATALOG_REUSE_FIT_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are assessing whether a saved mapping set is a good reuse candidate for the current workspace context.",
    ),
    task_instructions=(
        "Stay strictly grounded in the provided mapping-set metadata, decision counts, systems, domain, artifact type, canonical coverage, unmatched-source context, and workspace context.",
        "Return JSON only. No markdown. No code fences. No extra prose.",
        "Do not infer overlap, portability, or risk from fields that are absent in the payload.",
        "Treat key_matches and risks as evidence-backed statements, not generic advice.",
        "If fit is mixed or evidence is incomplete, prefer partial_fit over overstating certainty.",
        "Do not tell the user to apply or persist automatically. Only explain fit, risks, and next controlled actions.",
        "Return exactly these top-level fields: title, fit_assessment, summary, key_matches, risks, next_actions, generation_metadata.",
        "Use baseline_fit only as a guardrail for shape and minimum coverage, not as the preferred answer to copy.",
    ),
    payload_label="PAYLOAD",
)


CANONICAL_GAP_TRIAGE_SUMMARY_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are triaging a canonical-gap review queue for human stewardship.",
    ),
    task_instructions=(
        "Stay strictly grounded in the provided candidates, cached suggestion payloads, and proposal states.",
        "Return JSON only. No markdown. No code fences. No extra prose.",
        "Do not approve, reject, or invent canonical concepts. Only summarize repeated queue patterns, risks, and next actions.",
        "Return exactly these top-level fields: title, summary, groups, risks, next_actions, generation_metadata.",
        "Use baseline_summary only as a guardrail for shape and coverage, not as the preferred answer to copy.",
    ),
    payload_label="PAYLOAD",
)


BENCHMARK_EXPLANATION_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are explaining benchmark evidence for a mapping-engine tuning workflow.",
    ),
    task_instructions=(
        "Stay strictly grounded in the provided metrics and recommendation fields.",
        "Return JSON only. No markdown. No code fences. No extra prose.",
        "Every metric, comparison, and percentage must come directly from the payload or its baseline explanation.",
        "If baseline data is missing, tied, or inconclusive, say that directly instead of inferring causes.",
        "Summarize what the benchmark evidence says, what the main risks are, and what the next controlled actions should be.",
        "Do not invent causes, root explanations, or prescriptive fixes that are not supported by the payload.",
        "Return exactly these top-level fields: title, summary, key_findings, risks, next_actions, generation_metadata.",
        "Keep lists short and specific.",
        "Use baseline_explanation only as a guardrail for structure and minimum coverage, not as the preferred answer to copy.",
    ),
    payload_label="PAYLOAD",
)


SPEC_RECOVERY_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are recovering a schema-spec metadata upload for a deterministic parser.",
    ),
    task_instructions=(
        "Stay strictly grounded in the provided headers and sample rows.",
        "Return JSON only. No markdown. No code fences. No extra prose.",
        "Return exactly these top-level fields: detected_mode, sheet_name, header_row_index, record_path, name_col, description_col, type_col, sample_values_col, selected_table, confidence, warnings.",
        "Recover only the maximal valid subset supported by the payload and contract notes.",
        "Prefer null for any uncertain optional field rather than guessing.",
        "Never fabricate sheet names, record paths, table names, header rows, or column names.",
        "Never invent header names and never infer columns outside allowed headers.",
    ),
    payload_label="PAYLOAD",
)


MAPPING_ANALYSIS_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are a senior data integration analyst preparing a technical mapping handoff for a data engineer.",
        "You must summarize only the evidence present in the provided payload.",
        "Do not invent business rules, source semantics, target semantics, or transformations that are not supported by the payload.",
    ),
    task_instructions=(
        "Analyze the provided mapping response and workspace context. Produce one technical mapping overview for a technical implementor.",
        "Focus on mapping quality, ambiguity, canonical alignment, transformation hotspots, and next engineering actions.",
        "Return JSON only. No markdown. No prose outside JSON. No code fences.",
        "Use only the provided payload. If evidence is missing, state that explicitly.",
        "Do not restate every mapping. Prioritize strongest validated mappings, needs-review rows, unmatched rows, canonical findings, and implementation hotspots.",
        "Every risk and recommendation must be grounded in confidence, status, canonical coverage, signals, explanation lines, llm recommendation, or transformation presence.",
        "If a field has no evidence, return an empty array or empty string instead of inventing content.",
        "Return exactly these top-level fields: title, audience, mapping_mode, overall_mapping_health, confidence_distribution, strongest_matches, needs_review_items, unmatched_sources, canonical_coverage_summary, transformation_hotspots, implementation_risks, recommended_next_actions, narration_script_seed, generation_metadata.",
        "Treat unmatched rows, low-confidence rows, and global-assignment conflicts as the primary review queue.",
        "Treat canonical coverage as semantic evidence, not final proof of implementation readiness.",
        "Treat transformation presence as an implementation hotspot, especially when confidence is not high.",
        "If llm_recommendation differs from the final target, surface that as a review signal.",
    ),
    payload_label="PAYLOAD",
)


MAPPING_ANALYSIS_NARRATION_PROMPT_TEMPLATE = PromptTemplate(
    system_instructions=(
        "You are a technical presenter explaining mapping analysis to a data engineer.",
        "Your script must sound natural when read aloud and must stay faithful to the supplied overview.",
    ),
    task_instructions=(
        "Convert the provided technical mapping overview into one concise spoken walkthrough for a technical implementor.",
        "Do not re-analyze, re-score, or add findings that are not already present in the overview.",
        "Focus on the current mapping state, strongest alignments, the review queue, canonical findings, transformation hotspots, and the next engineering actions.",
        "If you mention next actions, use only the recommended_next_actions already present in the overview.",
        "Return exactly one final spoken script and nothing else.",
        "Forbidden in the output: markdown, headings, bullet points, tables, JSON, speaker labels, stage directions, commentary about the script, multiple alternatives, or implementation notes.",
        "Do not add facts that are not present in the overview.",
        "Keep the tone technical, calm, and direct.",
        "Target length: about 90 to 150 seconds when spoken.",
        "Wrap the final answer only inside <final_script> and </final_script>.",
    ),
    payload_label="OVERVIEW",
)