# Project Overview

## What Semantra Is

Semantra is an explainable semantic mapping product slice for aligning source and target schemas under analyst control.

It is designed around a deterministic-first review loop:
- ingest source and target structures
- profile schemas and rank candidate mappings
- enrich matching with metadata knowledge and custom overlays
- use constrained AI only where it adds clear value
- preview transformations before execution
- persist feedback, reusable rules, mapping sets, and evaluation artifacts

Semantra is already useful as a pilot-grade semantic mapping and review engine. It is not yet a full ETL platform, orchestration layer, or connector-heavy integration suite.

## Product Goal

The goal of Semantra is to make schema mapping:
- explainable
- measurable
- reviewable
- improvable over time

Instead of asking a free-form LLM to "map everything", Semantra keeps the core workflow deterministic and uses AI only in bounded, inspectable steps such as ambiguity resolution and transformation generation.

## Current Scope

Current MVP scope includes:
- CSV, JSON, XML, and XLSX row-data upload for source and target datasets
- SQL schema snapshot upload plus table discovery and explicit table selection for multi-table snapshots
- schema profiling with lexical, pattern, and statistical hints
- multi-signal candidate ranking with top-k alternatives and one-to-one assignment
- canonical business glossary matching with a file-backed glossary, canonical signal scoring, and source/target/project canonical coverage summaries
- explicit source -> concept -> target review support through canonical path details and grouped review tables
- optional constrained LLM validation in ambiguity-band cases
- prompt-driven pandas transformation generation for reviewed field pairs
- transformation preview with syntax checks, dry-run execution, before/after samples, structured warnings, and generated code output
- custom knowledge overlays layered on top of built-in metadata knowledge, including concept aliases that extend canonical concept matching
- persisted user corrections, promoted reusable rules, benchmark datasets, evaluation runs, transformation test sets, and versioned mapping sets
- lightweight mapping-set status workflow with `draft`, `review`, `approved`, and `archived`, now extended by the first Epic 6 governance slice
- internal Streamlit UI for upload, trust-layer review, canonical concept views, transformations, corrections, benchmarks, knowledge overlays, and admin/debug flows

Out of scope for the current slice:
- authentication and role-based access control
- production-grade frontend
- database connectors beyond the current flat-file workflow
- distributed job orchestration
- complex multi-table graph mapping
- production writeback into destination systems
- cross-project canonical governance and approval workflow

## Core Concept

Semantra treats data mapping as a multi-signal inference problem with explicit review surfaces.

Each source field is compared against target fields using a blend of lexical, semantic, metadata, pattern, statistical, overlap, optional embedding, and historical feedback signals. The result is a ranked candidate list with explanations, not a blind one-shot guess.

The product then layers controlled trust mechanisms on top of that ranking:
- knowledge overlays that can refine semantic matching without editing base assets
- canonical business concepts that let the review surface reason over source -> concept -> target paths instead of only source -> target guesses
- corrections and promoted reusable rules that improve future ranking behavior
- transformation preview and generated-code validation before the analyst commits to an execution artifact
- saved mapping sets and transformation test sets that make review and replay more structured

## Main Functional Areas

### 1. Dataset Ingestion and Profiling

Purpose:
- accept uploaded row-based files and schema snapshots
- assign dataset identifiers
- build the schema profile used by the mapping engine and trust layer

Current behavior:
- source and target datasets are uploaded separately
- row-based uploads support CSV, JSON, XML, and XLSX
- SQL uploads remain schema-only and can require explicit table selection for multi-table snapshots
- each upload produces a dataset handle, schema profile, and preview rows when row data exists

Implementation anchors:
- `backend/app/api/routes/upload.py`
- `backend/app/services/tabular_upload_service.py`
- `backend/app/services/profiling_service.py`
- `backend/app/services/upload_store.py`

### 2. Mapping Engine

Purpose:
- generate explainable mapping candidates from source schema to target schema

