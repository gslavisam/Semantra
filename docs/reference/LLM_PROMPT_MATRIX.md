# LLM Prompt Matrix

This document is the current reference for Semantra's bounded LLM prompts.

It answers three questions for each prompted surface:

- where the static prompt text lives
- where the dynamic payload is assembled
- what response shape the caller expects back

For the acceptance criteria used when these prompts are revised, see [LLM_PROMPT_EVALUATION_CHECKLIST.md](LLM_PROMPT_EVALUATION_CHECKLIST.md).

## Shared Contract

Most bounded prompts now follow the same contract:

- static instructions live in [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- runtime envelopes are assembled in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- rendered prompts use explicit `SYSTEM`, `TASK`, and a labeled payload section such as `PAYLOAD` or `OVERVIEW`
- planner-style prompts may include a neutral `baseline_*` payload object as a structural guardrail

## Adaptation Policy

External prompt reviews and scorecards are guidance, not drop-in replacements for Semantra contracts.

- Semantra adapts prompt hardening ideas to the current response models and fallback logic instead of replacing schemas blindly.
- If a suggested prompt changes the response shape or product role, treat it as a design input for a later model/API migration rather than a template-only edit.

## Current Hardening Status

- 2026-06-03 Phase 1 adapted: Catalog Reuse Fit, Benchmark Explanation, Spec Recovery, Mapping Analysis Narration
- 2026-06-03 Phase 2 adapted: Review Plan, Workspace Problem Guidance

### Status Labels

- `adapted now`: external prompt-hardening ideas were already translated into Semantra's current response contract and runtime role
- `future migration`: the idea looks useful, but adopting it cleanly would require a response-model, parser, or product-role redesign
- `do not drop-in`: the suggested external prompt conflicts with the current feature purpose and should not be applied directly to this surface

### Adoption Matrix

| Prompt Surface | Status | Reason |
| --- | --- | --- |
| Validator | `future migration` | external guidance shifts this surface toward generic contract validation instead of closed-set target selection |
| Canonical Gap Suggestion | `future migration` | useful ideas exist, but the external prompt narrows a surface that currently supports controlled new-concept proposals |
| Transformation Generator | `do not drop-in` | the external prompt changes the feature from code generation into structured transformation listing |
| Transformation Spec Generator | `future migration` | the external prompt points toward a lower-level execution spec, not the current business-readable design contract |
| Artifact Refinement | `do not drop-in` | the external prompt forbids semantic code changes, which conflicts with the current refinement surface |
| Review Plan | `adapted now` | boundedness, grounding, and anti-drift improvements were adapted to the existing plan schema |
| Workspace Problem Guidance | `adapted now` | routing-only and capability-bounded improvements were adapted to the existing product-aware guidance schema |
| Catalog Reuse Fit | `adapted now` | evidence-first and certainty-limiting improvements were adapted without changing the explanatory response shape |
| Canonical Gap Triage Summary | `do not drop-in` | the external prompt collapses the current queue-summary surface into a much narrower count roll-up |
| Benchmark Explanation | `adapted now` | stronger metric grounding and causal restraint were adapted to the current findings/risks/actions contract |
| Spec Recovery | `adapted now` | maximal-valid-subset and anti-fabrication ideas were adapted to the current parser-replay recovery contract |
| Mapping Analysis Overview | `do not drop-in` | the external prompt is too reductive for the current technical handoff surface |
| Mapping Analysis Narration | `adapted now` | anti-reanalysis and payload-faithfulness were adapted while preserving the spoken-script output contract |

The source of truth for centralized static prompt text remains [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py), but this matrix now mirrors the current static text for easier review.

## Centralized Prompts

### Validator

- Adoption status: `future migration`
- Status reason: the external review points toward a generic contract-validation component, while Semantra's current validator is a closed-set target selector.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are a strict data mapping validator.`
	- Task: select only from `candidate_targets`; prioritize business meaning and declared type over surface name similarity; use sample values and patterns to confirm or lower confidence; prefer `no_match` over guessing when evidence is weak; explain why the selected target won and why the strongest alternative lost; keep confidence conservative; return valid JSON only.
- Dynamic builder: `build_validator_prompt_envelope()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Runtime caller: `call_validator()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Dynamic payload: `source_field`, `candidate_targets`, `rules`, `response_format`
- Response contract: `selected_target`, `confidence`, `reasoning`
- Notes: closed-set only; can return `no_match`; no transformation generation in this step

### Canonical Gap Suggestion

- Adoption status: `future migration`
- Status reason: some stricter matching ideas are reusable, but the external proposal is narrower than the current assistant role, which can also support controlled new-concept suggestions.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are a strict canonical glossary assistant.`
	- Task: work only from the current mapping row and nearest concepts; suggest a controlled overlay change only when well-supported; prefer existing concepts when they fit; propose a new concept only for clear enterprise concepts; return valid JSON only.
- Dynamic builder: `build_canonical_gap_prompt_envelope()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Runtime caller: `call_canonical_gap_assistant()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Dynamic payload: `canonical_gap_candidate`, `nearest_existing_canonical_concepts`, `rules`, `response_format`
- Response contract: `action`, `concept_id`, `display_name`, `aliases`, `confidence`, `reasoning`, `risk_notes`
- Notes: bounded to `existing_concept_alias`, `new_canonical_concept`, or `no_action`

### Transformation Generator

- Adoption status: `do not drop-in`
- Status reason: the external proposal changes this surface from bounded code generation into non-executable transformation enumeration.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You generate pandas-oriented Python transformations for tabular data mapping.`
	- Task: return valid JSON only; use only `df_source`, `df_target`, `pd`, and standard Python built-ins; return empty `transformation_code` when direct mapping is already sufficient; prefer the smallest valid change; prefer expression-only output when possible; do not invent unsupported business rules or cleanup logic; use warnings for ambiguity; full assignment is allowed only when needed.
- Dynamic builder: `build_transformation_generator_prompt_envelope()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Runtime caller: `call_transformation_generator()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Dynamic payload: `source_field`, `target_field`, `user_instruction`, `rules`, `response_format`
- Response contract: `transformation_code`, `reasoning`, `warnings`
- Notes: runs only after target selection; may return empty `transformation_code` when no transform is needed

### Transformation Spec Generator

- Adoption status: `future migration`
- Status reason: the external proposal suggests a more execution-oriented op-spec contract than Semantra's current business-readable transformation design surface.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You convert natural-language transformation intent into a structured, reviewable transformation design spec.`
	- Task: return JSON only; no markdown, code fences, or executable code; use only the provided target fields; do not invent new targets; prefer concise business-readable rules over implementation detail.
- Dynamic builder: `build_transformation_spec_prompt_envelope()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Runtime caller: `call_transformation_spec_generator()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Dynamic payload: `mapping_decisions`, `allowed_target_fields`, `instruction`, `current_spec`, `rules`, `response_format`
- Response contract: `transformation_spec`, `reasoning`, `warnings`
- Notes: closed target set; business rules only, no executable code

### Artifact Refinement

- Adoption status: `do not drop-in`
- Status reason: the external proposal limits refinement to non-semantic cleanup, but Semantra's current refinement surface must support behavior-changing edits when the instruction requires them.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You refine {runtime_language} starter code for a data-mapping workflow.`
	- Task: return valid JSON only; preserve unaffected structure, naming, and runtime idioms; change only what is needed; do not add imports, helpers, or dependencies unless necessary; if ambiguous, keep the current code shape and make the smallest safe correction; return the complete rewritten artifact in the `code` field.
- Dynamic builder: `build_artifact_refinement_prompt_envelope()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Runtime caller: `call_artifact_refinement()` in [backend/app/services/llm_service.py](backend/app/services/llm_service.py)
- Dynamic payload: `artifact_mode`, `current_code`, `mapping_decisions`, `instruction`, `edge_cases`, `reference_excerpt`, `rules`, `response_format`
- Response contract: `code`, `reasoning`, `warnings`
- Notes: full rewritten artifact returned in JSON; tuned for minimal safe edits

### Review Plan

- Adoption status: `adapted now`
- Status reason: external hardening ideas were adapted into the current clustering and review-follow-up contract without changing the response schema.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are planning a bounded mapping-review triage workflow for a human reviewer.`
	- Task: stay grounded in filtered rows and canonical state; return JSON only; keep the plan finite and scoped to the current review slice; do not propose mappings or change statuses; return only the documented top-level fields; make every cluster, risk, and next action traceable to payload evidence; merge overlapping issue patterns; prioritize operational blocking impact before raw count; prefer fewer clusters when evidence is mixed; keep follow-up actions inside the current review workflow; use `baseline_plan` only as a structural guardrail.
- Dynamic builder: `build_review_plan_prompt()` in [backend/app/services/review_plan_service.py](backend/app/services/review_plan_service.py)
- Runtime caller: `build_review_plan()` in [backend/app/services/review_plan_service.py](backend/app/services/review_plan_service.py)
- Dynamic payload: `filters`, `filtered_rows`, `attention_summary_rows`, `baseline_plan`
- Response contract: `title`, `queue_summary`, `clusters`, `risks`, `next_actions`, `generation_metadata`
- Notes: `baseline_plan` is a structural guardrail, not a preferred answer; Phase 2 hardening tightened evidence-traceability and anti-drift behavior without changing the response schema

### Workspace Problem Guidance

- Adoption status: `adapted now`
- Status reason: external routing-only and anti-overreach ideas were adapted while preserving Semantra's richer product-aware guidance response.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are a bounded Workspace Copilot planner for Semantra.`
	- Task: first decide whether the request is in scope; classify and route the problem rather than solving it autonomously; stay grounded in workspace state and product surfaces only; return JSON only; do not invent features, automation, code edits, or write actions outside Semantra; keep every answer, section, and step traceable to payload evidence; if only partially aligned or ambiguous, prefer partial/out_of_scope and help restate the request; identify the primary bottleneck before later-stage work; keep `recommended_sections` inside the allowed section list; make the first step immediately actionable; do not recommend later-stage sections before their prerequisite is named; if prerequisites are missing, keep the first step in the current section; use `baseline_guidance` only as a structural guardrail.
- Dynamic builder: `build_workspace_problem_guidance_prompt()` in [backend/app/services/workspace_copilot_service.py](backend/app/services/workspace_copilot_service.py)
- Runtime caller: `build_workspace_problem_guidance()` in [backend/app/services/workspace_copilot_service.py](backend/app/services/workspace_copilot_service.py)
- Dynamic payload: `problem_statement`, `workspace`, `capability_snapshot`, `capability_descriptions`, `baseline_guidance`, `required_input_format_fields`, `prompt_template`
- Response contract: `title`, `disposition`, `normalized_problem`, `scope_reason`, `answer`, `capability_hits`, `recommended_sections`, `recommended_steps`, `prompt_template`, `input_format_fields`, `generation_metadata`
- Notes: bounded to current product capabilities and section names; Phase 2 hardening tightened routing-only behavior while preserving the existing product-aware response schema

### Catalog Reuse Fit

- Adoption status: `adapted now`
- Status reason: evidence-first and confidence-limiting improvements were adapted to the current explanatory reuse-fit surface.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are assessing whether a saved mapping set is a good reuse candidate for the current workspace context.`
	- Task: stay grounded in mapping-set metadata and workspace context; return JSON only; do not tell the user to apply or persist automatically; explain fit, risks, and next controlled actions only; use `baseline_fit` only as a structural guardrail.
- Dynamic builder: `build_catalog_reuse_fit_prompt()` in [backend/app/services/catalog_reuse_fit_service.py](backend/app/services/catalog_reuse_fit_service.py)
- Runtime caller: `build_catalog_reuse_fit()` in [backend/app/services/catalog_reuse_fit_service.py](backend/app/services/catalog_reuse_fit_service.py)
- Dynamic payload: `mapping_set_detail`, `workspace_context`, `baseline_fit`
- Response contract: `title`, `fit_assessment`, `summary`, `key_matches`, `risks`, `next_actions`, `generation_metadata`
- Notes: explanatory only; no automatic apply/persist guidance

### Canonical Gap Triage Summary

- Adoption status: `do not drop-in`
- Status reason: the external proposal shrinks this surface into a severity count summary and loses the current queue-pattern, risk, and action framing.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are triaging a canonical-gap review queue for human stewardship.`
	- Task: stay grounded in candidates, suggestion payloads, and proposal states; return JSON only; do not approve, reject, or invent concepts; summarize repeated queue patterns, risks, and next actions only; use `baseline_summary` only as a structural guardrail.
- Dynamic builder: `build_canonical_gap_triage_prompt()` in [backend/app/services/canonical_gap_triage_service.py](backend/app/services/canonical_gap_triage_service.py)
- Runtime caller: `build_canonical_gap_triage_summary()` in [backend/app/services/canonical_gap_triage_service.py](backend/app/services/canonical_gap_triage_service.py)
- Dynamic payload: `candidates`, `suggestions`, `proposal_states`, `baseline_summary`
- Response contract: `title`, `summary`, `groups`, `risks`, `next_actions`, `generation_metadata`
- Notes: queue summarization only; does not approve or reject proposals

### Benchmark Explanation

- Adoption status: `adapted now`
- Status reason: stronger metric grounding and reduced causal speculation were adapted to the current benchmark explanation contract.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are explaining benchmark evidence for a mapping-engine tuning workflow.`
	- Task: stay grounded in metrics and recommendation fields; return JSON only; summarize what the evidence says, what the risks are, and what the next controlled actions should be; do not invent unsupported causes; keep lists short; use `baseline_explanation` only as a structural guardrail.
- Dynamic builder: `build_benchmark_explanation_prompt()` in [backend/app/services/benchmark_explanation_service.py](backend/app/services/benchmark_explanation_service.py)
- Runtime caller: `build_benchmark_explanation()` in [backend/app/services/benchmark_explanation_service.py](backend/app/services/benchmark_explanation_service.py)
- Dynamic payload: `dataset_name`, `benchmark_result`, `correction_impact`, `profile_comparison`, `baseline_explanation`
- Response contract: `title`, `summary`, `key_findings`, `risks`, `next_actions`, `generation_metadata`
- Notes: evidence narration only; causal claims must stay payload-grounded

### Spec Recovery

- Adoption status: `adapted now`
- Status reason: maximal-valid-subset and anti-fabrication ideas were adapted without changing the deterministic parser-replay response contract.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are recovering a schema-spec metadata upload for a deterministic parser.`
	- Task: stay grounded in provided headers and sample rows; return JSON only; return only the documented top-level fields; never invent header names or infer columns outside the allowed headers.
- Dynamic builder: `build_spec_recovery_prompt()` in [backend/app/services/spec_recovery_service.py](backend/app/services/spec_recovery_service.py)
- Runtime caller: `recover_spec_layout()` in [backend/app/services/spec_recovery_service.py](backend/app/services/spec_recovery_service.py)
- Dynamic payload: `filename`, `candidate_blocks`, `contract`
- Response contract: `detected_mode`, `sheet_name`, `header_row_index`, `record_path`, `name_col`, `description_col`, `type_col`, `sample_values_col`, `selected_table`, `confidence`, `warnings`
- Notes: bounded helper for deterministic parser recovery, not general document understanding

### Mapping Analysis Overview

- Adoption status: `do not drop-in`
- Status reason: the external proposal would reduce a technical handoff surface into a narrow headline-metrics object.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: senior technical mapping handoff for a data engineer; summarize only evidence present in the payload; do not invent unsupported business rules, semantics, or transformations.
	- Task: produce one technical mapping overview; return JSON only; prioritize strongest validated mappings, needs-review rows, unmatched rows, canonical findings, and implementation hotspots; ground risks and recommendations in confidence, status, canonical coverage, signals, explanations, LLM recommendations, or transformation presence.
- Dynamic builder: `build_mapping_analysis_prompt()` in [backend/app/services/mapping_analysis_service.py](backend/app/services/mapping_analysis_service.py)
- Runtime caller: `build_mapping_analysis_summary()` in [backend/app/services/mapping_analysis_service.py](backend/app/services/mapping_analysis_service.py)
- Dynamic payload: `workspace`, `options`, `derived_overview`, `mapping_evidence`, `canonical_coverage`
- Response contract: structured mapping analysis summary payload
- Notes: centralized through the shared template layer and rendered with a standard `PAYLOAD` section

### Mapping Analysis Narration

- Adoption status: `adapted now`
- Status reason: payload-faithful narration and anti-reanalysis ideas were adapted while preserving the spoken-script output contract.

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: technical presenter for a data engineer; narration must sound natural and stay faithful to the supplied overview.
	- Task: return exactly one concise spoken walkthrough; no markdown, headings, bullet points, JSON, labels, alternatives, or invented facts; keep tone technical, calm, and direct; wrap the result in `<final_script>...</final_script>`.
- Dynamic builder: `build_mapping_analysis_narration_prompt()` in [backend/app/services/mapping_analysis_service.py](backend/app/services/mapping_analysis_service.py)
- Runtime caller: `build_mapping_analysis_narration()` in [backend/app/services/mapping_analysis_service.py](backend/app/services/mapping_analysis_service.py)
- Dynamic payload: compacted mapping analysis overview
- Response contract: one `<final_script>...</final_script>` spoken script
- Notes: centralized through the shared template layer and rendered with an `OVERVIEW` payload label because the output is narration-oriented rather than JSON-oriented

## How To Read This Matrix

- "Static template" means the stable instruction text authored by developers.
- "Dynamic builder" means the code path that turns runtime evidence into the prompt payload.
- "Runtime caller" means the function or service that actually sends the prompt to the configured provider.

If a prompt needs quality tuning, start with the static template first. If the model is making avoidable mistakes because key evidence is missing, then change the dynamic payload builder second.