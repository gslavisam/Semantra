# Transformation Preview and Codegen Warnings Reference

## Purpose

This document explains how Semantra evaluates transformation preview results, how warning codes are produced, and how Pandas code generation handles risky or invalid transformation logic.

It is grounded in the current implementation, primarily:

- `backend/app/services/transformation_service.py`
- `backend/app/services/preview_service.py`
- `backend/app/services/codegen_service.py`
- `backend/app/models/mapping.py`

Use this document when you need to understand:

- what preview `mode`, `status`, and `classification` mean
- what each warning code means
- when fallback to direct mapping happens
- what preview does with rejected or unresolved decisions
- how code generation handles invalid transformation code

## Important Framing

Transformation preview in Semantra is advisory.

That means:

- it is meant to expose behavior and risk before a durable artifact is used
- warning-free preview is useful evidence, but not a governance approval by itself
- preview and code generation are related, but they are not identical stages

## Where This Behavior Appears

The product surfaces this behavior through:

- `Workspace > Output` preview results
- transformation preview objects in the backend response model
- code generation warning objects returned with the generated Pandas artifact
- transformation test-set assertions that can check expected status, classification, and warning codes

## Output Objects

The key preview object is `TransformationPreviewResult`.

For each mapping decision it returns:

- `source`
- `target`
- `mode`
- `status`
- `classification`
- `before_samples`
- `after_samples`
- `warnings`

Warning entries are represented as `TransformationPreviewWarning` and include:

- `code`
- `message`
- `source`
- `target`
- `stage`
- `severity`
- `fallback_applied`
- `details`

The same warning object shape is reused for codegen warnings.

## Preview Modes

The current preview mode values are:

- `direct`
- `custom`

### `direct`

This means no custom transformation code was supplied for the mapping decision.

Behavior:

- preview copies the source column into the target column directly
- preview status is `direct`
- preview classification is also `direct`

### `custom`

This means the mapping decision includes explicit transformation code.

Behavior:

- preview tries to compile and execute the transformation code in a bounded execution environment
- the result may be validated successfully or may fall back to direct mapping depending on errors or unsafe output shape

## Preview Status Values

The current preview status values are:

- `direct`
- `validated`
- `fallback`

### `direct`

Used when there is no custom transformation code.

Interpretation:

- Semantra did not need to validate a custom expression
- the column is previewed as a straight copy

### `validated`

Used when custom transformation code was supplied, compiled, executed, and produced a usable target column without forcing fallback.

Interpretation:

- custom code ran successfully at preview time
- warnings may still exist even in `validated` status

### `fallback`

Used when custom transformation logic could not be trusted or executed safely, and the system fell back to direct mapping.

Typical causes:

- missing source column
- syntax error
- runtime error
- row count mismatch

Interpretation:

- the custom transformation did not survive preview validation
- the preview output shown for that column is direct mapping, not the original custom logic

## Preview Classification Values

The current classification values are:

- `direct`
- `safe`
- `risky`
- `custom`

In current implementation, the actual preview classifier behaves as follows:

- if `mode == direct`, classification is `direct`
- if `mode != direct` and `status == validated` and there are no warnings, classification is `safe`
- otherwise classification is `risky`

Operational meaning:

- `direct`: no custom logic was involved
- `safe`: custom logic validated cleanly and produced no warnings
- `risky`: custom logic produced warnings or required fallback

Note:

- the literal enum still includes `custom`, but the current classifier path emits `direct`, `safe`, or `risky`

## Bounded Execution Environment

Custom transformation code runs inside a restricted execution context.

Available helpers include only a small safe builtin set:

- `bool`
- `float`
- `int`
- `len`
- `max`
- `min`
- `str`

And the execution context exposes:

- `pd`
- `df_source`
- `df_target`

This is important because preview validation is not intended to run arbitrary unrestricted Python logic.

## Warning Stages

Warning objects carry a `stage` value.

The current stages are:

- `preview`
- `codegen`

Meaning:

- `preview` warnings come from transformation execution or validation in the preview pipeline
- `codegen` warnings come from generation of the Pandas artifact

## Warning Severity

The current severities are:

- `warning`
- `error`

General rule:

- `error` usually means fallback was applied or generated code had to be downgraded
- `warning` usually means execution succeeded but something potentially risky happened

## Warning Code Reference

The current warning codes are:

- `syntax_error`
- `runtime_error`
- `missing_source_column`
- `null_expansion`
- `type_coercion`
- `row_count_mismatch`
- `skipped_rejected_mapping`

### `missing_source_column`

Stage:

- `preview`

Produced when:

- the mapping decision references a source column that is not present in the current preview input frame

Behavior:

- preview result is marked `fallback`
- classification becomes `risky`
- direct mapping fallback is recorded

Typical interpretation:

- the decision references stale or invalid source metadata relative to the current dataset

### `syntax_error`

Stage:

- `preview`
- `codegen`

Produced when:

- the transformation statement fails Python compilation

Preview behavior:

