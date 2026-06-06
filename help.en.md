# Help for the Semantra UI

This document is a practical guide to the current Semantra Streamlit product surface. It is not a full button-by-button reference. Instead, it explains how the main workflows fit together.

## Main navigation

Semantra currently has five top-level areas:

- `Workspace`
- `Catalog`
- `Benchmarks`
- `System`
- `Governance`

Quick terminology note:

- `Canonical Console` is still a key governance surface, but it now lives inside `Governance` rather than as a separate top-level tab
- `System` is the operational successor to the older `Admin / Debug` description

Recommended order for a new session:

1. start in `Workspace`
2. move to `Governance` (`Canonical Console`) only if you need canonical governance or overlay work
3. use `Catalog` when you want reuse or discovery
4. use `Benchmarks` when you want repeatable quality measurement
5. use `System` for runtime, observability, and support tasks

## Sidebar controls

The left sidebar is now a multi-view support surface controlled by `Sidebar view`.

Available sidebar views:

- `System` for connection settings, runtime status, KPI metrics, and the unified status legend
- `WS Copilot` for read-only Workspace context plus bounded question/answer guidance and conversation history
- `WS Brief` for a compact `Now / Risks / Next actions` readout of the current Workspace state
- `Help` for this in-app English reference guide
- `Reference` for deeper technical reference documents loaded from `docs/reference` plus selected presentation references

### `System`

`System` is the operational sidebar view. It includes:

- `API Base URL`
- `Admin Token`
- `Runtime`
- `Operations`
- `Unified Status Legend`
- `Reset flow`

### `API Base URL`

Use this when the backend is not running on the default local URL.

### `Admin Token`

Use this for protected governance, benchmark, catalog, and knowledge flows when the backend requires an admin token.

### `WS Copilot`

Use this sidebar mode when you want bounded help about:

- what each Semantra area or Workspace section does
- what is currently blocking progress in Workspace
- what the next recommended action is
- the current mapping state, once a mapping result exists

It is a guidance surface, not a freeform autonomous agent. Its answers are constrained to app/workflow guidance and the current Workspace context.

### `WS Brief`

Use this when you want the shortest operational readout of the current Workspace session:

- `Now`
- `Risks`
- `Next actions`

### `Help`

This sidebar mode renders the current English help guide directly inside the app so the documentation stays visible while you work.

### `Reference`

This sidebar mode lets you choose an available document from `docs/reference` through a dropdown and read it directly inside the app. It also includes selected presentation-side reference documents such as `docs/presentation/Conceptualization.md`. Use it for deeper technical references such as scoring, preview/codegen warnings, benchmark metrics, canonical stewardship, catalog reuse, workflows, and product framing.

### `Reset flow`

This action is available only in the `System` sidebar view. It clears the active Workspace session state and returns the UI to a clean starting point. It resets transient Workspace data such as uploads, mapping results, analyses, generated artifacts, and sidebar copilot chat history. It does not delete backend data or change the configured connection.

## Workspace

`Workspace` is the main analyst flow. It has four internal sub-tabs:

- `Setup`
- `Review`
- `Decisions`
- `Output`

### `Setup`

Use `Setup` for:

- choosing `Standard` or `Canonical` mode
- choosing `Canonical target intent` in canonical mode when you want canonical-only behavior or a target-aware projection hint
- uploading source and target files in standard mapping mode
- uploading only the source in canonical-only mode
- choosing `Row data` or `Schema spec` when a file looks like a field-per-row specification
- selecting tables when an SQL snapshot contains multiple tables
- optionally enriching the source dataset with companion metadata
- optionally enriching the target dataset with companion metadata in standard mode
- enabling `Use LLM validation` when you want bounded validation inside the ambiguity band
- enabling `Prioritize source descriptions` when source description/type metadata should influence heuristic ranking more strongly
- setting `Canonical candidate pool size` in canonical mode

Use `Standard` when:

- you have a real source and a real target
- you may want separate companion files for both source and target when the uploaded row data lacks descriptions or the SQL DDL is too thin
- you want preview, Pandas/PySpark/dbt generation, and artifact refinement later

Use `Canonical` when:

- you do not yet have a real target dataset
- you want to normalize source fields to business concepts first
- you want a semantic preparation pass before a concrete source-to-target run
- you may still choose a target intent so canonical-first mapping can stay canonical-only or apply a system-aware projection hint
- preview is intentionally unavailable because no concrete target rows exist
- code generation and artifact refinement can still be produced from the current source-to-canonical decisions, including Pandas, PySpark, and dbt-style outputs

### `Review`

Use `Review` to inspect:

- the main `Workspace Copilot` panel with section questions such as `Summarize current mapping state` and `Summarize Review -> Decisions risks`
- trust-layer explanations
- confidence and signal breakdown
- repeated-attention clustering for noisy or repeated review patterns
- LLM notes when validation was used
- per-row `LLM refine` inputs with meaning, negative guidance, sample values, and a refinement instruction
- batch low-confidence LLM refinement for the current review set
- accept/revert handling for LLM-refined row proposals
- an `LLM Decision Proposals` panel for `needs_review` rows
	- it can materialize proposals from existing LLM traces
	- optionally, it can run live bounded LLM fill for rows without cached propositions
	- it does not change active decisions until apply actions are executed in `Decisions`
- canonical path information
- manual canonical override in the Review detail pane, with the selected canonical concept reflected in summary rows and canonical path text
- `Mapping Analysis Overview` for a technical summary of the current mapping state
- optional narration and audio generation for the mapping analysis
- `Review Queue Plan` for queue-level prioritization over the currently filtered review set
- `Selected Mapping Details`, including canonical-mismatch details, source-only concept rows, and target-side concept rows
- canonical-gap suggestion flows for rows that look semantically right but still have missing canonical coverage- manual canonical override selection in the Review details panel, with the selected canonical concept reflected in summary rows and canonical path text- `Gap Queue Summary` for repeated canonical-gap families before you review candidates one by one

This is the main place where you decide whether the engine output makes sense before you persist or generate artifacts.

Important distinction:

- `Mapping Analysis Overview` explains the current mapping state as a technical readout
- `Review Queue Plan` is about review order, clustering, and follow-up for the current queue
- `Gap Queue Summary` applies the same idea specifically to the canonical-gap queue
- `Selected Mapping Details` is the place where source-side and target-side concept tables appear; they are not separate top-level review tabs
- `LLM Decision Proposals` remain advisory until you explicitly apply them in `Decisions`
- the main `Workspace Copilot` panel can now hand you directly into `Decisions` without tripping Streamlit rerun/navigation state errors

### `Decisions`

Use `Decisions` for:

- the main `Workspace Copilot` panel questions such as `What still needs a decision?` and `Am I ready for Output?`
- manual target adjustments
- manual mapping in canonical mode through the virtual canonical target options
- exporting or importing mapping decisions as JSON or Excel
- apply/dismiss workflows for `LLM Decision Proposals` through `Apply safe proposals`, `Proposal source`, `Apply selected proposal`, and `Dismiss selected proposal`
- creating, resuming, and updating draft sessions for shared review/decision persistence
- saving mapping-set versions
- loading and applying previously saved mapping sets
- correction history and reusable-learning flows

Important current rules:

- mapping-set reuse back into Workspace works only for `approved` mapping sets
- corrections become durable only after the review outcome is closed
- `Apply safe proposals` is a conservative batch apply mode, not broad automatic acceptance of AI proposals
- `Apply selected proposal` is a single-proposal action for the currently chosen `Proposal source`
- `Active Decisions` now surfaces decision-origin metadata (`manual_mapping`, `llm_proposal`) when available
- decision-origin audit metadata is now included in decision JSON export/import
- draft sessions let you persist review filters, active decisions, and section context before returning later
- when `Workspace Copilot` suggests a handoff back to `Review` or forward to `Output`, that handoff now uses pending navigation state so it remains rerun-safe

### `Output`

Use `Output` for:

- the main `Workspace Copilot` panel questions `Why is codegen blocked?` and `Explain output gating and warning priority`
- `Generate preview`
- `Generate Pandas code`, `Generate PySpark code`, or `Generate dbt model`
- `Refine with LLM` on an already generated artifact
- saving, listing, or running transformation test sets when decisions are accepted

Important distinction:

- preview is advisory and can be used before final approval
- standard-mode code generation is governance-sensitive and requires accepted active decisions
- transformation test sets are governed artifacts and require accepted active decisions
- canonical mode skips preview but still allows code generation and artifact refinement from active source-to-canonical decisions

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

## Governance

`Governance` is the top-level area for canonical and knowledge governance.

Its main panel is `Canonical Console`, which is the central canonical governance surface.

`Canonical Console` currently has four sub-tabs:

- `Canonical`
- `Knowledge`
- `Overlays & Runtime`
- `Stewardship`

### Canonical / Knowledge / Overlay Cheat Sheet

Quick mental model:

- `Canonical` = stable business language (what a concept means across the company)
- `Knowledge` = system/vendor translation layer (how the same concept appears in SAP/Workday/QAD naming)
- `Overlay` = controlled additive patch (fast alias/context update without changing the base layer)
- `Runtime` = active composition the mapping engine is currently using

Hierarchy and recommendation priority:

1. `Canonical` is the semantic authority
2. `Knowledge` links system terms to canonical concepts
3. `Active Overlay` overrides base knowledge entries in runtime
4. `Runtime` is the effective state used for scoring, candidate ranking, and explainability

When to use what:

- use `Canonical` for durable, business-normalized concepts
- use `Knowledge` for system/domain synonyms and vendor-specific naming
- use `Overlay` to close a specific gap quickly without full canonical authoring
- check `Overlays & Runtime` when you need to confirm what is currently active in the engine

