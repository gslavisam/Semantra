# Help for the Semantra UI

This document is a practical guide to the current Semantra Streamlit product surface. It is not a full button-by-button reference. Instead, it explains how the main workflows fit together.

## Main navigation

Semantra currently has five top-level areas:

- `Workspace`
- `Canonical Console`
- `Catalog`
- `Benchmarks`
- `System`

Recommended order for a new session:

1. start in `Workspace`
2. move to `Canonical Console` only if you need canonical governance or overlay work
3. use `Catalog` when you want reuse or discovery
4. use `Benchmarks` when you want repeatable quality measurement
5. use `System` for runtime, observability, and support tasks

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
- optionally enriching the target dataset with companion metadata in standard mode
- setting `Canonical candidate pool size` in canonical mode

Use `Standard` when:

- you have a real source and a real target
- you may want separate companion files for both source and target when the uploaded row data lacks descriptions or the SQL DDL is too thin
- you want preview and Pandas code generation later

Use `Canonical` when:

- you do not yet have a real target dataset
- you want to normalize source fields to business concepts first
- you want a semantic preparation pass before a concrete source-to-target run
- preview is intentionally unavailable because no concrete target rows exist
- code generation can still be produced from the current source-to-canonical decisions

### `Review`

Use `Review` to inspect:

- trust-layer explanations
- confidence and signal breakdown
- LLM notes when validation was used
- per-row `LLM refine` inputs with meaning, negative guidance, sample values, and a refinement instruction
- batch low-confidence LLM refinement for the current review set
- accept/revert handling for LLM-refined row proposals
- canonical path information
- `Mapping Analysis Overview` for a technical summary of the current mapping state
- optional narration and audio generation for the mapping analysis
- `Review Queue Plan` for queue-level prioritization over the currently filtered review set
- `Source -> Concept View`
- `Concept -> Target View`
- canonical-gap suggestion flows for rows that look semantically right but still have missing canonical coverage
- `Gap Queue Summary` for repeated canonical-gap families before you review candidates one by one

This is the main place where you decide whether the engine output makes sense before you persist or generate artifacts.

Important distinction:

- `Mapping Analysis Overview` explains the current mapping state as a technical readout
- `Review Queue Plan` is about review order, clustering, and follow-up for the current queue
- `Gap Queue Summary` applies the same idea specifically to the canonical-gap queue

### `Decisions`

Use `Decisions` for:

- manual target adjustments
- manual mapping in canonical mode through the virtual canonical target options
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
- `Generate Pandas code` or `Generate PySpark code`
- `Refine with LLM` on an already generated artifact

Important distinction:

- preview is advisory and can be used before final approval
- standard-mode code generation is governance-sensitive and requires accepted active decisions
- canonical mode skips preview but still allows code generation from active source-to-canonical decisions

If you use refinement:

- the original and refined artifacts are shown side by side
- `Accept refined version` replaces the current generated artifact with the refinement candidate
- `Discard refinement` removes the refinement candidate and keeps the original artifact
- refinement does not become the active artifact until you explicitly accept it

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
- inspect the `Discovery Overview` across source-system -> target-system paths
- open integration detail
- inspect concept-centric catalog detail
- load mapping-set detail, audit, and diff
- use `similar approved integration exists` hints in result browsing
- run `Workspace Reuse Fit` for the selected catalog version
- reuse an approved mapping set back into Workspace

Important:

- Catalog works over saved artifacts, not the live review state
- reuse back into Workspace is governance-gated by mapping-set status
- `Workspace Reuse Fit` is a bounded explanation layer; it does not apply anything automatically, it only explains whether the selected version fits the current Workspace context

For the detailed reference on catalog search, similarity heuristics, and `Reuse in Workspace` behavior, see `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

## Benchmarks

`Benchmarks` is the quality measurement area.

Use it to:

- save the current mapping as a benchmark dataset
- load saved benchmark datasets
- run a selected benchmark
- compare scoring profiles
- measure correction impact
- generate `Benchmark Explanation` for the currently loaded benchmark evidence
- inspect benchmark run history

Important:

- `Save current mapping as benchmark` requires accepted active decisions
- this is for measuring quality and regression behavior, not for everyday mapping review itself
- `Benchmark Explanation` does not change the score or runtime config; it only summarizes the currently loaded evidence and risks

## System

`System` is the operational support surface.

It has two internal sub-tabs:

- `Admin`
- `Debug`

Use it for:

- runtime config inspection
- decision-log inspection
- correction and reusable-rule inspection
- other supporting observability and runtime checks that are not part of the main canonical governance flow

## Recommended workflows

### Standard mapping workflow

1. In `Workspace > Setup`, upload source and target.
2. Select tables or `Schema spec` mode if needed, and optionally add source/target companion files.
3. Click `Upload and profile`.
4. Click `Generate mapping`.
5. In `Review`, optionally generate `Mapping Analysis Overview`, use per-row or batch `LLM refine`, then inspect trust-layer output, canonical paths, and any canonical-gap suggestions.
6. If the review queue is large or noisy, use `Review Queue Plan` and, when relevant, `Gap Queue Summary`.
6. In `Decisions`, make manual edits, export a checkpoint, or save a mapping set.
7. In `Output`, use preview first, then code generation when the decisions are accepted.
8. If the generated artifact needs polishing, use `Refine with LLM`, then explicitly accept or discard the refinement.

### Canonical-first workflow

1. In `Workspace > Setup`, switch to `Canonical` mode.
2. Upload source row data or a source spec and, if needed, adjust `Canonical candidate pool size`.
3. Optionally add source companion metadata, then click `Upload and profile` and `Generate canonical mapping`.
4. In `Review`, inspect the source -> canonical path and use per-row `LLM refine` when needed.
5. In `Decisions`, you can manually map to canonical options.
6. In `Output`, generate code without preview.
7. If you find semantic gaps, continue the governance loop in `Canonical Console`.

### Canonical governance workflow

1. Open `Canonical Console`.
2. Refresh the registry, overlay state, and stewardship queue if needed.
3. Open the concept detail or stewardship item you care about.
4. Review status, audit context, and impact preview.
5. Approve, reject, ignore, or promote to glossary when the item is ready.

## Short notes

- The confidence score is a review heuristic, not a probability.
- Scores `>= 0.75` are currently auto-accepted even when the confidence label stays `medium_confidence`.
- Preview is intentionally advisory; it does not mean the mapping is fully approved.
- Durable artifact and execution-like surfaces are governed more strictly than preview.
- The newer bounded AI panels across Review, Benchmarks, and Catalog are guidance layers only; they do not auto-apply durable changes.
- If the UI state feels inconsistent after multiple experiments, `Reset flow` is often the fastest recovery path.

For the detailed reference on signals, score formula, confidence thresholds, and bounded LLM cases, see `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

For the detailed reference on preview status, warning codes, classification, and fallback behavior, see `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

For the detailed reference on benchmark metrics, confidence-bucket interpretation, and correction-impact deltas, see `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

For the detailed reference on transformation test-set structure, assertion rules, and run-result interpretation, see `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

For the detailed reference on Catalog reuse and similarity heuristics, see `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

For the detailed reference on Canonical Console runtime behavior, overlay lifecycle, and stewardship rules, see `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.
