# Semantra Current State

As of 2026-05-27, Semantra is a pilot-ready semantic integration workbench built around a FastAPI backend, a Streamlit product UI, and a SQLite persistence layer. It already supports end-to-end analyst workflows from upload and schema profiling through mapping review, transformation authoring, guided explanation, governed artifact persistence, canonical knowledge management, benchmark evaluation, and reuse discovery. It is not yet a production-grade execution platform with persistent background workers, release packaging, or a DB-only canonical authoring model.

## Product Posture

What Semantra is today:

- an analyst-guided mapping and review tool for source-to-target and source-to-canonical workflows
- a governed workspace for saving, reviewing, reusing, and auditing mapping artifacts
- a canonical and overlay management console for semantic stewardship
- a searchable catalog of approved integration knowledge and concept reuse
- a benchmark and regression surface for measuring mapping quality changes
- a deterministic-first product with bounded AI assistance rather than autonomous mapping

What Semantra is not yet:

- a production ETL runtime or scheduler
- a multi-step enterprise workflow engine
- a fully normalized metadata/knowledge platform with DB-only authoring and migration lifecycle
- a full graph or ontology management product
- a resume-by-design workspace with durable `draft session` restore across reloads or runtime switches

## Persistence And State Placement Today

The product already persists a substantial part of its governed domain model in SQLite. The important distinction is not "DB or no DB", but rather which slices are:

- DB-backed and authoritative for runtime/listing/governance behavior
- DB-backed as a runtime snapshot while source authoring still remains file-seeded or reseed-driven
- session-local Streamlit orchestration state that is intentionally transient today

### A. DB-backed governed entities today

These slices already live in SQLite and are part of the current durable backend model:

- mapping-set governance records and version payloads (`mapping_sets`)
- catalog discovery projections and concept usage read models (`mapping_catalog_entries`, `mapping_catalog_concepts`)
- draft-session persistence for the current minimal save/list/load flow (`draft_sessions`)
- benchmark datasets and evaluation runs
- async mapping job status, progress, cancel metadata, and event log (`mapping_jobs`, `mapping_job_events`)
- corrections and reusable correction rules
- knowledge overlay versions and entries
- knowledge audit log and stewardship items
- source-field hints

In the current live pilot database this is observable directly: catalog rows, mapping-set rows, draft-session rows, job rows, and the canonical/knowledge runtime tables are physically present in `backend/semantra.sqlite3`.

### B. DB-backed runtime snapshots with file-backed authoring still present

These slices are stored in SQLite and loaded from SQLite during normal runtime when the persisted seed hash matches, but authoring is not yet fully DB-only:

- base knowledge concept registry (`knowledge_concepts`, `knowledge_field_contexts`)
- canonical concept registry (`canonical_concepts`, `canonical_field_contexts`)
- knowledge seed metadata (`knowledge_seed_meta`)

Current behavior:

- runtime loading is DB-first when the cached SQLite snapshot is current
- source-file changes still trigger reseed from canonical glossary / metadata source files back into the DB snapshot
- canonical authoring still retains file-backed reseed paths and is therefore not yet a pure DB-native authoring lifecycle

This is why the current product should be described as `DB-first runtime` rather than `DB-only knowledge authoring`.

### C. Session-local or browser-local orchestration state today

These slices still rely heavily on `st.session_state` and are not yet modeled as durable collaborative domain entities:

- active upload response and current profiled dataset handles in the browser session
- current mapping response, review filters, queue focus, and editor selections
- generated explanation, preview, codegen, and refinement panels that are intentionally rebuilt or cleared
- API base URL, admin token, backend reachability snapshot, and similar UI connection state
- debug-console selections, currently loaded details, and one-session operator context

Some of this can remain transient permanently because it is UI choreography rather than business state. The gap is not that every widget value must be persisted, but that any domain entity a user expects to resume, share, audit, or govern should have a backend identity and persistence model.

### D. Practical bottom line

The current state is:

- Catalog is in the DB.
- Mapping sets are in the DB.
- Draft sessions are in the DB, but resume semantics are still minimal.
- Mapping job state is in the DB, but execution is still local/thread-backed.
- Overlay lifecycle is in the DB.
- Canonical and knowledge runtime snapshots are in the DB.
- Canonical and base knowledge authoring are not yet fully DB-only because file-backed reseed inputs still exist.
- Workspace interaction state is still largely session-local.

So the next architecture step is not "introduce persistence from scratch". It is to finish the move from `pilot DB-backed runtime plus session orchestration` to `DB-first domain model with clear boundaries for what may remain ephemeral UI state`.

