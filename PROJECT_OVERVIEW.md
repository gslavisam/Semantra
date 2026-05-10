# Project Overview

## What Semantra Is

Semantra is a semantic mapping and governance workbench for analyst-guided integration design.

It is built around a deterministic-first loop:

1. ingest source and target structures
2. profile schemas and rank mapping candidates
3. enrich matching with metadata knowledge, canonical concepts, and prior review memory
4. use bounded AI only where it adds explainable value
5. review, refine, preview, and persist governed artifacts

The current product is pilot-ready for controlled analyst and stewardship workflows. It is not yet a production ETL runtime, enterprise connector platform, or orchestration engine.

## Product Goal

The goal of Semantra is to make schema mapping:

- explainable
- reviewable
- measurable
- reusable
- improvable through governed feedback

The product does not treat LLMs as an autonomous mapper. Instead, it keeps the main inference path deterministic and uses AI only inside bounded, inspectable surfaces such as ambiguity review, transformation generation, and canonical-gap suggestion.

## Product Shape Today

Semantra currently consists of:

- a FastAPI backend in `backend/app`
- a Streamlit product UI in `streamlit_app.py` and `streamlit_ui/*`
- a SQLite persistence layer in `backend/semantra.sqlite3`
- file-backed canonical/metadata seed inputs with DB-first runtime loading when the persisted seed is current

The main top-level UI areas are:

- `Workspace`
- `Canonical Console`
- `Catalog`
- `Benchmarks`
- `Admin / Debug`

## Core Functional Areas

### 1. Ingestion and schema profiling

Implemented today:

- row-data upload for CSV, JSON, XML, and XLSX
- SQL snapshot upload with explicit table selection for multi-table files
- schema-spec upload where each row represents one field
- source companion metadata enrichment over an existing uploaded dataset

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
- top-k candidate ranking with one-to-one assignment
- signal fusion across lexical, semantic, knowledge, canonical, pattern, statistical, overlap, embedding, correction, and optional LLM inputs
- project/source/target canonical coverage reporting
- async mapping jobs with progress polling

Important behavior:

- confidence is a normalized ranking heuristic, not a calibrated probability
- current thresholds are `high >= 0.85`, `medium >= 0.65`, otherwise `low`

Detailed signal, score, and bounded LLM behavior is documented in `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

Main anchors:

- `backend/app/services/mapping_service.py`
- `backend/app/api/routes/mapping.py`
- `backend/app/services/mapping_job_service.py`

### 3. Review and decisioning

Implemented today:

- trust-layer explanations and signal breakdowns
- source-to-concept and concept-to-target review views
- manual target adjustment
- decision export/import as JSON and Excel
- reusable transformation templates and manual transformation editing

This turns the engine output into an analyst-controlled review surface rather than an opaque guess.

Main anchors:

- `streamlit_ui/workspace_review_views.py`
- `streamlit_ui/workspace_decision_views.py`
- `streamlit_ui/mapping_helpers.py`

### 4. Preview, code generation, and transformation testing

Implemented today:

- advisory preview over active mapping decisions
- Pandas code generation
- LLM transformation generation when configured
- structured transformation warnings and fallback behavior
- transformation test set save/list/detail/run flows

Important product contract:

- preview is intentionally advisory and can run before all decisions are accepted
- code generation and transformation test-set persistence/execution are governance-gated

Detailed preview/codegen warning behavior and classification is documented in `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`.

Detailed transformation test-set assertion and run behavior is documented in `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`.

Main anchors:

- `backend/app/services/preview_service.py`
- `backend/app/services/codegen_service.py`
- `backend/app/services/transformation_test_service.py`
- `backend/app/api/routes/mapping.py`

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

Detailed Canonical Console and stewardship behavior is documented in `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`.

### 9. Enterprise Integration Catalog

Implemented today:

- integration list/search/detail APIs
- concept-centric catalog detail
- Streamlit Catalog browse/search/drilldown flows
- reuse into Workspace from approved mapping-set artifacts

Current boundary:

- basic reuse discovery exists
- richer concept/reuse visualization remains open

Main anchors:

- `backend/app/api/routes/catalog.py`
- `streamlit_ui/catalog_views.py`

Detailed catalog search, similarity, and reuse behavior is documented in `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`.

### 10. Benchmarks and evaluation

Implemented today:

- built-in and custom benchmark run endpoints
- saved benchmark dataset create/list/run flows
- evaluation run history
- correction-impact measurement

Detailed benchmark metric and correction-impact interpretation is documented in `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

Main anchors:

- `backend/app/api/routes/evaluation.py`
- `backend/app/services/evaluation_service.py`
- `streamlit_ui/benchmark_views.py`

## Governance Model Today

Semantra already enforces several concrete governance contracts, not just passive statuses.

Implemented backend-enforced rules include:

- only approved mapping sets can be applied or reused in Workspace flows
- code generation requires accepted active mapping decisions
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

## Recommended Reading Order

If you need the most grounded view first:

1. `project_docs/current_state.md`
2. `README.md`
3. `PROJECT_OVERVIEW.md`
4. `project_docs/completed_slices.md`
5. `project_docs/plan.md`
6. `project_docs/epics.md`

For deeper strategy around catalog direction, see `docs/vision/INTEGRATION_CATALOG_VISION.md`.
