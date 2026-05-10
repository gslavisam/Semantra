# Help for the Semantra UI

This document is a practical guide to the current Semantra Streamlit product surface. It is not a full button-by-button reference. Instead, it explains how the main workflows fit together.

## Main navigation

Semantra currently has five top-level areas:

- `Workspace`
- `Canonical Console`
- `Catalog`
- `Benchmarks`
- `Admin / Debug`

Recommended order for a new session:

1. start in `Workspace`
2. move to `Canonical Console` only if you need canonical governance or overlay work
3. use `Catalog` when you want reuse or discovery
4. use `Benchmarks` when you want repeatable quality measurement
5. use `Admin / Debug` for runtime and observability support tasks

## Sidebar controls

### `API Base URL`

Use this when the backend is not running on the default local URL.

### `Admin Token`

Use this for protected governance, benchmark, catalog, and knowledge flows when the backend requires an admin token.

### `Reset flow`

This clears the active Workspace session state and returns the UI to a clean starting point. Use it when you want to start a new scenario without any leftover review state.

## Workspace

`Workspace` is the main analyst flow. It has four internal sub-tabs:

- `Setup`
- `Review`
- `Decisions`
- `Output`

### `Setup`

Use `Setup` for:

- choosing `Standard` or `Canonical` mode
- uploading source and target files in standard mapping mode
- uploading only the source in canonical-only mode
- choosing `Row data` or `Schema spec` when a file looks like a field-per-row specification
- selecting tables when an SQL snapshot contains multiple tables
- optionally enriching the source dataset with companion metadata

Use `Standard` when:

- you have a real source and a real target
- you want preview and Pandas code generation later

Use `Canonical` when:

- you do not yet have a real target dataset
- you want to normalize source fields to business concepts first
- you want a semantic preparation pass before a concrete source-to-target run

### `Review`

Use `Review` to inspect:

- trust-layer explanations
- confidence and signal breakdown
- LLM notes when validation was used
- canonical path information
- `Source -> Concept View`
- `Concept -> Target View`
- canonical-gap suggestion flows for rows that look semantically right but still have missing canonical coverage

This is the main place where you decide whether the engine output makes sense before you persist or generate artifacts.

### `Decisions`

Use `Decisions` for:

- manual target adjustments
- exporting or importing mapping decisions as JSON or Excel
- saving mapping-set versions
- loading and applying previously saved mapping sets
- correction history and reusable-learning flows

Important current rules:

- mapping-set reuse back into Workspace works only for `approved` mapping sets
- corrections become durable only after the review outcome is closed

### `Output`

Use `Output` for:

- `Generate preview`
- `Generate Pandas code`

Important distinction:

- preview is advisory and can be used before final approval
- code generation is governance-sensitive and requires accepted active decisions

If you are using transformations:

- you can enable a suggested transformation
- generate transformation code with the LLM if the runtime is configured
- use a reusable template
- manually write your own code
- only explicitly activated transformations are used by preview and code generation

## Canonical Console

`Canonical Console` is the main canonical governance area.

Use it to:

- browse the canonical concept registry
- filter concepts by name, alias, source system, business domain, and focus
- open concept detail with aliases, contexts, active overlay entries, usage, and audit references
- inspect active overlay summary and overlay lifecycle state
- review the mirrored canonical-gap queue from Workspace
- work with stewardship items for `canonical_gap` and `overlay_promotion`
- promote an overlay alias into the stable glossary when the item is `ready_for_approval`

Important:

- this is no longer just a debug area; it is the main governance console for the canonical layer
- LLMs may suggest, but persistence and promotion still require an explicit human action
- some flows are protected by the admin token

For the detailed reference on canonical runtime behavior, overlay lifecycle, stewardship states, and promote-to-glossary rules, see `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.

## Catalog

`Catalog` is the reuse and discovery surface over saved integration knowledge.

Use it to:

- list and search integrations
- open integration detail
- inspect concept-centric catalog detail
- load mapping-set detail, audit, and diff
- reuse an approved mapping set back into Workspace

Important:

- Catalog works over saved artifacts, not the live review state
- reuse back into Workspace is governance-gated by mapping-set status

For the detailed reference on catalog search, similarity heuristics, and `Reuse in Workspace` behavior, see `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

## Benchmarks

`Benchmarks` is the quality measurement area.

Use it to:

- save the current mapping as a benchmark dataset
- load saved benchmark datasets
- run a selected benchmark
- measure correction impact
- inspect benchmark run history

Important:

- `Save current mapping as benchmark` requires accepted active decisions
- this is for measuring quality and regression behavior, not for everyday mapping review itself

## Admin / Debug

`Admin / Debug` is the operational support surface.

Use it for:

- runtime config inspection
- decision-log inspection
- correction and reusable-rule inspection
- other supporting observability and runtime checks that are not part of the main canonical governance flow

## Recommended workflows

### Standard mapping workflow

1. In `Workspace > Setup`, upload source and target.
2. Select tables or `Schema spec` mode if needed.
3. Click `Upload and profile`.
4. Click `Generate mapping`.
5. In `Review`, inspect trust-layer output, canonical paths, and any canonical-gap suggestions.
6. In `Decisions`, make manual edits, export a checkpoint, or save a mapping set.
7. In `Output`, use preview first, then code generation when the decisions are accepted.

### Canonical-first workflow

1. In `Workspace > Setup`, switch to `Canonical` mode.
2. Upload source row data or a source spec.
3. Click `Upload and profile`, then `Generate canonical mapping`.
4. In `Review`, inspect the source -> canonical path.
5. If you find semantic gaps, continue the governance loop in `Canonical Console`.

### Canonical governance workflow

1. Open `Canonical Console`.
2. Refresh the registry, overlay state, and stewardship queue if needed.
3. Open the concept detail or stewardship item you care about.
4. Review status, audit context, and impact preview.
5. Approve, reject, ignore, or promote to glossary when the item is ready.

## Short notes

- The confidence score is a review heuristic, not a probability.
- Preview is intentionally advisory; it does not mean the mapping is fully approved.
- Durable artifact and execution-like surfaces are governed more strictly than preview.
- If the UI state feels inconsistent after multiple experiments, `Reset flow` is often the fastest recovery path.

For the detailed reference on signals, score formula, confidence thresholds, and bounded LLM cases, see `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

For the detailed reference on preview status, warning codes, classification, and fallback behavior, see `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

For the detailed reference on benchmark metrics, confidence-bucket interpretation, and correction-impact deltas, see `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

For the detailed reference on transformation test-set structure, assertion rules, and run-result interpretation, see `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

For the detailed reference on Catalog reuse and similarity heuristics, see `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

For the detailed reference on Canonical Console runtime behavior, overlay lifecycle, and stewardship rules, see `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.