Current behavior:
- compute source-target scores across lexical, semantic, knowledge, canonical, pattern, statistical, overlap, optional embedding, correction, and optional LLM signals
- return top-k ranked candidates per source field
- apply a greedy global one-to-one assignment step for selected mappings
- attach signal breakdowns, canonical concept details, and explanation lines to both selected mappings and ranked candidates
- return source, target, and project-level canonical coverage summaries alongside the mapping payload

Important implementation notes:
- the weighted score is still a ranking heuristic, not a calibrated probability
- correction signal now includes both raw feedback history and promoted reusable rules
- the knowledge signal can be influenced by both built-in metadata assets and active knowledge overlays
- the canonical signal is currently glossary-driven and file-backed; it is not yet a governed enterprise semantic model

Implementation anchor:
- `backend/app/services/mapping_service.py`

### 3. Constrained LLM Validation and Transformation Generation

Purpose:
- use AI in bounded, inspectable steps instead of handing over the full mapping workflow

Current behavior:
- ambiguity-band validation can re-rank only the closed candidate set or return `no_match`
- prompt-driven transformation generation produces pandas-oriented code for a selected source-target pair
- provider adapters currently cover OpenAI Responses API, OpenAI-compatible LM Studio endpoints, and Ollama

Implementation anchors:
- `backend/app/services/llm_service.py`
- `backend/app/api/routes/mapping.py`

### 4. Transformation Safety, Preview, and Codegen

Purpose:
- make reviewed transformations inspectable before they become code artifacts

Current behavior:
- preview executes reviewed `transformation_code` against sample rows
- preview returns `before_samples`, `after_samples`, `status`, `classification`, and structured warnings
- warnings cover syntax errors, runtime errors, missing source columns, null expansion, type coercion, and row-count mismatch
- code generation emits Pandas starter code and now returns structured warning objects when it must skip or fall back
- reusable transformation templates exist for common text cleanup and formatting patterns
- transformation test sets can be saved and executed as lightweight regression cases

Implementation anchors:
- `backend/app/services/transformation_service.py`
- `backend/app/services/preview_service.py`
- `backend/app/services/codegen_service.py`
- `backend/app/services/transformation_template_service.py`
- `backend/app/services/transformation_test_service.py`

### 5. Knowledge Overlay and Canonical Glossary Runtime

Purpose:
- let a team add project-specific aliases, abbreviations, and synonyms without editing base metadata files
- maintain a canonical business glossary that can participate directly in mapping and trust-layer explanation

Current behavior:
- CSV overlays can be validated, saved, listed, inspected, activated, deactivated, rolled back, archived, and reloaded at runtime
- overlay entries are merged into metadata-driven semantic expansion and explanation generation
- `concept_alias` overlay entries validate against the canonical glossary and extend canonical concept matching at runtime
- canonical glossary CSV can be imported/exported through admin-protected API endpoints and the Streamlit admin/debug surface
- overlay lifecycle changes are audit logged

Implementation anchors:
- `backend/app/services/knowledge_overlay_service.py`
- `backend/app/services/metadata_knowledge_service.py`
- `backend/app/api/routes/knowledge.py`

### 6. Correction Learning and Reusable Rules

Purpose:
- turn explicit analyst feedback into durable ranking improvements

Current behavior:
- corrections distinguish `accepted`, `rejected`, and `overridden`
- correction history can boost corrected targets and penalize previously wrong suggestions
- repeated history can be surfaced as reusable rule candidates
- candidates can now be promoted into persisted reusable rules
- promoted rules are stronger than raw history and appear in mapping explanations as an explicit influence

Implementation anchors:
- `backend/app/services/correction_service.py`
- `backend/app/api/routes/observability.py`

### 7. Mapping Sets and Lightweight Governance Slice

Purpose:
- make reviewed mapping decisions persistable, replayable, and status-aware

Current behavior:
- mapping sets can be saved with versioning by name
- each saved version carries `draft`, `review`, `approved`, or `archived` status
- status changes are audit logged
- saved sets can be reloaded back into the current Streamlit review state
- mapping sets now also carry `owner`, `assignee`, and `review_note` metadata at the version level
- applying a saved mapping set back into the active review state is audit logged
- version diff views are available for comparing two versions of the same mapping set
- stronger export/run gates are still planned under the remaining Epic 6 governance work

