# Mapping Signals and Scoring Reference

## Purpose

This document is the detailed reference for how Semantra computes mapping scores, how confidence labels are derived, and where bounded LLM validation can change the outcome.

It is intentionally grounded in the current implementation, primarily:

- `backend/app/services/mapping_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/core/config.py`
- `backend/app/models/mapping.py`

Use this document when you need to understand:

- what each signal means
- how the final score is computed
- why a candidate is `high`, `medium`, or `low`
- when the LLM is consulted
- what happens when the LLM disagrees with the final selected target

## Important Framing

The Semantra mapping score is:

- a normalized heuristic score in the `0..1` range
- a ranking and review-prioritization signal
- not a calibrated probability of correctness

This matters operationally:

- a higher score means the candidate has stronger evidence relative to the current scoring model
- it does not mean the mapping is guaranteed to be correct
- review and governance rules still matter even for high-confidence results

## Output Model

For each `source -> target` candidate, Semantra computes:

- `signals`
- a normalized `confidence` score
- a `confidence_label`
- explanation lines
- optional canonical details
- optional LLM recommendation data

The exposed signal fields are:

- `name`
- `semantic`
- `knowledge`
- `canonical`
- `pattern`
- `statistical`
- `overlap`
- `embedding`
- `correction`
- `llm`

## Score Profiles And Weights

Semantra no longer relies on a single hardcoded global weight vector.

The active profile is selected through `SEMANTRA_SCORING_PROFILE` in `backend/.env`.
Available built-in profiles are:

- `balanced`
- `schema_only`
- `data_rich`
- `canonical_first`
- `description_priority`

The default `balanced` profile preserves the original runtime behavior:

| Signal | Weight |
|---|---:|
| `name` | `0.20` |
| `semantic` | `0.12` |
| `knowledge` | `0.10` |
| `canonical` | `0.05` |
| `pattern` | `0.20` |
| `statistical` | `0.15` |
| `overlap` | `0.10` |
| `embedding` | `0.12` |
| `correction` | `0.10` |
| `llm` | `0.05` |

Profile intent:

- `balanced`: current general-purpose default for mixed source/target mapping
- `schema_only`: emphasizes lexical, semantic, knowledge, and canonical evidence when instance-level data is sparse
- `data_rich`: emphasizes value-shape, overlap, and statistical compatibility when representative samples exist
- `canonical_first`: increases `knowledge` and `canonical` influence for concept-centric or canonical-heavy mapping programs
- `description_priority`: emphasizes semantic + knowledge context when schema metadata descriptions/types are available and row-level evidence is limited

Auto-enable behavior:

- in schema-spec style target cases (`row_count == 0` with metadata-described columns), Semantra can auto-enable description-priority scoring for that run

Optional fine-tuning can be applied with `SEMANTRA_SCORING_WEIGHT_OVERRIDES` as a JSON object, for example:

```json
{"knowledge": 0.2, "canonical": 0.15}
```

These weights still do not mean every signal is always active.

## Signal Meanings

### `name`

Lexical similarity between source and target field names.

Current implementation combines:

- fuzzy similarity between normalized names
- Jaccard overlap over tokenized names

Interpretation:

- strong when physical field names look very similar
- weaker when names differ strongly even if business meaning is still related

### `semantic`

Semantic similarity after normalization and metadata-driven token expansion.

Current implementation uses semantic token sets built from:

- normalized field meaning
- metadata knowledge token expansion

Interpretation:

- strong when business meaning matches even if literal field names differ
- especially useful for abbreviations and business synonyms

### `knowledge`

Alignment derived from the metadata knowledge layer.

Interpretation:

- strong when built-in metadata knowledge or active overlays explicitly support the match
- often one of the strongest non-lexical reasons for a candidate to rise

### `canonical`

Alignment through shared canonical business concepts.

Interpretation:

- strong when source and target resolve toward the same canonical concept
- especially important for canonical-first and concept-aware review flows

### `pattern`

Pattern similarity between detected value shapes.

Examples:

- emails
- dates
- identifier-like strings
- codes

Interpretation:

- strong when value shapes are compatible even if names are weak

### `statistical`

Compatibility across simple column statistics.

Current implementation compares:

- `unique_ratio`
- `null_ratio`
- average length

Interpretation:

- useful when distributions and field behavior look compatible
- should be treated as supporting evidence, not business proof by itself

### `overlap`

Representative sample-value overlap.

Interpretation:

- only active when both sides have representative sample values
- strong when sampled values visibly overlap
- naturally absent in schema-only cases

### `embedding`

Embedding-based semantic similarity.

Interpretation:

- only active when an embedding provider is configured
- acts as an additional semantic hint, not as the primary scoring path

### `correction`

Historical signal from durable review feedback and promoted reusable rules.

Interpretation:

- positive when past review supported the candidate
- negative when history repeatedly rejected or overrode away from the candidate
- stronger when reusable promoted rules exist

