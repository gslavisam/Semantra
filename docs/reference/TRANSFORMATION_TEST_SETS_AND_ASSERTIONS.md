# Transformation Test Sets and Assertions Reference

## Purpose

This document explains how Semantra stores and executes transformation test sets, what each assertion field actually checks, and how to interpret pass or failure output.

It is grounded in the current implementation, primarily:

- `backend/app/services/transformation_test_service.py`
- `backend/app/api/routes/mapping.py`
- `backend/app/models/mapping.py`
- `backend/app/services/persistence_service.py`
- `backend/tests/test_api_smoke.py`

Use this document when you need to understand:

- what a transformation test set contains
- which assertions are available today
- how pass/fail is decided for a case
- what save and run governance rules apply
- what gets persisted versus what is only returned at run time

## Important Framing

Transformation test sets are lightweight regression checks over Semantra preview behavior.

They are not a separate execution engine.

Current implementation runs each test case by calling the same preview pipeline used elsewhere in the product:

- `build_preview(case.source_rows, mapping_decisions)`

Operational meaning:

- test-set results validate preview semantics, not an external ETL runtime
- any preview warning, fallback, classification, or output-value behavior is checked through the real preview path

## Where This Behavior Appears

Current implementation exposes transformation test sets through backend mapping endpoints:

- `POST /mapping/transformation/test-sets`
- `GET /mapping/transformation/test-sets`
- `GET /mapping/transformation/test-sets/{test_set_id}`
- `POST /mapping/transformation/test-sets/{test_set_id}/run`

The capability is documented in product docs, but the implementation surface in the current codebase is API-first.

## Core Data Model

### `TransformationTestAssertion`

Each assertion targets one transformed output column and may specify any combination of:

- `target`
- `expected_status`
- `expected_classification`
- `expected_warning_codes`
- `expected_output_values`

Each field is optional except `target`.

Operational meaning:

- an assertion can check only status
- or only warning codes
- or the full combination of status, classification, warnings, and output values

### `TransformationTestCase`

Each case contains:

- `case_name`
- `source_rows`
- `assertions`

`source_rows` is the synthetic preview input for that case.

### `TransformationTestSetCreateRequest`

Each saved test set contains:

- `name`
- `mapping_decisions`
- `cases`

The saved mapping decisions are the same governed decisions the preview pipeline will use at run time.

## What the Runner Actually Does

For each test case, Semantra:

1. runs preview using the saved `mapping_decisions` and the case `source_rows`
2. finds the transformation preview whose `target` matches each assertion target
3. evaluates every specified assertion field
4. records failure messages for every mismatch

The runner returns, per case:

- `passed`
- `failures`
- `preview`
- `transformation_previews`

This is important because even a failed case still returns the actual preview output that caused the failure.

## Assertion Semantics

### Missing asserted preview

If the runner cannot find a transformation preview for the asserted target, the case records:

- `Missing transformation preview for target '<target>'.`

This usually means:

- the target is wrong for the saved mapping decisions
- the mapping decision never produced a preview entry for that target

### `expected_status`

If provided, this must exactly match the preview `status`.

Current possible values are:

- `direct`
- `validated`
- `fallback`

Any mismatch produces a failure message naming both expected and actual status.

### `expected_classification`

If provided, this must exactly match the preview `classification`.

Current relevant emitted values are:

- `direct`
- `safe`
- `risky`

Any mismatch produces a failure message naming both expected and actual classification.

### `expected_warning_codes`

If provided, the runner builds:

- `actual_warning_codes = [warning.code for warning in transformation_preview.warnings]`

and compares it to the expected list using exact list equality.

Operational consequence:

- this is not a loose contains check
- order matters
- omissions matter
- extra warning codes also fail the assertion

This is intentionally strict and makes warning-model regressions visible.

### `expected_output_values`

If provided, the runner collects target-column values from the preview rows and compares them row by row.

Current normalization is strict but simple:

- `None` becomes `""`
- all other values become `str(value)`

Operational consequence:

- row order matters
- string representation matters
- null handling is normalized only through the `None -> ""` conversion

This makes output assertions easy to write, but still precise enough to catch changed preview behavior.

## Case and Set Pass Rules

### Case pass

A case passes only when it records no failures.

If any asserted field mismatches, the case result is:

- `passed = false`

and the case retains all failure messages.

### Test-set pass

The whole test set passes only when all case results pass.

Current run response includes:

- `passed`
- `total_cases`
- `passed_cases`
- `case_results`

Interpretation:

- `passed_cases == total_cases` means the test set passed cleanly
- any lower value means at least one case failed and should be inspected through its detailed preview output

## Governance Rules

Current rules are strict:

- saving a transformation test set requires all active mapping decisions to be `accepted`
- running a saved transformation test set also requires all active mapping decisions to be `accepted`
- create/list/detail/run endpoints are admin-gated

If non-accepted decisions exist, the API returns a `409` with the same governance-style block reason used by other governed output surfaces.

Important distinction from preview:

- plain preview remains advisory
- transformation test-set save and execution are treated as governed artifact flows

## Persistence Model

When a test set is saved, current implementation persists:

- `mapping_decisions`
- `cases`
- `version`
- `created_at`
- `mapping_count`
- `case_count`

Versioning behavior is name-based:

- saving another test set with the same `name` increments `version`

Current list/detail behavior:

- list returns record-level metadata
- detail returns metadata plus full `mapping_decisions` and `cases`

Current run behavior:

- run results are returned immediately in the API response
- run results are not persisted as a separate historical ledger

## Concrete Scenarios

### Scenario 1. Clean pass on safe transformation

The backend smoke tests currently include a passing example:

- mapping: `email -> customer_name`
- transformation splits the email local part, replaces dots with spaces, and title-cases the result
- case rows include values such as `ana.markovic@example.com`

Expected assertions:

- `expected_status = validated`
- `expected_classification = safe`
- `expected_warning_codes = []`
- `expected_output_values = ["Ana Markovic", "Marko Petrovic"]`

Why this is useful:

- it shows the ideal green-path case
- the transformation executes cleanly
- preview output values are asserted directly, not only status flags

### Scenario 2. Output mismatch failure

The smoke tests also include a failing example where the expected output value is intentionally wrong.

Behavior:

- run returns `passed = false`
- `passed_cases = 0`
- the case failure list includes a message beginning with `Expected output values ...`

Why this matters:

- the runner is diagnostic, not only binary
- it tells you exactly which asserted dimension drifted

### Scenario 3. Governance block on unresolved decisions

The smoke tests cover both save-time and run-time blocks when a mapping decision is still `needs_review`.

Behavior:

- save is rejected with `409` if the submitted mapping decisions are not all accepted
- run is also rejected with `409` if a persisted test set contains non-accepted decisions

Why this matters:

- a transformation test set is treated as a governed artifact, not just an exploratory convenience

## How to Read Failures Efficiently

When a case fails, inspect in this order:

1. `failures`
2. `transformation_previews`
3. `preview`

Reason:

- `failures` tells you which assertion dimension broke
- `transformation_previews` shows the exact preview status, warnings, and before/after samples for the asserted target
- `preview` shows the row-level output values that fed the output assertion

## Relationship to Other References

Use this document together with:

- `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md` when a failing assertion involves warning codes, fallback, or preview classification
- `docs/reference/MAPPING_SIGNALS_AND_SCORING.md` when the saved mapping decisions themselves changed because upstream mapping selection changed