Implementation anchors:
- `backend/app/api/routes/mapping.py`
- `backend/app/services/persistence_service.py`
- `streamlit_app.py`
- `streamlit_ui/workspace_views.py`
- `streamlit_ui/workspace_decision_views.py`

### 8. Evaluation and Benchmarking

Purpose:
- measure mapping quality and learning effects with repeatable datasets

Current behavior:
- run the built-in benchmark fixture or custom ad hoc payloads
- save benchmark datasets in SQLite and re-run them later
- compare baseline vs correction-aware performance through correction-impact evaluation
- persist evaluation run history for later inspection

Implementation anchors:
- `backend/app/api/routes/evaluation.py`
- `backend/app/services/evaluation_service.py`
- `backend/tests/fixtures/mapping_gold.json`

### 9. Streamlit Review UI

Purpose:
- provide a fast operator-facing surface for demo, pilot, and analyst review workflows

Current behavior:
- upload source and target files
- review ranked candidates and trust-layer explanations
- inspect explicit `Source -> Concept` and `Concept -> Target` tables plus grouped canonical concept summaries
- edit mappings manually and attach transformations
- save corrections, promote reusable rules, manage knowledge overlays, import/export canonical glossary data, save mapping sets, inspect benchmarks, and use admin/debug tools

Implementation anchor:
- `streamlit_app.py`
- `streamlit_ui/workspace_views.py`
- `streamlit_ui/workspace_review_views.py`
- `streamlit_ui/workspace_decision_views.py`
- `streamlit_ui/admin_views.py`
- `streamlit_ui/benchmark_views.py`

## Main Workflows

Semantra currently supports eight practical workflows.

### Workflow 1. Upload and Auto-Map

Input:
- source and target files or SQL schema snapshots

Process:
- parse uploads
- build schema profiles
- score all candidate mappings
- optionally invoke constrained LLM validation inside the ambiguity band
- apply one-to-one assignment and return top-k ranked alternatives

Result:
- profiled datasets
- selected mappings
- ranked candidates with explanation and signal breakdowns
- canonical concept details and project-level canonical coverage for the active source/target pair

Endpoints:
- `POST /upload`
- `POST /upload/sql/tables`
- `POST /mapping/auto`

### Workflow 2. Review, Transform, Preview, and Generate Code

Input:
- reviewed mapping decisions
- optional custom or generated transformation code

Process:
- preview transformed rows against sample source data
- classify transformations as `direct`, `safe`, or `risky`
- surface structured preview warnings
- generate Pandas starter code for the reviewed mapping set

Result:
- preview rows
- transformation previews with warnings and samples
- generated Pandas artifact

Endpoints:
- `POST /mapping/preview`
- `POST /mapping/codegen`
- `GET /mapping/transformation/templates`
- `POST /mapping/transformation/generate`

### Workflow 3. Learn From Corrections

Input:
- user-reviewed decisions and correction notes

Process:
- persist correction history
- aggregate repeated corrections into reusable rule candidates
- promote stable patterns into persisted reusable rules
- apply both raw history and promoted rules back into future ranking

Result:
- correction memory
- promoted reusable rules
- stronger explainable feedback signal in future runs

Endpoints:
- `GET /observability/corrections`
- `POST /observability/corrections`
- `GET /observability/corrections/reusable-rules`
- `GET /observability/corrections/reusable-rules/active`
- `POST /observability/corrections/reusable-rules/promote`

### Workflow 4. Manage Knowledge Overlays

Input:
- overlay CSV files with aliases, abbreviations, and synonyms
- optional canonical glossary CSV import/export actions

Process:
- validate uploaded rows
- save a versioned overlay
- inspect entries
- activate, deactivate, rollback, archive, or reload runtime knowledge
- import or export the canonical glossary CSV used by the canonical signal layer

Result:
- active project-specific knowledge layer on top of built-in metadata
- active canonical glossary that can drive source -> concept -> target explanations and project-level coverage summaries
- audit trail for knowledge lifecycle changes

