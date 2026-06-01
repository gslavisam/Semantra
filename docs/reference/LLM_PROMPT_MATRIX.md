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

The source of truth for centralized static prompt text remains [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py), but this matrix now mirrors the current static text for easier review.

## Centralized Prompts

### Validator

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

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are planning a bounded mapping-review triage workflow for a human reviewer.`
	- Task: stay grounded in filtered rows and canonical state; return JSON only; do not propose mappings or change statuses; return only the documented top-level fields; describe repeated patterns as clusters; merge overlapping issue patterns; prioritize operational blocking impact before raw count; keep follow-up actions inside the current review workflow; use `baseline_plan` only as a structural guardrail.
- Dynamic builder: `build_review_plan_prompt()` in [backend/app/services/review_plan_service.py](backend/app/services/review_plan_service.py)
- Runtime caller: `build_review_plan()` in [backend/app/services/review_plan_service.py](backend/app/services/review_plan_service.py)
- Dynamic payload: `filters`, `filtered_rows`, `attention_summary_rows`, `baseline_plan`
- Response contract: `title`, `queue_summary`, `clusters`, `risks`, `next_actions`, `generation_metadata`
- Notes: `baseline_plan` is a structural guardrail, not a preferred answer

### Workspace Problem Guidance

- Static template: [backend/app/services/prompt_templates.py](backend/app/services/prompt_templates.py)
- Static prompt text:
	- System: `You are a bounded Workspace Copilot planner for Semantra.`
	- Task: first decide whether the request is in scope; stay grounded in workspace state and product surfaces only; return JSON only; do not invent features or automation; if only partially aligned, help restate the request; identify the primary bottleneck before later-stage work; keep `recommended_sections` inside the allowed section list; make the first step immediately actionable; do not recommend later-stage sections before their prerequisite is named; if prerequisites are missing, keep the first step in the current section; use `baseline_guidance` only as a structural guardrail.
- Dynamic builder: `build_workspace_problem_guidance_prompt()` in [backend/app/services/workspace_copilot_service.py](backend/app/services/workspace_copilot_service.py)
- Runtime caller: `build_workspace_problem_guidance()` in [backend/app/services/workspace_copilot_service.py](backend/app/services/workspace_copilot_service.py)
- Dynamic payload: `problem_statement`, `workspace`, `capability_snapshot`, `capability_descriptions`, `baseline_guidance`, `required_input_format_fields`, `prompt_template`
- Response contract: `title`, `disposition`, `normalized_problem`, `scope_reason`, `answer`, `capability_hits`, `recommended_sections`, `recommended_steps`, `prompt_template`, `input_format_fields`, `generation_metadata`
- Notes: bounded to current product capabilities and section names

### Catalog Reuse Fit

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