In the recommendation flow (practical):

- during candidate/ranking phases, knowledge and canonical signals contribute to final score together with lexical/semantic signals
- `Overlay` can immediately change recommendation quality because it changes the active runtime signal
- if canonical coverage is still weak, the row usually remains `needs_review` and enters the canonical-gap loop
- in canonical-only mode, canonical signal importance is operationally higher because there is no concrete target dataset

Typical decisions:

- local system-specific issue: start with `Overlay`
- stable and broadly reusable business concept: promote via `Canonical`
- vendor-specific name or synonym: model in `Knowledge`
- unexpected recommendation: inspect runtime/active overlay first, then tune the engine if needed

Use it to:

- browse the canonical concept registry
- see canonical concept count metrics (`Filtered`, `Total`, `With active overlay`, `With context`) aligned with the Knowledge registry style
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
- generate `Workspace Reuse Shortlist` for the current Workspace context
- use `Field Reuse Search` to search only across selected source fields from the active Workspace
- run `Workspace Reuse Fit` for the selected catalog version
- reuse an approved mapping set back into Workspace

Important:

- Catalog works over saved artifacts, not the live review state
- reuse back into Workspace is governance-gated by mapping-set status
- `Workspace Reuse Shortlist` works at whole-activity level, not at per-field subset level
- `Field Reuse Search` adds field-scoped shortlist and overlap inspection, but it does not selectively pull decisions by itself
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

Important:

- `System` is not a replacement for `Governance > Canonical Console`
- write-governance actions remain in their dedicated workflows

## Recommended workflows

### Standard mapping workflow

1. In `Workspace > Setup`, upload source and target.
2. Select tables or `Schema spec` mode if needed, and optionally add source/target companion files.
3. Click `Upload and profile`.
4. Click `Generate mapping`.
5. In `Review`, optionally generate `Mapping Analysis Overview`, use per-row or batch `LLM refine`, then inspect trust-layer output, canonical paths, and any canonical-gap suggestions.
6. If the review queue is large or noisy, use `Review Queue Plan` and, when relevant, `Gap Queue Summary`.
7. In `Decisions`, make manual edits, optionally apply `LLM Decision Proposals`, save a draft session if you need to pause or share state, export a checkpoint, or save a mapping set.
8. In `Output`, use preview first, then code generation when the decisions are accepted, and use transformation test-set flows when needed.
9. If the generated artifact needs polishing, use `Refine with LLM`, then explicitly accept or discard the refinement.

### Canonical-first workflow

1. In `Workspace > Setup`, switch to `Canonical` mode.
2. Upload source row data or a source spec and, if needed, adjust `Canonical candidate pool size`.
3. Optionally add source companion metadata, then click `Upload and profile` and `Generate canonical mapping`.
4. In `Review`, inspect the source -> canonical path and use per-row `LLM refine` when needed.
5. In `Decisions`, you can manually map to canonical options and close any advisory proposal flows when relevant.
6. In `Output`, generate code and use artifact refinement without preview.
7. If you find semantic gaps, continue the governance loop in `Governance` (`Canonical Console`).

### Canonical governance workflow

1. Open `Governance`, then open `Canonical Console`.
2. Refresh the registry, overlay state, and stewardship queue if needed.
3. Open the concept detail or stewardship item you care about.
4. Review status, audit context, and impact preview.
5. Approve, reject, ignore, or promote to glossary when the item is ready.

## Short notes

- The confidence score is a review heuristic, not a probability.
- Scores `>= 0.75` are currently auto-accepted even when the confidence label stays `medium_confidence`.
- Preview is intentionally advisory; it does not mean the mapping is fully approved.
- Durable artifact and execution-like surfaces are governed more strictly than preview.
- The sidebar `WS Copilot` and `WS Brief` surfaces are guidance layers only; they do not auto-apply durable changes.
- The newer bounded AI panels across Review, Benchmarks, and Catalog are also guidance layers only; they do not auto-apply durable changes.
- If the UI state feels inconsistent after multiple experiments, `Reset flow` in the `System` sidebar view is often the fastest recovery path.
- The in-app `Help` sidebar view renders this English guide directly from the repository help file.
- The onboarding `Dismiss` action only hides the hint for the current session and does not modify product data.
- Closing the browser does not automatically restore the full Workspace state the next day; continue through a draft session, saved mapping set, or imported decision checkpoint.

For the detailed reference on signals, score formula, confidence thresholds, and bounded LLM cases, see `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

For the detailed reference on preview status, warning codes, classification, and fallback behavior, see `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

For the detailed reference on benchmark metrics, confidence-bucket interpretation, and correction-impact deltas, see `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

For the detailed reference on transformation test-set structure, assertion rules, and run-result interpretation, see `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

For the detailed reference on Catalog reuse and similarity heuristics, see `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

For the detailed reference on Canonical Console runtime behavior, overlay lifecycle, and stewardship rules, see `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.