- preview falls back to direct mapping
- status becomes `fallback`
- classification becomes `risky`

Codegen behavior:

- generated artifact still returns code
- the invalid transformation is replaced by direct mapping code
- warning severity is `error`
- `fallback_applied` is `true`

Typical interpretation:

- the custom transformation is not syntactically valid Python/Pandas logic in its current form

### `runtime_error`

Stage:

- `preview`

Produced when:

- compiled transformation code raises an exception during execution

Behavior:

- preview falls back to direct mapping
- status becomes `fallback`
- classification becomes `risky`
- warning details include exception type and statement

Typical interpretation:

- syntax was valid, but the logic failed when executed against actual preview data

### `row_count_mismatch`

Stage:

- `preview`

Produced when:

- the transformation result produces a target series whose row count differs from the source preview frame

Behavior:

- preview falls back to direct mapping
- status becomes `fallback`
- classification becomes `risky`

Why it matters:

- Semantra expects preview transformations to preserve row alignment for field-level mapping preview

### `null_expansion`

Stage:

- `preview`

Produced when:

- the transformation result contains more nulls than the source series

Behavior:

- preview can still stay `validated`
- classification becomes `risky` because warnings exist
- no forced fallback is applied

Typical interpretation:

- the transformation ran, but it may be dropping or failing to derive values for some rows

### `type_coercion`

Stage:

- `preview`

Produced when:

- the semantic dtype label changes between source and transformed result

Behavior:

- preview can still stay `validated`
- classification becomes `risky` because warnings exist
- no forced fallback is applied

Typical interpretation:

- the transformation changed the data type category, such as string to numeric or string to datetime
- this is often intentional, but it is important to surface explicitly

### `skipped_rejected_mapping`

Stage:

- `codegen`

Produced when:

- a mapping decision has status `rejected`

Behavior:

- the rejected mapping is omitted from generated code
- code generation continues for the remaining decisions

Typical interpretation:

- codegen respects review decisions rather than silently emitting code for rejected mappings

## Preview Pipeline Behavior by Case

### Case 1. No custom transformation code

Behavior:

- direct source-to-target copy
- `mode = direct`
- `status = direct`
- `classification = direct`
- no transformation warnings unless the broader preview row receives aggregated warnings from other sources

### Case 2. Custom code compiles and runs cleanly

Behavior:

- `mode = custom`
- `status = validated`
- `classification = safe`
- `before_samples` and `after_samples` expose the transformation effect

### Case 3. Custom code compiles and runs, but with warnings

Examples:

- `null_expansion`
- `type_coercion`

Behavior:

- `mode = custom`
- `status = validated`
- `classification = risky`

This is an important distinction:

- the transformation is still usable in preview
- but the system is explicitly telling the analyst that the behavior deserves review

### Case 4. Custom code fails validation or execution

Examples:

- `syntax_error`
- `runtime_error`
- `row_count_mismatch`
- `missing_source_column`

Behavior:

- `mode = custom`
- `status = fallback`
- `classification = risky`
- direct mapping output is shown instead of the custom result

## Preview Row Warnings vs Transformation Warnings

Semantra exposes warnings in two related but different places.

### Transformation-level warnings

These live inside `transformation_previews`.

Use them when you want:

- exact warning codes
- source/target-specific details
- fallback metadata
- before/after sample context

### Row-level preview warnings

These live inside each preview row.

They are aggregated user-facing warning strings built from:

- missing source-column checks for accepted preview decisions
- warning messages from transformation preview results

Use them when you want:

- quick visible per-row caution in the output preview table

Use `transformation_previews` when you need precise diagnostic detail.

## How Rejected and Needs-Review Decisions Behave

### Preview

Preview includes all mapping decisions except those explicitly marked `rejected`.

That means:

- `rejected` decisions are excluded from preview transformation execution
- `needs_review` decisions are still previewed

This matches the product rule that preview is advisory.

Preview also returns:

- `unresolved_targets`

These are targets from mapping decisions whose status is `needs_review`.

Interpretation:

- the preview can still be useful even while unresolved decisions remain
- but the response clearly surfaces that review is not finished

### Code generation

Code generation skips only `rejected` mappings.

For each skipped rejected decision it emits:

- `code = skipped_rejected_mapping`
- `stage = codegen`

## Codegen-Specific Behavior

Code generation always tries to emit a usable Pandas artifact.

For each non-rejected decision:

- if no custom code exists, direct mapping code is generated
- if custom code exists, the generated statement is compiled first
- if compilation fails, direct mapping code is emitted instead and a `syntax_error` warning is returned

Important distinction from preview:

- codegen does not execute the transformation logic against data
- it only validates syntactic compilability of the emitted statement

So:

- runtime issues appear in preview, not in codegen
- syntax issues can appear in both preview and codegen

## Transformation Test Sets

Transformation test-set assertions can validate:

- expected preview status
- expected preview classification
- expected warning codes
- expected output values

This makes the preview warning model testable as a lightweight regression surface.