Endpoints:
- `POST /knowledge/overlays/validate`
- `POST /knowledge/overlays`
- `GET /knowledge/overlays`
- `GET /knowledge/overlays/{overlay_id}`
- `POST /knowledge/overlays/{overlay_id}/activate`
- `POST /knowledge/overlays/{overlay_id}/deactivate`
- `POST /knowledge/overlays/{overlay_id}/archive`
- `POST /knowledge/overlays/rollback`
- `GET /knowledge/audit`
- `GET /knowledge/canonical-glossary/export`
- `POST /knowledge/canonical-glossary/import`
- `POST /knowledge/reload`

### Workflow 5. Save and Version Mapping Sets

Input:
- current reviewed mapping decisions
- optional author and note metadata

Process:
- save a versioned mapping set by name
- update status across `draft`, `review`, `approved`, and `archived`
- inspect audit history
- reload a saved version into the current review state

Result:
- reusable mapping-set artifacts instead of session-only JSON exports
- lightweight governance trail around create, status change, apply, and version diff review

Endpoints:
- `POST /mapping/sets`
- `GET /mapping/sets`
- `GET /mapping/sets/{mapping_set_id}`
- `POST /mapping/sets/{mapping_set_id}/apply`
- `POST /mapping/sets/{mapping_set_id}/status`
- `GET /mapping/sets/{mapping_set_id}/audit`
- `GET /mapping/sets/{mapping_set_id}/diff?against_id=<other_version_id>`

### Workflow 6. Save and Run Transformation Test Sets

Input:
- reviewed mapping decisions
- named transformation test cases with assertions

Process:
- persist named test sets
- run them against preview logic
- compare actual preview output and warning codes with expectations

Result:
- lightweight regression safety net for reviewed transformations

Endpoints:
- `POST /mapping/transformation/test-sets`
- `GET /mapping/transformation/test-sets`
- `GET /mapping/transformation/test-sets/{test_set_id}`
- `POST /mapping/transformation/test-sets/{test_set_id}/run`

### Workflow 7. Benchmark and Evaluate

Input:
- built-in fixtures, ad hoc evaluation cases, or saved benchmark datasets

Process:
- measure mapping accuracy
- compare baseline vs correction-aware performance
- persist evaluation runs for later inspection

Result:
- measurable quality outputs for heuristics and feedback loops

Endpoints:
- `GET /evaluation/benchmark`
- `POST /evaluation/run`
- `POST /evaluation/datasets`
- `GET /evaluation/datasets`
- `POST /evaluation/datasets/{dataset_id}/run`
- `POST /evaluation/datasets/{dataset_id}/correction-impact`
- `GET /evaluation/runs`

### Workflow 8. Review in Streamlit UI

Input:
- uploaded source and target files
- reviewed mappings, corrections, and optional benchmark or governance metadata

Process:
- run upload and review flows from a single operator surface
- inspect explanations, canonical source/concept/target views, transformation previews, reusable rule candidates, knowledge overlays, benchmarks, and saved mapping sets
- apply saved mapping-set versions back into the current review state

Result:
- fast analyst-friendly validation layer on top of the backend APIs

Implementation anchor:
- `streamlit_app.py`
- `streamlit_ui/workspace_views.py`
- `streamlit_ui/workspace_review_views.py`
- `streamlit_ui/workspace_decision_views.py`
- `streamlit_ui/admin_views.py`
- `streamlit_ui/benchmark_views.py`

## Architecture

Semantra uses a layered FastAPI backend plus a modular Streamlit review UI.

### Application Layer

Responsible for:
- app bootstrap
- middleware setup
- router registration

Key file:
- `backend/app/main.py`

### API Layer

Responsible for:
- request/response handling
- lightweight validation
- route-level orchestration

Main route groups:
- `mapping`
- `observability`
- `evaluation`
- `knowledge`
- `upload`

Location:
- `backend/app/api/routes/`

### Core Layer

Responsible for:
- runtime settings
- `.env` and environment variable loading
- settings reload behavior
- logging setup

Location:
- `backend/app/core/`

### Domain Model Layer

Responsible for:
- schema models
- mapping models
- evaluation models
- observability models

Location:
- `backend/app/models/`

