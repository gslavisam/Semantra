# Project Overview

## What Semantra Is

Semantra is a semantic mapping and governance workbench for analyst-guided integration design.

It is built around a deterministic-first loop:

1. ingest source and target structures
2. profile schemas and rank mapping candidates
3. enrich matching with metadata knowledge, canonical concepts, and prior review memory
4. use bounded AI only where it adds explainable value
5. review, refine, preview, benchmark, and persist governed artifacts

The current product is pilot-ready for controlled analyst and stewardship workflows. It is not yet a production ETL runtime, enterprise connector platform, or orchestration engine.

## Product Goal

The goal of Semantra is to make schema mapping:

- explainable
- reviewable
- measurable
- reusable
- improvable through governed feedback

The product does not treat LLMs as an autonomous mapper. Instead, it keeps the main inference path deterministic and uses AI only inside bounded, inspectable surfaces.

## Bounded AI Operating Model

Today, Semantra uses optional AI only in controlled surfaces such as:

- closed-set mapping validation in the ambiguity band
- Mapping Analysis Overview, narration, and audio generation
- transformation generation
- output artifact refinement
- review queue planning
- Workspace Copilot closure/readiness/output guidance across `Review`, `Decisions`, and `Output`
- canonical-gap suggestion and queue summary
- benchmark explanation
- catalog workspace reuse-fit explanation

These surfaces share the same intent:

- they do not auto-approve or auto-apply durable changes
- they expose structured output rather than freeform hidden reasoning
- they stay close to a concrete local workflow step
- they fall back gracefully when the LLM is unavailable or the response is invalid
- when they navigate across Workspace sections, they now do so through rerun-safe pending handoff state rather than by mutating widget-bound active navigation state mid-render

Implementation note:
Bounded prompts now share a common backend envelope with explicit `SYSTEM`, `TASK`, and labeled payload sections. Planner and summarizer prompts also use neutral `baseline_*` payload hints so deterministic fallback content can be used as a guardrail without over-anchoring the model toward copying the fallback verbatim.

## Product Shape Today

Semantra currently consists of:

- a FastAPI backend in `backend/app`
- a Streamlit product UI in `streamlit_app.py` and `streamlit_ui/*`
- a SQLite persistence layer in `backend/semantra.sqlite3`
- file-backed canonical/metadata seed inputs with DB-first runtime loading when the persisted seed is current

The main top-level UI areas are:

- `Workspace`
- `Governance` (including `Canonical Console`)
- `Catalog`
- `Benchmarks`
- `System`

## Core Functional Areas

### 1. Ingestion and schema profiling

Implemented today:

- row-data upload for CSV, JSON, XML, and XLSX
- SQL snapshot upload with explicit table selection for multi-table files
- schema-spec upload where each row represents one field
- source companion metadata enrichment over an existing uploaded source dataset
- target companion metadata enrichment over an existing uploaded target dataset in standard mode

Purpose:

- turn various source/target structure representations into a `SchemaProfile`
- preserve row preview when row data exists
- support schema-only mapping flows when sample rows do not exist yet

Main anchors:

- `backend/app/api/routes/upload.py`
- `backend/app/services/upload_store.py`
- `backend/app/services/spec_upload_service.py`
- `backend/app/services/schema_snapshot_service.py`

### 2. Mapping engine

Implemented today:

- standard source-to-target mapping
- canonical-only source-to-business-concept mapping
- configurable canonical candidate shortlisting before full canonical scoring
- top-k candidate ranking with one-to-one assignment
- signal fusion across lexical, semantic, knowledge, canonical, pattern, statistical, overlap, embedding, correction, and optional LLM inputs
- project/source/target canonical coverage reporting
- async mapping jobs with progress polling, active-job limits, and cancel support

Important behavior:

- confidence is a normalized ranking heuristic, not a calibrated probability
- current thresholds are `high >= 0.85`, `medium >= 0.65`, otherwise `low`
- scores `>= 0.75` are auto-accepted even when the confidence label remains `medium_confidence`
- canonical mode can narrow the initial search to a configurable likely-candidate pool before full scoring; the default UI pool is now `10`
- bounded LLM target validation and bounded transformation generation are now separate steps; the validator selects from the closed target set, and transformation code is generated only after a target has already been chosen

Detailed signal, score, and bounded LLM behavior is documented in `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

Main anchors:

- `backend/app/services/mapping_service.py`
- `backend/app/api/routes/mapping.py`
- `backend/app/services/mapping_job_service.py`
- `backend/app/services/prompt_templates.py`

### 3. Review, explainability, and guided queue support

Implemented today:

- trust-layer explanations and signal breakdowns
- source-to-concept and concept-to-target review views
- per-row LLM mapping refinement with transient meaning/negative/sample/refinement hints
- batch low-confidence LLM refinement plus accept/revert handling for refined row proposals
- opportunistic LLM decision proposal generation for `needs_review` rows
- optional live bounded LLM fill for rows without cached LLM proposition traces
- Mapping Analysis Overview with technical summary, recommended actions, and optional narration/audio
- Review Queue Plan for the currently filtered review set
- grouped review-attention summary for repeated unmatched or low-confidence patterns
- Workspace Copilot `Review -> Decisions` risk/closure summary in both the sidebar `WS Copilot` and the main `Workspace Copilot` panel
- Canonical Gap Suggestions plus Gap Queue Summary for queue-level canonical stewardship guidance

This turns the engine output into an analyst-controlled review surface rather than an opaque guess.

Main anchors:

- `streamlit_ui/workspace_review_views.py`
- `backend/app/services/mapping_analysis_service.py`
- `backend/app/services/review_plan_service.py`
- `backend/app/services/canonical_gap_triage_service.py`

### 4. Decisions, preview, code generation, and artifact refinement

Implemented today:

- manual target adjustment in both standard and canonical workflows
- explicit apply/dismiss flows for `LLM Decision Proposals`
- safe batch apply mode for proposal subsets that pass conservative guardrails
- decision export/import as JSON and Excel
- reusable transformation templates and manual transformation editing
- advisory preview over active mapping decisions
- Pandas and PySpark starter code generation
- structured transformation warnings and fallback behavior
- LLM transformation generation when configured
- output artifact refinement with original vs refined compare and explicit accept/discard actions
- Workspace Copilot `Decisions -> Output` readiness assessment and `Output` gating/warning-priority explanation in both the sidebar and main Workspace panel
- transformation test set save/list/detail/run flows

Important product contract:

- preview is intentionally advisory and can run before all decisions are accepted
- preview remains a standard-mode artifact; canonical mode intentionally skips preview because no concrete target rows exist
- standard-mode code generation and transformation test-set persistence/execution are governance-gated
- canonical mode still supports Pandas/PySpark code generation and artifact refinement from current source-to-canonical decisions
- refinement is guidance only until the user explicitly accepts the refined artifact
- active decisions now surface decision-origin metadata (`manual_mapping`, `llm_proposal`) when available
- decision JSON export/import now includes decision-origin audit metadata
- panel-level `Workspace Copilot` handoff actions are live-browser-validated against Streamlit reruns and no longer throw widget-state mutation exceptions on section handoff

Detailed preview/codegen warning behavior and classification is documented in `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