## Implemented User-Facing Capabilities

### 1. Data Ingestion and Schema Profiling

Implemented:

- row-data upload for CSV, JSON, XML, and XLSX
- SQL schema snapshot upload with table discovery and explicit table selection for multi-table files
- schema-spec upload where each row describes one field rather than one business record
- source-side companion metadata enrichment over an existing uploaded dataset handle
- target-side companion metadata enrichment over an existing uploaded target dataset handle in standard mode
- dataset summary and schema-profile display in the Workspace setup flow

Main code surfaces:

- `backend/app/api/routes/upload.py`
- `backend/app/services/spec_upload_service.py`
- `backend/app/services/schema_snapshot_service.py`
- `backend/app/services/upload_store.py`
- `streamlit_ui/workspace_views.py`

### 2. Mapping Workflows

Implemented:

- standard source-to-target auto mapping
- canonical-only source-to-business-concept mapping without a real target dataset
- configurable canonical candidate shortlisting before full canonical scoring
- sync and async mapping job flows with progress polling
- SQLite-backed durable status and progress persistence for async mapping jobs, while execution remains local and thread-backed
- active-job limits, TTL cleanup, and cooperative cancel support for mapping jobs
- one-to-one target assignment across the full target schema
- optional LLM closed-set validation layered on top of heuristic ranking
- scoring based on name, semantic, knowledge, canonical, pattern, statistical, overlap, embedding, correction, and LLM signals
- project/source/target canonical coverage reporting in mapping responses

Important current behavior:

- confidence labels remain `high >= 0.85`, `medium >= 0.65`, otherwise `low`
- mappings with score `>= 0.75` are currently auto-accepted even if the label remains `medium_confidence`
- canonical mode can narrow the initial search to a configurable likely-candidate pool before full scoring; the UI default is currently `10`
- async job API contract stays `start`, `poll status`, and `cancel`, but runtime state now survives ordinary in-process object churn because status/progress are read from SQLite
- finished jobs keep the same retention contract: up to `32` retained finished rows with a `900s` TTL; interrupted active jobs are marked `failed` on restart instead of remaining stuck in `running`

Main code surfaces:

- `backend/app/api/routes/mapping.py`
- `backend/app/services/mapping_service.py`
- `backend/app/services/mapping_job_service.py`
- `backend/app/services/virtual_target_service.py`
- `streamlit_ui/workspace_views.py`
- `streamlit_ui/workspace_review_views.py`

### 3. Review, Explainability, and Guided Copilots

Implemented:

- trust-layer review of selected mappings with confidence, signal traces, explanations, and LLM notes
- source-to-concept and concept-to-target review views
- per-row LLM mapping refinement with transient meaning, negative guidance, sample values, and a refinement instruction
- batch low-confidence LLM refinement plus accept/revert handling for refined row proposals
- opportunistic LLM decision proposals for filtered `needs_review` rows
- optional live LLM fill for missing proposal traces under bounded, closed-set constraints
- Mapping Analysis Overview with structured technical summary, risk readout, and recommended next actions
- optional narration/audio generation for Mapping Analysis Overview
- Review Queue Plan for queue-level prioritization over the currently filtered review set
- grouped attention summary for repeated unmatched or low-confidence review patterns
- canonical-gap suggestion flow for individual candidates
- Gap Queue Summary for the current canonical-gap queue before candidate-by-candidate review

Important current behavior:

- these guidance surfaces do not auto-approve or auto-apply durable changes
- they are designed to stay close to a concrete local workflow step
- they use deterministic fallback behavior when LLM output is unavailable or invalid
- proposal generation in Review remains advisory until explicit apply actions are executed in Decisions
- the five bounded guidance panels now share the same `LLM` / `Fallback` header-detail pattern, explicit read-only role messaging, aligned success/error copy, and aligned section-heading treatment for `Risks` and `Next actions`

Main code surfaces:

- `streamlit_ui/workspace_review_views.py`
- `backend/app/services/mapping_analysis_service.py`
- `backend/app/services/review_plan_service.py`
- `backend/app/services/canonical_gap_triage_service.py`

### 4. Decisions, Output, and Transformation Authoring

Implemented:

- manual adjustment of suggested target mappings in the Decisions flow
- manual mapping to virtual canonical target options in canonical mode
- export/import of current mapping decisions as JSON and Excel
- apply/dismiss workflows for LLM decision proposals, including conservative `Apply safe` execution
- transformation suggestion, template-assisted authoring, and manual transformation code editing
- advisory row preview from active mapping decisions
- Pandas, PySpark, and dbt starter code generation from reviewed mapping decisions
- transformation generation via LLM when configured
- structured preview/codegen warnings for syntax, runtime, type coercion, row-count mismatch, and related issues
- transformation templates
- output artifact refinement with side-by-side original/refined compare and explicit accept/discard actions
- transformation test set persistence, detail, listing, and execution
- decision-origin audit metadata (`manual_mapping`, `llm_proposal`) surfaced in Active Decisions

Important current behavior:

- preview is intentionally advisory and remains available before all decisions are accepted
- standard-mode code generation is governance-gated and requires accepted active decisions
- canonical mode intentionally skips preview because no concrete target dataset exists, but still supports Pandas/PySpark/dbt code generation and artifact refinement from active source-to-canonical decisions
- dbt output is currently scoped to starter-artifact generation and refinement; generating a fuller dbt package (`model.sql`, `schema.yml`, optional `sources.yml`) is intentionally deferred to a future iteration
- draft-session continuity now has a minimal save/list/load path for `Workspace > Review` and `Workspace > Decisions`; restore rebuilds a stable mapping contract from saved schema handles, editor state, audit metadata, and `mapping_runtime`, while still clearing preview/codegen/guidance artifacts instead of reviving stale generated outputs
- draft-session restore also persists the saved `api_base_url` and blocks resume when the active runtime or upload schema context does not match the saved draft
- transformation test-set save and run are governance-gated and require accepted active decisions
- refinement does not replace the active generated artifact until the user explicitly accepts it
- decision-origin audit metadata is persisted through decision JSON export/import for analyst handoff continuity

Main code surfaces:

- `backend/app/api/routes/mapping.py`
- `backend/app/services/preview_service.py`
- `backend/app/services/codegen_service.py`
- `backend/app/services/transformation_test_service.py`
- `backend/app/services/llm_service.py`
- `streamlit_ui/workspace_views.py`

### 5. Mapping Set Governance and Reuse

Implemented:

- versioned mapping-set persistence
- `owner`, `assignee`, `review_note`, status, and audit metadata
- mapping-set status workflow: `draft`, `review`, `approved`, `archived`
- mapping-set diff and audit views
- mapping-set apply/reuse flow back into Workspace state
- reuse/apply gating so only approved mapping sets can be used in workspace flows
- catalog persistence projection over saved mapping sets
- normalized SQLite repository surfaces for mapping-set governance, catalog listing/search/detail, and concept-centric discovery reads

Main code surfaces:

- `backend/app/api/routes/mapping.py`
- `backend/app/services/mapping_governance_repository.py`
- `backend/app/services/catalog_repository.py`
- `backend/app/services/persistence_service.py`
- `streamlit_ui/workspace_decision_views.py`
- `streamlit_ui/catalog_views.py`

### 6. Corrections and Reusable Learning

Implemented:

- persistence of user corrections from mapping review
- reviewed correction save flow in the UI
- reusable correction-rule candidate generation and promotion
- correction impact evaluation against saved benchmark datasets
- learning-signal integration back into mapping ranking

Important current behavior:

- only closed review outcomes are allowed to become durable correction history
- legacy `overridden` history is no longer treated as an approved reusable-learning class
- reusable-rule promotion rejects unresolved review states

Main code surfaces:

- `backend/app/api/routes/observability.py`
- `backend/app/services/correction_service.py`
- `backend/app/services/mapping_service.py`
- `streamlit_ui/workspace_decision_views.py`

### 7. Canonical Layer and Knowledge Overlay Lifecycle

Implemented:

- file-backed canonical glossary import/export
- canonical concept runtime with aliases, field contexts, and usage overlays
- DB-first canonical runtime bootstrap with seed-hash detection and SQLite reload support
- overlay CSV validation preview before save
- overlay version create/list/detail lifecycle
- overlay activate, deactivate, archive, rollback, reload, and reseed flows
- canonical-gap candidate extraction from mapping results
- LLM-assisted canonical-gap suggestion flow
- approve, reject, ignore, and proposal-state handling for canonical-gap stewardship
- stewardship records for `canonical_gap` and `overlay_promotion`
- explicit promotion from overlay stewardship item into stable canonical glossary
- active overlay aliases merged into the runtime and surfaced in the console
- numeric-only canonical aliases filtered out of canonical registry and glossary promotion/import paths
- canonical glossary import and overlay-promotion authoring sync now refresh only the canonical runtime tables over persisted knowledge concepts, instead of forcing a full metadata reseed path

