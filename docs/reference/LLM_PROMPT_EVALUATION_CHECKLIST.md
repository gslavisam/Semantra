# LLM Prompt Evaluation Checklist

This document defines the minimum acceptance criteria for changing bounded LLM prompts in Semantra.

Use it together with [LLM_PROMPT_MATRIX.md](LLM_PROMPT_MATRIX.md):

- the prompt matrix tells you where each prompt lives and what contract it uses
- this checklist tells you what has to remain true after you tune a prompt

## How To Use It

For any prompt change:

1. identify the affected surface in [LLM_PROMPT_MATRIX.md](LLM_PROMPT_MATRIX.md)
2. check the static template and dynamic payload builder separately
3. run at least one prompt-shape or contract test for the edited surface
4. run at least one behavior-scoped API or service test for the edited surface when one exists
5. record whether the change improved quality, neutrality, and policy adherence without reducing boundary safety

When opening a PR specifically for bounded prompt changes, use [.github/PULL_REQUEST_TEMPLATE/prompt-change.md](../../.github/PULL_REQUEST_TEMPLATE/prompt-change.md).

## Global Acceptance Criteria

Every bounded prompt change should preserve these invariants:

- output shape remains compatible with the current caller and parser
- prompt stays grounded in the provided payload and product surface
- no new autonomous write, approval, or persistence behavior is implied
- fallback or baseline guardrails remain advisory and do not become the preferred answer to copy
- the prompt does not weaken JSON-only or single-output constraints where they are required
- the prompt does not shift responsibility across bounded stages, for example validator -> transformation generation

## Surface Checklists

### Validator

Pass if all are true:

- selected target always remains inside the closed candidate set or `no_match`
- the prompt still prefers `no_match` over low-evidence guessing
- reasoning is expected to distinguish the chosen target from the strongest rejected alternative
- confidence guidance remains conservative when payload evidence is weak or conflicting
- the prompt does not ask for transformation code

Recommended checks:

- `tests/test_llm_and_evaluation.py -k "validator_prompt"`
- targeted mapping tests that exercise ambiguity-band validation

### Transformation Generator

Pass if all are true:

- the prompt still limits code to the declared runtime objects
- direct mapping can result in empty `transformation_code`
- the prompt prefers the smallest valid change instead of gratuitous transformation logic
- unsupported business cleanup or enrichment is not encouraged
- ambiguity is surfaced via warnings instead of invented logic

Recommended checks:

- `tests/test_llm_and_evaluation.py -k "transformation_prompt"`

### Transformation Spec Generator

Pass if all are true:

- the prompt remains closed to the provided target field set
- the output stays non-executable and business-readable
- no invented target fields are encouraged

Recommended checks:

- `tests/test_llm_and_evaluation.py -k "transformation_spec_prompt"`

### Artifact Refinement

Pass if all are true:

- the prompt still requires a complete rewritten artifact in the expected JSON shape
- instructions favor surgical edits over broad rewrites
- unaffected structure and runtime idioms remain protected
- the prompt does not encourage unnecessary helpers, imports, or dependencies

Recommended checks:

- `tests/test_llm_and_evaluation.py -k "artifact_refinement_prompt"`
- `tests/test_api_smoke.py -k "build_artifact_refinement_prompt"`

### Review Plan

Pass if all are true:

- clusters summarize repeated review patterns instead of restating rows one by one
- overlapping patterns are expected to merge instead of duplicate
- prioritization favors operational blocking impact before raw count
- follow-up actions stay executable inside the current review workflow
- no target remapping or status mutation is suggested

Recommended checks:

- `tests/test_llm_and_evaluation.py -k "review_plan_prompt"`
- `tests/test_api_smoke.py -k "review_plan"`

### Workspace Problem Guidance

Pass if all are true:

- the prompt still asks for in-scope vs partial vs out-of-scope framing
- the first recommended step is immediately actionable in the current workspace state
- later-stage sections are not recommended before prerequisites are named
- the answer stays bounded to existing Semantra capabilities and section names
- no unsupported automation or product features are suggested

Recommended checks:

- `tests/test_llm_and_evaluation.py -k "workspace_problem_guidance_prompt"`
- `tests/test_api_smoke.py -k "workspace_problem_guidance"`

### Catalog Reuse Fit

Pass if all are true:

- the prompt remains explanatory rather than auto-apply oriented
- fit assessment stays grounded in metadata overlap and workspace context
- risks and next actions remain controlled and product-realistic

Recommended checks:

- `tests/test_api_smoke.py -k "reuse_fit"`

### Canonical Gap Suggestion

Pass if all are true:

- the prompt remains bounded to alias reuse, new concept creation, or no action
- new concept creation is still harder than reusing a close existing concept
- no canonical approval or persistence behavior is implied

Recommended checks:

- targeted canonical gap service tests

### Canonical Gap Triage Summary

Pass if all are true:

- the prompt stays queue-summary oriented rather than decision-authoring oriented
- repeated patterns, risks, and next actions are summarized without approving or rejecting proposals
- proposal-state awareness remains intact

Recommended checks:

- `tests/test_api_smoke.py -k "triage_summary"`

### Benchmark Explanation

Pass if all are true:

- the prompt stays grounded in metrics and recommendation fields
- unsupported causal claims are still discouraged
- next actions remain controlled and benchmark-focused

Recommended checks:

- `tests/test_api_smoke.py -k "benchmark_explanation"`

### Spec Recovery

Pass if all are true:

- the prompt remains constrained to provided candidate blocks and header names
- uncertain cases can still resolve to `unknown`
- no invented header names or out-of-contract fields are encouraged

Recommended checks:

- `tests/test_llm_and_evaluation.py -k "spec_recovery_prompt"`
- `tests/test_spec_recovery_service.py`

### Mapping Analysis Overview

Pass if all are true:

- summary remains technical, payload-grounded, and JSON-only
- risks and next actions remain traceable to confidence, canonical, transformation, or explanation evidence
- the prompt does not drift into invented source or target semantics

Recommended checks:

- mapping analysis service tests and any future prompt-shape migration tests

### Mapping Analysis Narration

Pass if all are true:

- output remains one single `<final_script>...</final_script>` block
- narration stays faithful to the supplied overview without new facts
- the response remains suitable for spoken playback instead of written report formatting

Recommended checks:

- mapping analysis narration tests and any future audio/narration regression tests

## Review Record Template

When you revise a prompt, capture this summary in the PR, task log, or session note:

- Prompt surface:
- Static template changed:
- Dynamic payload changed:
- Expected improvement:
- Boundary risks checked:
- Focused tests run:
- Remaining open questions:

## Future Direction

This checklist is intentionally lightweight. A stronger later step would be to pair it with a compact evaluation fixture set per prompt surface so prompt revisions can be graded against stable examples, not only contract tests.