Detailed transformation test-set assertion and run behavior is documented in `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

Main anchors:

- `backend/app/services/preview_service.py`
- `backend/app/services/codegen_service.py`
- `backend/app/services/transformation_test_service.py`
- `backend/app/services/llm_service.py`
- `backend/app/services/prompt_templates.py`
- `backend/app/api/routes/mapping.py`
- `streamlit_ui/workspace_views.py`

### 5. Mapping-set governance and reuse

Implemented today:

- versioned mapping-set persistence
- status workflow: `draft`, `review`, `approved`, `archived`
- `owner`, `assignee`, and `review_note`
- audit trail and version diff
- approved-only apply/reuse back into Workspace

This is the first durable governance layer around reviewed mapping results.

Main anchors:

- `backend/app/api/routes/mapping.py`
- `backend/app/services/persistence_service.py`
- `streamlit_ui/workspace_decision_views.py`

### 6. Corrections and reusable learning

Implemented today:

- durable correction history
- reviewed correction save flow in the UI
- reusable-rule candidate generation and promotion
- correction impact evaluation against saved benchmark datasets
- correction-aware influence back into ranking

Important current rule:

- only closed review outcomes can become durable learning input

Main anchors:

- `backend/app/services/correction_service.py`
- `backend/app/api/routes/observability.py`

### 7. Canonical layer and overlay lifecycle

Implemented today:

- canonical glossary runtime
- canonical glossary import/export
- knowledge overlay validation, create, list, activate, deactivate, archive, rollback, reload, and reseed flows
- canonical-gap candidate extraction and LLM-assisted suggestion
- approve/reject/ignore/proposal-state handling for canonical-gap stewardship
- overlay-promotion stewardship and explicit promotion to the stable glossary

Important current boundary:

- canonical runtime is DB-first at runtime, but canonical authoring still includes file-backed reseed inputs

Main anchors:

- `backend/app/api/routes/knowledge.py`
- `backend/app/services/metadata_knowledge_service.py`
- `backend/app/services/knowledge_overlay_service.py`
- `backend/app/services/canonical_gap_service.py`

Detailed canonical runtime, overlay lifecycle, and stewardship behavior is documented in `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.

### 8. Canonical Console

Implemented today:

- top-level console for canonical concept registry and governance
- concept detail with aliases, contexts, active overlay entries, catalog usage, and audit references
- canonical registry metrics (`Filtered`, `Total`, `With active overlay`, `With context`) aligned with the Knowledge registry style
- active overlay summary and lifecycle actions
- mirrored canonical-gap queue from Workspace review
- stewardship item detail for `canonical_gap` and `overlay_promotion`
- explicit promote-to-glossary execution flow

Current maturity:

- the core happy-path canonical governance loop is pilot-complete
- remaining work here is stabilization and wider productization rather than missing core flow

Main anchors:

- `streamlit_ui/admin_views.py`
- `backend/app/api/routes/knowledge.py`

### 11. UI shell orientation and guided onboarding

Implemented today:

- compact sidebar operations strip with live workflow KPIs
- unified status legend shared across Workspace and Governance surfaces
- dismissible onboarding hints per top-level area for first-run discoverability

Main anchors:

- `streamlit_ui/shared_views.py`
- `streamlit_app.py`

### 12. Session continuity boundary today

Current behavior:

- browser session state is local UI state and is not automatically resumed across days
- durable continuation is supported through explicit artifacts (saved draft sessions, saved mapping sets, exported/imported decision checkpoints)
- current draft-session restore is intentionally bounded to the stable workspace contract needed for review and decisions; generated outputs are rebuilt instead of blindly replayed

Open productization task:

- deepen the draft/resume model deliberately (scope, conflict handling, sharing, and audit semantics) before introducing auto-resume behavior

### 9. Enterprise Integration Catalog

Implemented today:

- integration list/search/detail APIs
- concept-centric catalog detail
- Streamlit Catalog browse/search/drilldown flows
- discovery overview over source-system -> target-system paths
- similar-approved-integration hints
- approved-only reuse into Workspace
- workspace reuse-fit explanation for the selected catalog version against the current workspace context

Current boundary:

- basic reuse discovery exists
- richer concept/reuse visualization remains open

Main anchors:

- `backend/app/api/routes/catalog.py`
- `backend/app/services/catalog_reuse_fit_service.py`
- `streamlit_ui/catalog_views.py`