Main code surfaces:

- `backend/app/api/routes/knowledge.py`
- `backend/app/services/knowledge_runtime_repository.py`
- `backend/app/services/stewardship_repository.py`
- `backend/app/services/metadata_knowledge_service.py`
- `backend/app/services/knowledge_overlay_service.py`
- `backend/app/services/canonical_gap_service.py`
- `streamlit_ui/admin_views.py`
- `streamlit_app.py`

### 8. Canonical Console

Implemented:

- top-level Canonical Console area in the Streamlit product navigation
- concept registry with search and filtering by scope/focus
- canonical concept count summary (`Filtered`, `Total`, `With active overlay`, `With context`) aligned with knowledge-registry metrics style
- concept detail showing aliases, field contexts, active overlay entries, catalog usage, and audit references
- active overlay summary metrics and lifecycle controls
- mirror of canonical-gap queue from Workspace review
- lightweight impact preview before approval/promotion
- stewardship item detail with status, owner, assignee, review note, and payload snapshot
- overlay-promotion review and explicit promote-to-glossary execution flow

Current maturity:

- the core Canonical Console happy-path governance loop is pilot-complete
- remaining work around the console is stabilization and productization, not missing core workflow

Main code surfaces:

- `streamlit_ui/admin_views.py`
- `backend/app/api/routes/knowledge.py`
- `backend/app/services/persistence_service.py`

### 9. Enterprise Integration Catalog

Implemented:

- integration listing and search with filters
- integration detail drilldown
- concept-centric catalog detail lookup
- Streamlit Catalog tab for browse/search/detail flows
- source-system -> target-system discovery overview over catalog results
- similar-approved-integration hints in result browsing
- field-scoped reuse discovery with compare-before-import, partial import, and undo
- mapping-set detail, audit, and diff drilldown
- compare -> detail drilldown for peer integrations and version baselines
- Catalog -> Workspace Review handoff for selected versions and diff-scoped changed-source review context
- multi-source Catalog diff handoff now also has live browser confirmation on an already loaded Workspace review set: `Filter by source` stays `All`, while scope is carried through `source_scope` messaging and a review-focus caption instead of a hard source filter
- Catalog -> Governance handoff with section-aware `Canonical` / `Stewardship` landing and stale-filter reset
- approved-only reuse back into Workspace
- Workspace Reuse Fit explanation for the selected catalog version against the current workspace context

Current boundary:

- catalog search, drilldown, compare, reuse-fit, and review/governance handoff flows are implemented
- broader concept/reuse visual discovery beyond the current table/drilldown and handoff surfaces remains open
- Workspace Reuse Fit now follows the same bounded-guidance caption, unlock, metadata, and output-heading pattern as the Workspace and Benchmarks guidance panels

Main code surfaces:

- `backend/app/api/routes/catalog.py`
- `backend/app/services/persistence_service.py`
- `backend/app/services/catalog_reuse_fit_service.py`
- `streamlit_ui/catalog_views.py`

### 10. Benchmarks and Evaluation

Implemented:

- fixture benchmark run endpoint
- custom benchmark run endpoint
- saved benchmark dataset create/list/run flows
- scoring-profile comparison
- saved evaluation run history
- correction-impact benchmarking
- Benchmark Explanation over the currently loaded benchmark evidence in the Benchmarks UI

Important current behavior:

- saving the current mapping as a benchmark is governance-gated and requires accepted active decisions
- benchmark explanation is a readout surface only; it does not change runtime scoring state
- benchmark explanation now uses the same bounded-guidance intro, unlock, metadata, and output-heading treatment as the other guidance panels

Main code surfaces:

- `backend/app/api/routes/evaluation.py`
- `backend/app/services/evaluation_service.py`
- `backend/app/services/benchmark_explanation_service.py`
- `streamlit_ui/benchmark_views.py`

### 11. Admin and Observability

Implemented:

- runtime config read/reload endpoints
- decision-log inspection
- corrections and reusable-rule inspection/promote flows
- admin-token-aware UI behavior
- Admin / Debug surface separate from Canonical Console
- knowledge runtime status now surfaces cache/source separation via `runtime_source`, `source_hash_state`, and seeded-count metadata
- mapping job runtime now persists status/progress in SQLite while keeping local thread-backed execution, and observability surfaces durable-backend pressure plus explicit trigger flags

