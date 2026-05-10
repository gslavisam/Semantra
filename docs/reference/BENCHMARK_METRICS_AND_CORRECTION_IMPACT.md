# Benchmark Metrics and Correction Impact Reference

## Purpose

This document explains how Semantra computes benchmark metrics, what each returned field means, and how correction impact is measured.

It is grounded in the current implementation, primarily:

- `backend/app/services/evaluation_service.py`
- `backend/app/services/correction_service.py`
- `backend/app/services/mapping_service.py`
- `backend/app/api/routes/evaluation.py`
- `backend/app/models/mapping.py`
- `streamlit_ui/benchmark_views.py`

Use this document when you need to understand:

- what benchmark `accuracy` and `top1_accuracy` actually measure
- how `confidence_by_bucket` is computed
- what correction-impact deltas compare
- how durable correction memory influences benchmark results
- which benchmark flows are saved, governed, or admin-gated

## Important Framing

Benchmark metrics in Semantra are evaluation metrics over benchmark cases with known expected targets.

They are useful for:

- comparing mapping quality over time
- checking regressions after scoring or knowledge changes
- measuring whether durable correction memory is helping or hurting known cases

They are not:

- a replacement for analyst review
- a production SLA metric
- proof that an approved mapping set is semantically correct in every real dataset

## Where This Behavior Appears

The current product surfaces benchmark behavior through:

- `Benchmarks` in the Streamlit UI
- `POST /evaluation/run` for ad hoc benchmark evaluation
- `GET /evaluation/benchmark` for the built-in fixture benchmark
- saved benchmark dataset create/list/run flows under `/evaluation/datasets/*`
- correction-impact measurement under `/evaluation/datasets/{dataset_id}/correction-impact`
- saved benchmark run history under `GET /evaluation/runs`

## Benchmark Case Shape

The evaluation service expects each case to provide:

- `source_columns`
- `target_columns`
- `ground_truth`
- optional `row_count`

At runtime, each case is converted into synthetic `SchemaProfile` objects and evaluated through the normal mapping engine.

Operational consequence:

- benchmark metrics measure the same mapping pipeline used in the product, not a separate evaluator
- any scoring, canonical, correction, embedding, or bounded-LLM behavior active in the mapping engine can influence the result

## Concrete Fixture Examples

The built-in fixture benchmark in `backend/tests/fixtures/mapping_gold.json` currently contains three simple cases.

### Example 1. Phone-like identifier should map to phone target

Fixture shape:

- source field: `cust_ref`
- candidate targets: `customer_id`, `phone_number`
- ground truth: `cust_ref -> phone_number`

Why this case is useful:

- it separates identifier-like naming from actual value pattern evidence
- `customer_id` looks superficially plausible by name alone
- `phone_number` has the stronger sample-value and pattern agreement

What this tests:

- whether pattern and overlap evidence can beat a misleading ID-style alternative

### Example 2. Email alias should map to email target

Fixture shape:

- source field: `client_mail`
- candidate targets: `customer_email`, `customer_phone`
- ground truth: `client_mail -> customer_email`

Why this case is useful:

- it is a clean single-field lexical plus pattern match
- it helps confirm that obvious email evidence lands in the correct confidence bucket

What this tests:

- whether the engine preserves intuitive top-ranked matches in a low-ambiguity case

### Example 3. Multi-field case shows `total_cases` vs `total_fields`

Fixture shape:

- source fields: `primary_phone`, `contact_email`
- target fields: `phone_number`, `email_address`
- ground truth contains two mappings in one case

Why this case is useful:

- it shows that `total_cases` and `total_fields` are not the same thing
- one benchmark case can contribute multiple evaluated mapping outcomes

Structural implication for the shipped fixture:

- `total_cases = 3`
- `total_fields = 4`

If every selected mapping matches ground truth, the resulting headline metrics would be:

- `correct_matches = 4`
- `accuracy = 1.0`
- `top1_accuracy = 1.0`