For the full reference on test-set structure, assertion strictness, persistence, and run interpretation, see `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

## Concrete Scenarios

The examples below are intentionally small and aligned to the current implementation.

### Scenario 1. `null_expansion` without fallback

Input idea:

- source column `cost_center` contains `CC-100`, `100`, `CC-300`
- transformation keeps only values that already match the expected prefix pattern

Example transformation:

```python
df_target["cost_center"] = df_source["cost_center"].where(
	df_source["cost_center"].str.startswith("CC-")
)
```

What happens:

- values that do not start with `CC-` become null
- preview still succeeds because the statement compiles, executes, and preserves row count
- result status stays `validated`
- classification becomes `risky` because warnings exist
- warning code includes `null_expansion`

Why this matters:

- the transformation may be intentionally filtering invalid values
- but the analyst should confirm that extra nulls are expected rather than accidental data loss

### Scenario 2. `type_coercion` without fallback

Input idea:

- source column `net_amount` contains string values such as `100.50`, `220.00`, `0.00`
- transformation converts them into numeric values for downstream arithmetic

Example transformation:

```python
df_target["net_amount"] = pd.to_numeric(df_source["net_amount"], errors="raise")
```

What happens:

- preview succeeds and keeps the transformed numeric series
- row count remains aligned, so no fallback is needed
- result status stays `validated`
- classification becomes `risky` because warnings exist
- warning code includes `type_coercion`

Why this matters:

- type conversion is often the correct business outcome
- Semantra still surfaces it because a semantic type change can affect joins, formatting, and downstream rule logic

### Scenario 3. `syntax_error` with preview and codegen fallback

Input idea:

- the analyst starts writing a datetime conversion but leaves the statement incomplete

Example transformation:

```python
df_target["posting_date"] = pd.to_datetime(df_source["posting_date"]
```

What happens in preview:

- compilation fails before execution starts
- preview status becomes `fallback`
- classification becomes `risky`
- preview emits `syntax_error`
- the shown output falls back to direct source-to-target copy

What happens in code generation:

- codegen also compiles the emitted statement before adding it to the artifact
- the same syntax problem produces a `syntax_error` warning at `stage = codegen`
- generated code is downgraded to direct mapping so the artifact remains usable

Why this matters:

- this is the clearest case where preview and codegen agree
- both stages reject invalid syntax, but only preview would also catch runtime failures on syntactically valid code

### Scenario 4. `runtime_error` with preview fallback

Input idea:

- the transformation tries to derive a numeric ratio from text input
- one of the preview values cannot be converted into a number at execution time

Example transformation:

```python
df_target["discount_rate"] = df_source["discount_rate"].astype(float) / 100
```

What happens:

- the statement compiles, so preview proceeds to execution
- if a row contains something like `N/A` or `unknown`, execution raises an exception
- preview emits `runtime_error`
- status becomes `fallback`
- classification becomes `risky`
- the shown output falls back to direct source-to-target copy

Why this matters:

- this is different from `syntax_error` because the code is structurally valid Python
- the failure is data-dependent and therefore visible in preview, but not in codegen compilation alone

### Scenario 5. `row_count_mismatch` with preview fallback

Input idea:

- the transformation mutates `df_target` into a shorter frame instead of preserving source-row alignment

Example transformation:

```python
df_target["document_id"] = df_source["document_id"]
df_target = df_target[df_target["document_id"].notna()].reset_index(drop=True)
```

What happens:

- the statement can compile and execute
- the resulting target frame now contains fewer rows than the source preview frame
- preview emits `row_count_mismatch`
- status becomes `fallback`
- classification becomes `risky`
- Semantra falls back to direct mapping because field-level preview expects row-preserving output

Why this matters:

- preview transformations are not allowed to silently reshape the dataset
- any logic that behaves more like row filtering than field derivation is treated as unsafe for this surface

## Practical Reading Guide

### `validated` + `safe`

Typical meaning:

- custom transformation executed cleanly
- no surfaced risk flags

### `validated` + `risky`

Typical meaning:

- custom transformation executed
- but Semantra observed a potentially important semantic change

Common reasons:

- null expansion
- type coercion

### `fallback` + `risky`

Typical meaning:

- Semantra could not trust or execute the custom logic
- preview output shown is direct mapping fallback

Common reasons:

- missing source column
- syntax error
- runtime error
- row count mismatch

### codegen warning with usable code

Typical meaning:

- Semantra preserved a usable artifact by degrading to direct mapping or skipping a rejected mapping
- the analyst still needs to inspect the warning list before treating the artifact as ready

## What This Document Does Not Cover

This document covers preview and codegen warning behavior only.

It does not fully document:

- transformation generation prompting
- reusable transformation templates
- transformation test-set governance rules
- mapping score signals and bounded LLM validation

Those are separate concerns.

## Related Docs

- `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`
- `README.md`
- `PROJECT_OVERVIEW.md`
- `docs/reference/workflows.md`