For dataset-level measurement of how this signal changes benchmark outcomes, see `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

### `llm`

Bounded LLM validation signal.

Interpretation:

- not part of the first-pass heuristic score
- only added if the LLM is actually consulted and returns a valid recommendation inside the allowed candidate set

## Active vs Inactive Signals

Semantra normalizes over active signals, not over the full weight table every time.

This matters because some signals are structurally unavailable in some scenarios:

- `overlap` is inactive when representative sample values do not exist on both sides
- `embedding` is inactive when embeddings are disabled
- `correction` is inactive when no relevant durable review history exists
- `llm` is inactive unless bounded LLM validation actually runs and returns a valid decision

Operational consequence:

- a schema-only case is not unfairly punished just because no overlap signal exists
- a no-history case is not penalized for missing correction signal

## Final Score Formula

For the active signals only, Semantra computes a weighted average and clamps the result into `0..1`.

Conceptually:

$$
raw\_score = \sum_{i \in A}(signal_i \cdot weight_i)
$$

$$
final\_score = clamp\left(\frac{raw\_score}{\sum_{i \in A} weight_i}, 0, 1\right)
$$

Where:

- $A$ is the set of active signals for that candidate
- each signal value is already normalized to `0..1`
- the final score is rounded and returned as the candidate confidence

## Runtime Confidence Calibration

After the weighted normalization above, Semantra applies bounded runtime calibration rules in the current implementation.

### 1. Strong identifier consensus hard-cap

If business/value/pattern/LLM evidence all align strongly, the score is forced to `1.0`.

### 2. SAP context boosts

When SAP table+field context and exact canonical-code evidence are present, additive boosts are applied.

### 3. SAP business anchor floor

For strong SAP business anchors, weak heuristic dilution is bounded by a minimum floor.

Operational meaning:

- the weighted average is still the base signal fusion model
- but final score can be calibrated upward in these narrowly-scoped, explicitly-coded consensus/context cases

## Confidence Labels

The current thresholds come from `backend/app/core/config.py`:

- `high_confidence >= 0.85`
- `medium_confidence >= 0.65`
- otherwise `low_confidence`

SAP PIR override thresholds:

- `high_confidence >= 0.82`
- `medium_confidence >= 0.58`

These labels are mapped from score only.

They do not mean:

- approved
- production-safe
- governance-complete

They mean only how strong the current ranking evidence is.

## Automatic Status Mapping

For selected heuristic mappings:

- score `>= auto_accept_threshold` becomes initial status `accepted`
- score below `auto_accept_threshold` becomes initial status `needs_review`

Current default threshold:

- `auto_accept_threshold = 0.75`

SAP PIR override:

- `sap_pir_auto_accept_threshold = 0.72`

This is a convenience for the review loop, not a governance override.

## Canonical Lock Behavior

Semantra has a special case for strong canonical concept matches.

A candidate is treated as a strong canonical concept lock when:

- the target resolves as a canonical concept id
- `knowledge >= 0.85`
- `canonical >= 0.6`

When this happens:

- weak physical field-name evidence should not dilute a strong concept match
- `name` is removed from active signals
- `pattern` can also be removed if pattern evidence is absent or disjoint

Why this exists:

- canonical targets represent normalized business concepts, not only physical column labels
- otherwise a semantically correct canonical match could be unfairly penalized by weak lexical similarity

Additional strong-concept deemphasis (current implementation):

- in strong concept-lock situations with weak physical evidence, Semantra can also deemphasize:
	- `name` (weak lexical evidence)
	- `pattern` (very weak pattern alignment)
	- `overlap` (very weak sample overlap)

These are bounded rules and do not replace the main weighted scoring model.

## Candidate Explanations

The trust layer explanations are derived from the signal profile.

Typical explanation families include:

- strong canonical concept lock
- strong pattern alignment
- semantic token alignment
- metadata knowledge alignment
- canonical alignment
- lexical similarity
- sample overlap
- statistical compatibility
- embedding reinforcement
- reusable rule influence
- historical correction influence or penalty

Every candidate also gets a final signal breakdown line that prints the concrete numeric values.

## Where the LLM Fits

The LLM is not the first-pass mapper.

The implemented model is:

- deterministic heuristic ranking first
- bounded LLM validation second
- only on selected candidates and only in selected cases

The LLM sees a closed candidate set, not the full target schema.

That is one of the most important product rules in Semantra.

## LLM Gate Conditions

The LLM is consulted only when `should_run_llm_validation(...)` returns `True`.

### Case 1. Standard ambiguity band

By default, the LLM runs when the top heuristic score is inside:

- `llm_gate_min_score = 0.3`
- `llm_gate_max_score = 0.75`

So the common ambiguity condition is:

$$
0.3 < top\_score < 0.75
$$

Interpretation:

- obvious strong matches should stay deterministic
- very weak matches should not be rescued by free-form AI guessing
- the LLM is used mainly where heuristic evidence is plausible but ambiguous

### Case 2. Close strong canonical competitors

If a strong canonical concept lock already exists, the LLM is usually skipped.

Exception:

- if another strong canonical candidate exists within `0.05` score margin

This is the implemented arbitration rule for near-tied strong canonical candidates.

### Case 3. Canonical semantic rescue

There is also a special rescue path for weak canonical naming cases.

The LLM may run when all of the following are true:

- top score is below the standard LLM gate minimum but still not extremely low
- top score is `< 0.3` and `>= 0.2`
- the candidate target name is a canonical concept id
- `semantic >= 0.45`
- `knowledge == 0`
- `canonical == 0`

Interpretation:

- semantic evidence suggests a plausible business-concept match
- but the structured knowledge/canonical signals are still missing
- the LLM is allowed to arbitrate inside the closed candidate set

## What the LLM Can Return

The validator returns a JSON object that includes:

- `selected_target`
- `confidence`
- `reasoning`
- optional `transformation_code`

Allowed target choices are:

- one of the provided candidate target names
- `no_match`

If the LLM returns anything outside that closed set, the result is rejected.

## LLM Acceptance Rules

The LLM result is only accepted if:

- `selected_target` is in the closed candidate set or equals `no_match`
- `confidence` is between `0` and `1`
- if the target is not `no_match`, confidence is at least `llm_min_confidence`
- reasoning is returned as a list

Current threshold:

- `llm_min_confidence = 0.5`

## LLM Outcome Cases

### Outcome A. Valid target recommendation

If the LLM selects a valid candidate target:

- that candidate gets `signals.llm = llm_confidence`
- `llm` becomes an active signal
- the candidate score is recomputed
- the candidate is flagged as `llm_selected`
- explanation lines are extended with LLM reasoning

If this candidate survives the later global assignment step, the selected mapping method becomes:

- `llm_validated`

### Outcome B. `no_match`

If the LLM returns `no_match`:

- the selected mapping becomes `target = None`
- method becomes `llm_validator_no_match`
- confidence becomes `0.0`
- status becomes `needs_review`

This is a real explicit branch in the output model, not only a log message.

### Outcome C. Invalid or unusable LLM response

If the LLM response is invalid, out of schema, out of closed set, or below the minimum confidence threshold:

- the LLM result is rejected
- heuristic ranking remains in force

### Outcome D. Rescue-mode low confidence becomes `no_match`

In canonical semantic rescue mode, if the LLM picks a target but confidence is below `llm_min_confidence`:

- the system rewrites the result to `no_match`

This is a safety rule to prevent weak rescue guesses from looking stronger than they are.

## Global One-to-One Assignment Still Wins

Even after LLM re-ranking, Semantra still performs global one-to-one target assignment across the full schema.

This means a source can go through LLM validation and still end up with a different final selected target.

Two important cases exist:

### Case 1. The LLM-preferred target was assigned elsewhere

If another source wins that target in the global assignment step:

- the current source may receive a different target
- or may remain without a unique target assignment

The selected mapping explanation explicitly says this happened.

### Case 2. Heuristic top candidate differs from global final target

Even without LLM, the global assignment step may pick a different target in order to maximize overall one-to-one coverage.

This is why selected output must be interpreted as:

- candidate ranking evidence
- plus global assignment constraints

not only as "the single top local score".

## Practical Reading Guide

### High score, no LLM

Usually means:

- deterministic evidence was already strong enough
- the case was outside the ambiguity band

Typical interpretation:

- likely straightforward, still reviewable

### Medium score, LLM consulted

Usually means:

- heuristic evidence was plausible but ambiguous
- the LLM arbitrated inside the top candidate set

Typical interpretation:

- read both the signal breakdown and the LLM reasoning

### Low score with `no_match`

Usually means one of two things:

- heuristic evidence was weak
- or the bounded LLM validator explicitly rejected the candidate set

Typical interpretation:

- treat as unresolved mapping work, not as a failed prediction score only

### Strong canonical candidate with weak lexical name similarity

Usually means:

- concept evidence outweighed physical naming mismatch
- the canonical lock rule was active

Typical interpretation:

- this can still be a strong match even if field names do not look similar

## What This Document Does Not Cover

This document covers mapping signals and bounded LLM validation only.

It does not try to fully document:

- transformation preview risk classification
- transformation code generation details
- canonical-gap assistant prompting rules
- benchmark metric formulas

Those can be documented separately if needed.

## Related Docs

- `README.md` for the short product summary
- `PROJECT_OVERVIEW.md` for the broader architecture and product picture
- `docs/reference/workflows.md` for the operational workflow view
- `docs/pilot/REAL_LIFE_PILOT_TEST_PLAN.md` for pilot validation scenarios
- `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md` for output-stage warning and fallback behavior