### Service Layer

Responsible for the main product logic:
- upload store
- profiling
- mapping
- embedding
- llm validation
- knowledge overlay and metadata runtime enrichment
- preview
- code generation
- transformation templates and transformation tests
- decision logging
- correction handling
- mapping-set persistence and lightweight governance state
- persistence
- evaluation

Location:
- `backend/app/services/`

### Streamlit UI Layer

Responsible for:
- composition of the operator-facing review app
- API client helpers and runtime status widgets
- mapping-state helpers and trust-layer presentation helpers
- workspace, decision, admin/debug, and benchmark tab rendering

Current shape:
- `streamlit_app.py` acts as the composition root and compatibility wrapper surface for focused AST-based tests
- extracted UI responsibilities live in `streamlit_ui/api.py`, `streamlit_ui/shared_views.py`, `streamlit_ui/mapping_state.py`, `streamlit_ui/mapping_helpers.py`, `streamlit_ui/workspace_views.py`, `streamlit_ui/workspace_review_views.py`, `streamlit_ui/workspace_decision_views.py`, `streamlit_ui/admin_views.py`, and `streamlit_ui/benchmark_views.py`

### Utility Layer

Responsible for:
- name normalization
- token enrichment
- low-level similarity helpers

Location:
- `backend/app/utils/`

### Storage Model

Semantra currently uses two storage modes:

1. In-memory storage
   Used for active uploaded datasets during the current process lifetime.

2. SQLite storage
   Used for:
   - decision logs
   - user corrections
   - reusable correction rules
   - mapping sets
   - mapping-set audit logs
   - saved benchmark datasets
   - saved evaluation runs
   - transformation test sets
   - knowledge overlay versions and entries
   - knowledge audit logs

## Current API Surface

Semantra currently exposes these endpoint groups.

Upload:
- `POST /upload`
- `POST /upload/sql/tables`

Mapping and transformation:
- `POST /mapping/auto`
- `POST /mapping/preview`
- `POST /mapping/codegen`
- `GET /mapping/transformation/templates`
- `POST /mapping/transformation/generate`
- `POST /mapping/sets`
- `GET /mapping/sets`
- `GET /mapping/sets/{mapping_set_id}`
- `POST /mapping/sets/{mapping_set_id}/status`
- `GET /mapping/sets/{mapping_set_id}/audit`
- `POST /mapping/transformation/test-sets`
- `GET /mapping/transformation/test-sets`
- `GET /mapping/transformation/test-sets/{test_set_id}`
- `POST /mapping/transformation/test-sets/{test_set_id}/run`

Observability and feedback:
- `GET /observability/decision-logs`
- `GET /observability/corrections`
- `POST /observability/corrections`
- `GET /observability/corrections/reusable-rules`
- `GET /observability/corrections/reusable-rules/active`
- `POST /observability/corrections/reusable-rules/promote`
- `GET /observability/config`
- `POST /observability/config/reload`

Knowledge overlays:
- `POST /knowledge/overlays/validate`
- `POST /knowledge/overlays`
- `GET /knowledge/overlays`
- `GET /knowledge/overlays/{overlay_id}`
- `POST /knowledge/overlays/{overlay_id}/activate`
- `POST /knowledge/overlays/{overlay_id}/deactivate`
- `POST /knowledge/overlays/{overlay_id}/archive`
- `POST /knowledge/overlays/rollback`
- `GET /knowledge/audit`
- `GET /knowledge/canonical-glossary/export`
- `POST /knowledge/canonical-glossary/import`
- `POST /knowledge/reload`

Evaluation:
- `GET /evaluation/benchmark`
- `POST /evaluation/run`
- `POST /evaluation/datasets`
- `GET /evaluation/datasets`
- `POST /evaluation/datasets/{dataset_id}/run`
- `POST /evaluation/datasets/{dataset_id}/correction-impact`
- `GET /evaluation/runs`

## Outputs the Project Produces

The project currently produces the following categories of output:

### Mapping Outputs
- selected mapping decisions
- top-k ranked alternatives
- confidence labels
- signal breakdowns
- explanations
- canonical concept paths and source/target/project coverage summaries
- generated transformation suggestions and transformation mode
- versioned mapping sets with status metadata