This is a useful sanity check when reading benchmark output from the built-in fixture.

## What the Evaluator Actually Does

For each benchmark case, Semantra:

1. builds source and target schema profiles from the case payload
2. runs `generate_mapping_candidates(...)`
3. compares the final selected mapping for each source field against `ground_truth`
4. also compares the first ranked candidate in `ranked_mappings` against `ground_truth`
5. aggregates confidence-bucket accuracy from the selected mappings

This yields two related but different views:

- selected-output quality through `accuracy`
- first-ranked candidate quality through `top1_accuracy`

## EvaluationMetrics Fields

The returned `EvaluationMetrics` object contains:

- `total_cases`
- `total_fields`
- `correct_matches`
- `accuracy`
- `top1_accuracy`
- `confidence_by_bucket`

### `total_cases`

The number of benchmark cases evaluated.

### `total_fields`

The number of selected mapping outputs evaluated across all cases.

In current implementation this increments once for each entry in `result.mappings`, which in practice means one evaluated mapping outcome per source field.

### `correct_matches`

The count of final selected mappings whose chosen target exactly matches the case `ground_truth` for that source field.

This uses `result.mappings`, so it reflects the engine's final selected output rather than only the raw local ranking.

### `accuracy`

Computed as:

$$
accuracy = \frac{correct\_matches}{total\_fields}
$$

Interpretation:

- this is the most direct measure of how often Semantra's final selected mapping matched the expected target
- it is the best headline metric when you care about the engine's actual chosen output

### `top1_accuracy`

Computed as:

$$
top1\_accuracy = \frac{top1\_correct}{total\_fields}
$$

Where `top1_correct` increments when the first candidate in `ranked_mappings` matches the expected target.

Important nuance:

- this is not taken from `result.mappings`
- it reflects the best-ranked candidate in the per-source ranking list before you interpret the final globally selected output

Interpretation:

- use this when you want to understand local ranking quality
- compare it against `accuracy` to see whether the final selection layer improved or degraded the raw first-choice result

### `confidence_by_bucket`

This is a dictionary keyed by:

- `high_confidence`
- `medium_confidence`
- `low_confidence`

For each bucket, Semantra computes:

$$
confidence\_by\_bucket[bucket] = \frac{bucket\_correct}{bucket\_total}
$$

using the confidence label of the final selected mapping.

Interpretation:

- this shows whether the current confidence labeling is directionally useful
- ideally, higher-confidence buckets should outperform lower-confidence buckets

## How to Read `accuracy` vs `top1_accuracy`

### `accuracy` lower than `top1_accuracy`

Typical interpretation:

- the local first-choice candidate was often right
- but the final selected output underperformed after later selection constraints or routing decisions

In practice this can point to:

- one-to-one global assignment tradeoffs
- closed-set LLM intervention not improving the case
- `no_match` or final-selection behavior being more conservative than raw ranking

### `accuracy` higher than `top1_accuracy`

Typical interpretation:

- the raw top-ranked candidate was not always the best final choice
- later control layers improved the final selected output

In practice this can happen when:

- a lower-ranked candidate becomes the correct final selection
- bounded validation or global assignment avoids a misleading local first choice

## Correction Impact Measurement

`CorrectionImpactMetrics` compares the same benchmark cases twice:

- `baseline`
- `correction_aware`

### `baseline`

The evaluator runs with correction feedback temporarily disabled using `correction_store.feedback_disabled()`.

Operational meaning:

- durable correction history and reusable correction rules are ignored for this pass
- correction signal strength is effectively zeroed out

### `correction_aware`

The evaluator reruns the same benchmark cases with normal correction feedback enabled.

Operational meaning:

- the mapping engine can use durable correction history and promoted reusable rules
- this is the realistic current behavior of the correction-aware engine

### Delta fields

The correction-impact response also returns:

- `accuracy_delta`
- `top1_accuracy_delta`
- `correct_matches_delta`

They are computed as:

$$
accuracy\_delta = correction\_aware.accuracy - baseline.accuracy
$$

$$
top1\_accuracy\_delta = correction\_aware.top1\_accuracy - baseline.top1\_accuracy
$$

$$
correct\_matches\_delta = correction\_aware.correct\_matches - baseline.correct\_matches
$$

Interpretation:

- positive values mean correction memory improved benchmark outcomes on this dataset
- zero means correction memory had no measurable effect on these cases
- negative values mean historical feedback is now biasing the engine away from benchmark truth

## What Currently Contributes to Correction Strength

The correction signal comes from `correction_store.describe_feedback(source, target)`.

Closed review outcomes only are counted. Current logic uses:

- accepted corrections that confirm `corrected_target == target`
- rejected suggestions where `suggested_target == target`
- accepted corrections that explicitly moved away from a suggested target
- promoted reusable rules that prefer the target
- promoted reusable rules that reject or override away from the target

The current strength formula is:

- accepted correction boost: `+0.06` each, capped at `+0.20`
- rejected/overridden-away penalty: `-0.06` for rejected suggestions and `-0.05` for overridden-away accepted suggestions, capped at `-0.20`
- promoted preferred-rule boost: `+0.18` each, capped at `+0.30`
- promoted rejected/overridden-away rule penalty: `-0.18` each, capped at `-0.30`

The final strength is:

$$
strength = round(boost + rule\_boost - penalty - rule\_penalty, 4)
$$

This strength is then used as `signals.correction` in the mapping engine.

Important mapping consequence:

- the correction signal participates only when relevant history exists
- when active, it uses the normal scoring weight defined in `mapping_service.py`
- today that weight is `0.10`

## Practical Reading Guide for Correction Impact

### Positive delta

Typical meaning:

- saved analyst feedback and promoted rules are helping on benchmark cases that resemble reviewed history

Healthy signs:

- `accuracy_delta > 0`
- `top1_accuracy_delta > 0` or stable
- improvements concentrated in `medium` or `low` confidence areas

### Zero delta

Typical meaning:

- no relevant correction memory applied to these cases
- or correction memory exists but did not materially change ranking outcomes

This is not automatically a problem.

It may simply mean:

- the benchmark dataset does not overlap reviewed history
- reusable rules have not yet been promoted for this pattern family

### Negative delta

Typical meaning:

- historical correction memory is now pulling the engine in the wrong direction for this benchmark set

This deserves investigation of:

- stale accepted corrections
- over-broad promoted reusable rules
- benchmark cases that no longer reflect the current intended target semantics

## Governance and Access Rules

Current product rules include:

- saving the current mapping as a benchmark dataset requires accepted active mapping decisions
- saved benchmark dataset create/list/run flows are admin-gated at the API layer
- correction-impact measurement for saved datasets is admin-gated at the API layer
- saved run history is admin-gated at the API layer

Important distinction:

- `GET /evaluation/benchmark` and `POST /evaluation/run` exist as direct evaluation endpoints outside the saved-dataset UI flow
- saved dataset management and saved run history are the governed operational path surfaced in the product UI

## What Gets Persisted

Current implementation persists:

- benchmark datasets
- saved evaluation runs from `/evaluation/datasets/{dataset_id}/run`

Current implementation does not persist correction-impact results as evaluation-run records.

Operational consequence:

- benchmark run history records normal saved benchmark runs
- correction-impact measurement is returned to the UI but is not currently written into the evaluation-run ledger

## UI-Level Interpretation

The `Benchmarks` tab currently supports:

- saving the current mapping as a benchmark dataset
- loading saved datasets
- running a selected saved benchmark
- measuring correction impact for a selected saved benchmark
- loading benchmark run history

The current UI renders:

- raw benchmark result JSON for the last benchmark run
- a compact correction-impact comparison table
- saved dataset and run-history tables

This means the detailed interpretation burden still mostly lives in documentation and analyst judgment rather than in heavy built-in dashboarding.