Main code surfaces:

- `backend/app/api/routes/observability.py`
- `streamlit_ui/admin_views.py`
- `streamlit_ui/api.py`

### 12. UI shell guidance surfaces

Implemented:

- compact sidebar operations strip in a 2x3 KPI layout for fast workflow orientation
- unified status badge legend shared across Workspace and Governance views
- dismissible onboarding hints by top-level app area

Main code surfaces:

- `streamlit_ui/shared_views.py`
- `streamlit_app.py`

### 13. Session continuity boundary

Current behavior:

- browser session state is not automatically resumed across days
- continuation is supported through explicit persisted artifacts (mapping sets or exported/imported decision checkpoints)

Open design track:

- design a deliberate draft/resume model (scope, conflict handling, audit) before enabling auto-resume behavior

## Enforced Governance Rules Today

The product already enforces several concrete governance contracts at the backend and mirrors them in the UI where appropriate.

Implemented enforcement:

- only approved mapping sets can be applied or reused in Workspace flows
- code generation requires all active mapping decisions to be accepted
- saving the current mapping as a benchmark requires all active mapping decisions to be accepted
- saving reviewed corrections requires closed review outcomes, not unresolved states
- promotion of reusable correction rules rejects unresolved review states
- canonical-gap approval requires proposal triage state `ready_for_approval`
- knowledge overlay activation requires a `validated` overlay version
- knowledge overlay archive only allows `validated` or `active` overlay versions
- transformation test-set save requires accepted active decisions
- transformation test-set run requires accepted active decisions, including persisted sets from older states

Intentional product distinction:

- preview remains advisory so analysts can inspect current mapping behavior before final approval
- execution-like or durable artifact surfaces remain governed

## Architecture and Persistence Shape

Current runtime shape:

- FastAPI backend in `backend/app`
- Streamlit product UI in `streamlit_app.py` and `streamlit_ui/*`
- SQLite persistence in `backend/semantra.sqlite3`
- in-memory dataset store for uploaded handles and mapping job runtime state
- DB-first canonical/knowledge runtime with file-based reseed source for canonical glossary and metadata inputs

Important implementation characteristics:

- knowledge and canonical runtime are loaded primarily from SQLite when the seed hash is current
- canonical glossary authoring now refreshes the canonical slice over persisted knowledge concepts without a full metadata/workbook reseed; explicit reseed remains for source-file drift
- background mapping jobs are currently in-memory/thread based and designed for local/demo use
- mapping job runtime now exposes concrete saturation/retention triggers before a durable backend becomes mandatory
- newer bounded AI surfaces use small structured request/response contracts and deterministic fallback behavior

## Testing and Validation Shape

The codebase already contains focused backend and Streamlit regression coverage for the major product surfaces.

Strongly covered areas include:

- upload and multi-format ingestion
- auto mapping and async job polling
- preview/codegen behavior and artifact refinement
- mapping-set governance and catalog detail flows
- canonical gap assistant and canonical console governance flows
- overlay promotion and stable glossary execution
- benchmark flows, profile comparison, correction impact, and explanation
- Streamlit helper behavior for workspace, benchmark, catalog, admin, and transformation state

The primary regression anchors are:

- `backend/tests/test_api_smoke.py`
- `backend/tests/test_mapping_service.py`
- `tests/test_streamlit_*`

## Known Boundaries and Immediate Next Steps

The following items remain outside the current pilot-complete scope or are the next productization steps:

- browser-level bounded guidance discoverability confirmation and regression capture across `Workspace`, `Catalog`, and `Benchmarks`
- broader catalog visual discovery beyond the current compare and handoff surfaces
- persistent background job queue/status backend for multi-user, restart-resilient, or materially longer-running tasks
- DB-only canonical authoring and promotion model without file-backed reseed source inputs
- system-specific virtual targets beyond canonical-only mode (`Epic 12B`)
- stronger data-quality intelligence signals (`Epic 9`)
- broader operational packaging beyond preview/codegen/test artifacts (`Epic 10`)
- deeper vector/cache acceleration and signal precomputation (`Epic 14A/14B`)
- graph-shaped lineage and impact analysis as a derived analysis layer (`Epic 15`)

## How To Use `project_docs`

Use the project docs in this order:

1. `current_state.md` for what exists today
2. `completed_slices.md` for chronological delivery history
3. `plan.md` for forward-looking priorities and sequencing
4. `epics.md` for backlog structure and status by epic
5. `implementation_checklists.md` for active execution checklists only