Detailed catalog search, similarity, and reuse behavior is documented in `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

### 10. Benchmarks and evaluation

Implemented today:

- built-in and custom benchmark run endpoints
- saved benchmark dataset create/list/run flows
- scoring-profile comparison across predefined profiles
- evaluation run history
- correction-impact measurement
- bounded benchmark explanation over loaded benchmark evidence

Detailed benchmark metric and correction-impact interpretation is documented in `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

Main anchors:

- `backend/app/api/routes/evaluation.py`
- `backend/app/services/evaluation_service.py`
- `backend/app/services/benchmark_explanation_service.py`
- `streamlit_ui/benchmark_views.py`

## Governance Model Today

Semantra already enforces several concrete governance contracts, not just passive statuses.

Implemented backend-enforced rules include:

- only approved mapping sets can be applied or reused in Workspace flows
- standard-mode code generation requires accepted active mapping decisions
- canonical-mode code generation is allowed from active source-to-canonical decisions even before final acceptance
- saving the current mapping as a benchmark requires accepted active decisions
- reviewed corrections require closed review outcomes
- reusable-rule promotion rejects unresolved review states
- canonical-gap approval requires proposal state `ready_for_approval`
- overlay activation requires `validated`
- overlay archive allows only `validated` or `active`
- transformation test-set save and run require accepted active decisions

Intentional distinction:

- preview remains advisory so analysts can inspect behavior before final approval
- durable artifact and execution-like surfaces remain governed

## Authorization Model Today

The current authorization posture is intentionally described as transitional rather than complete.

- most protected governance and admin routes still use the existing binary `X-Admin-Token` guard
- a minimal principal, role enum, and `require_roles()` layer now exists in the backend
- that new RBAC bootstrap is currently applied only to `mapping/draft-sessions*` and `mapping/sets*`
- this means Semantra now has a real pilot RBAC slice, but not yet a complete multi-role authorization model across the whole application

## Architecture Notes

### Backend

The FastAPI backend exposes six main API domains:

- `upload`
- `mapping`
- `knowledge`
- `catalog`
- `evaluation`
- `observability`

### UI

The Streamlit UI has been decomposed into focused modules under `streamlit_ui/*`, while `streamlit_app.py` primarily acts as a composition root and navigation shell.

### Persistence

SQLite stores:

- mapping sets and audit logs
- benchmark datasets and evaluation runs
- transformation test sets
- correction history and reusable rules
- canonical and knowledge runtime data
- stewardship items and knowledge audit logs

### Runtime limitations

Current known architectural boundaries:

- background jobs are still in-memory/thread based
- canonical authoring is not yet fully DB-only
- some persistence models still use JSON-heavy storage patterns that are acceptable for pilot scope but not ideal for long-term scale

## What Semantra Is Not Yet

Not yet in current scope:

- production scheduler or batch orchestration platform
- connector-rich ingestion layer
- destination-system writeback engine
- multi-step RBAC enterprise workflow model
- graph-native lineage platform

## Immediate Next Steps

The next product wave should focus on proof, not feature sprawl:

1. keep the documentation aligned with the real current state of the product and its boundaries
2. run manual pilot scenarios and proof-of-concept checks that show whether the current surface adds concrete value to analyst and governance workflows
3. package those validated flows into stakeholder-facing presentations, repeatable live demos, and supporting artifacts
4. only after that evidence is strong, decide which enterprise-wide investments should come next: broader RBAC, deeper persistence, runtime hardening, and wider operational packaging

## Recommended Reading Order

If you need the most grounded view first:

1. `project_docs/current_state.md`
2. `README.md`
3. `PROJECT_OVERVIEW.md`
4. `project_docs/completed_slices.md`
5. `project_docs/plan.md`
6. `project_docs/epics.md`

For deeper strategy around catalog direction, see `docs/vision/INTEGRATION_CATALOG_VISION.md`.