### Execution Outputs
- projected target preview rows
- transformation previews with before/after samples and structured warnings
- generated Pandas code
- transformation test-set run results

### Observability Outputs
- decision logs
- correction records
- reusable rule candidates and promoted reusable rules
- mapping-set audit trail
- knowledge overlay audit trail
- runtime config snapshot

### Evaluation Outputs
- benchmark metrics
- saved benchmark dataset records
- persisted evaluation run records

## Current Milestone Status

The current delivered baseline includes a completed canonical semantic layer MVP, completed Phase 1 cleanup, and completed Phase 2 Streamlit decomposition.

The product now includes:
- multi-format row-data upload plus SQL schema snapshots
- explainable multi-signal mapping with constrained AI assistance
- custom knowledge overlays with lifecycle actions and audit history
- initial canonical semantic layer with a business glossary, canonical signal, concept-aware trust layer, explicit source -> concept -> target views, and project-level coverage metrics
- correction learning with promoted reusable rules
- transformation preview safety checks, templates, and transformation test sets
- versioned mapping sets with lightweight status workflow and audit trail
- persisted benchmarks and correction-impact evaluation
- internal Streamlit review UI spanning upload, trust layer, corrections, knowledge, benchmarks, and admin/debug surfaces through a modular `streamlit_ui/*` layer

What is not closed yet:
- the hardening/debt package described as Phase 0 is still open and was not part of the recent delivery slice
- deeper governance remains intentionally narrow for now; the remaining Epic 6 work is mainly the export/run status gate

This puts Semantra in a strong internal-alpha / pilot-ready state for controlled schema-mapping workflows.

## Next Recommended Milestone

The next planned milestone is to finish the remaining status-gate part of Epic 6 on top of the already extended mapping-set workflow.

Most natural next steps inside that remaining slice are:
- enforce clearer status gates for export and run flows so non-approved versions are blocked or explicitly flagged
- tighten any follow-up tests around that gate without widening the workflow unnecessarily

After that, the next refactor-heavy move remains Phase 3 decomposition of the mapping engine.

## Result for the User

From a user perspective, the result of using Semantra is not just a guessed field mapping.

The result is a controlled semantic-mapping package made of:
- dataset understanding
- candidate ranking
- final mapping decisions
- explanation of why decisions were made
- canonical concept paths and project-level semantic coverage for the active mapping context
- reusable organizational knowledge from overlays and promoted rules
- preview of transformed data
- starter implementation code
- transformation validation and transformation regression cases
- audit trail of knowledge and mapping-set changes
- reusable correction memory
- measurable quality metrics

## Current Technical Status

At the current stage, Semantra is no longer just a scaffold. It contains:
- a real mapping engine with multiple explainable signals
- constrained LLM validation and transformation generation hooks
- runtime metadata enrichment with custom knowledge overlays
- canonical business glossary-driven matching with explicit canonical path payloads and import/export support
- persisted correction learning plus promoted reusable rules
- persisted mapping sets and transformation test sets
- benchmark and correction-impact evaluation tooling
- a working internal-alpha Streamlit review UI with extracted `streamlit_ui/*` modules and `streamlit_app.py` reduced to composition/root orchestration
- focused automated tests around backend services, API flows, and key Streamlit helpers

The biggest remaining growth areas are now mostly P1 and beyond:
- richer trust-layer explanations and analyst tooling
- deeper governance features beyond the current minimal mapping-set and glossary workflow, starting with Epic 6
- broader canonical business concept governance and reuse beyond the current glossary-driven MVP
- stronger connector story beyond flat files and SQL snapshots
- eventual execution and operationalization beyond preview/codegen

## Short Summary

Semantra is an explainable semantic mapping and review engine that profiles source and target schemas, ranks and validates mapping candidates, reasons over canonical business concepts, previews and tests reviewed transformations, learns from analyst feedback, and persists knowledge, reusable rules, mapping sets, and evaluation artifacts through a FastAPI backend and Streamlit review UI.