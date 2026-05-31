# Semantra Developer Codebase Guide

This document is a narration-ready introduction to the Semantra codebase. It is meant for a developer who wants one structured pass through the Python project without jumping between many files first.

Use this guide together with the existing primary docs:

- `README.md` for product posture and local startup.
- `PROJECT_OVERVIEW.md` for architecture and the bounded-AI operating model.
- `project_docs/current_state.md` for the authoritative list of implemented product behavior.
- `project_docs/plan.md` and `project_docs/epics.md` for forward-looking work.

As of 2026-05-18, Semantra is a FastAPI backend plus a Streamlit UI over a SQLite persistence layer. The dominant product loop is:

1. ingest source and target structure
2. build schema profiles
3. rank mapping candidates with deterministic signals
4. guide review with bounded AI where useful
5. preview, transform, benchmark, and persist governed artifacts

## How To Read The Repo

If you are new to Semantra, start in this order:

1. `README.md`
2. `PROJECT_OVERVIEW.md`
3. `backend/app/main.py`
4. `backend/app/models/mapping.py`
5. `backend/app/services/mapping_service.py`
6. `streamlit_app.py`
7. `streamlit_ui/workspace_views.py`
8. `backend/app/services/persistence_service.py`
9. `backend/app/services/metadata_knowledge_service.py`
10. `backend/tests/test_mapping_service.py`

That path gives you the product story, API surface, core models, ranking engine, UI shell, persistence layer, and a realistic test anchor.

## Architectural Orientation

- `backend/app/main.py` wires the API routes.
- `backend/app/models/*` defines the core domain payloads shared across flows.
- `backend/app/services/*` holds the real product behavior: ingestion, ranking, review guidance, governance, persistence, overlays, evaluation, and generation.
- `streamlit_app.py` and `streamlit_ui/*` render the product surface and call the backend through a thin HTTP client.
- `backend/tests/*` and `tests/*` provide targeted regression coverage for backend and Streamlit helper logic.

Two practical boundaries matter while developing:

- the ranking path is deterministic-first, with LLM use only in bounded and inspectable surfaces
- governance rules are real backend contracts, not just UI hints

## Root-Level Python Files

- `streamlit_app.py`: main Streamlit entrypoint and top-level UI shell; keeps many helper imports local so AST-based tests can load specific functions without importing the whole UI stack.

## Support Utilities

- `support/vendor_ingest/parse_hrdh_columns.py`: offline utility that parses an HR Data Hub Excel export and emits a knowledge overlay CSV plus candidate canonical additions.
- `support/vendor_ingest/parse_workday_xsd.py`: offline utility that parses Workday XSD metadata and produces a knowledge overlay CSV plus canonical concept suggestions.
- `support/sap/*`: offline SAP inventory, promotion, prioritization, and context-materialization scripts used to produce reviewable runtime artifacts without polluting the repo root.

## Backend Application

### App Entry

- `backend/app/main.py`: creates the FastAPI app, configures CORS, and mounts the upload, mapping, catalog, evaluation, knowledge, and observability routers.

### Core Infrastructure

- `backend/app/core/config.py`: central settings loader; reads `.env` and environment variables for scoring thresholds, provider selection, TTS, CORS, SQLite path, and admin token behavior.
- `backend/app/core/logging.py`: tiny logging bootstrap used before the FastAPI app is created.

### API Dependencies

- `backend/app/api/deps.py`: admin-token dependency that guards protected routes when `SEMANTRA_ADMIN_API_TOKEN` is configured.

### API Routes

- `backend/app/api/routes/upload.py`: ingest endpoints for row-data files, SQL snapshots, schema-spec uploads, and companion metadata enrichment.
- `backend/app/api/routes/mapping.py`: main mapping workflow routes, including sync/async mapping, review-related actions, preview/codegen-adjacent flows, and mapping-set governance operations.
- `backend/app/api/routes/catalog.py`: catalog search, approved integration detail, and reuse-fit surfaces.
- `backend/app/api/routes/evaluation.py`: benchmark dataset CRUD-like flows, benchmark runs, scoring-profile comparison, and correction-impact evaluation.
- `backend/app/api/routes/knowledge.py`: canonical glossary, overlay lifecycle, stewardship items, import/export, runtime reload, and field-hint related endpoints.
- `backend/app/api/routes/observability.py`: runtime config inspection/reload, decision-log and correction inspection, plus admin observability endpoints.

### Domain Models

- `backend/app/models/mapping.py`: the largest domain model file; defines mapping candidates, mapping responses, scoring signals, canonical details, transformation preview warnings, mapping-set records, benchmark records, catalog records, and related request/response contracts.
- `backend/app/models/schema.py`: models for schema profiling, dataset handles, column statistics, preview rows, and detected pattern categories.
- `backend/app/models/knowledge.py`: models for canonical glossary entries, overlay rows, stewardship records, source field hints, and knowledge runtime status.

### Services

#### Mapping And Ranking

- `backend/app/services/mapping_service.py`: heart of Semantra; computes multi-signal mapping scores, applies one-to-one assignment, blends correction and canonical evidence, optionally gates closed-set LLM validation, and assembles explanations.
- `backend/app/services/mapping_job_service.py`: in-memory job runtime for async mapping requests, including capacity limits, cancellation, TTL cleanup, and runtime status reporting.
- `backend/app/services/embedding_service.py`: minimal embedding layer; currently supports disabled mode or deterministic hash-based embeddings plus cosine similarity.
- `backend/app/services/correction_service.py`: persists reviewed corrections and promotes reusable correction rules back into future ranking behavior.
- `backend/app/services/decision_log_service.py`: lightweight in-memory decision/audit log for local runtime inspection.

#### Ingestion And Profiling

- `backend/app/services/tabular_upload_service.py`: parses CSV, JSON, XML, and XLSX row-data payloads into normalized records.
- `backend/app/services/spec_upload_service.py`: parses schema-spec style uploads where each row describes one field instead of one business row.
- `backend/app/services/schema_snapshot_service.py`: extracts table and column structure from SQL DDL snapshots.
- `backend/app/services/profiling_service.py`: derives schema statistics such as null ratio, uniqueness, average length, sample values, and pattern hints.
- `backend/app/services/upload_store.py`: session-scoped in-memory dataset store that holds uploaded rows, schema profiles, preview rows, and merged companion metadata.
- `backend/app/services/source_field_hint_service.py`: merges companion source metadata such as descriptions, types, and sample values into an existing dataset profile.

#### Canonical And Knowledge Runtime

- `backend/app/services/metadata_knowledge_service.py`: manages canonical glossary state, knowledge aliases, field contexts, persisted runtime loading, overlay-aware concept lookup, and canonical refresh behavior.
- `backend/app/services/knowledge_overlay_service.py`: validates and manages overlay versions and related lifecycle operations before they affect the active runtime.
- `backend/app/services/canonical_gap_service.py`: extracts canonical-gap candidates from mapping output and supports review-time concept suggestion and approval paths.
- `backend/app/services/canonical_gap_triage_service.py`: summarizes the canonical-gap queue into grouped risks, priorities, and next-action guidance.
- `backend/app/services/virtual_target_service.py`: builds a virtual canonical target schema from the glossary so canonical-only mapping can behave like target-based mapping without a real target dataset.

#### Analysis, Guidance, And Narration

- `backend/app/services/mapping_analysis_service.py`: builds the Mapping Analysis Overview summary and spoken narration, with deterministic fallback and optional bounded LLM enhancement.
- `backend/app/services/review_plan_service.py`: creates review-queue level guidance so analysts can prioritize what to inspect first.
- `backend/app/services/catalog_reuse_fit_service.py`: explains how well an approved catalog integration fits the current workspace context.
- `backend/app/services/benchmark_explanation_service.py`: explains benchmark results and profile differences in a developer/analyst-readable form.
- `backend/app/services/mapping_audio_service.py`: converts narration text into WAV output through LM Studio Orpheus-style chunked TTS generation.

#### Transformation, Preview, And Output

- `backend/app/services/transformation_service.py`: builds transformation expressions, classifies risk, runs preview-oriented transformation logic, and prepares warning metadata.
- `backend/app/services/transformation_template_service.py`: serves reusable transformation templates for common mapping patterns.
- `backend/app/services/transformation_test_service.py`: saves and runs transformation test sets against current mapping logic.
- `backend/app/services/preview_service.py`: produces advisory row previews from active mapping decisions and transformations.
- `backend/app/services/codegen_service.py`: generates Pandas and PySpark starter artifacts, plus warning and fallback behavior around generated output.

#### LLM And Evaluation

- `backend/app/services/llm_service.py`: provider abstraction for OpenAI, LM Studio, Ollama, and Gemini; builds bounded prompts, normalizes structured outputs, and handles fallback behavior.
- `backend/app/services/evaluation_service.py`: evaluates mappings against saved benchmark datasets and compares scoring profiles or correction impact.

#### Persistence

- `backend/app/services/persistence_service.py`: largest persistence-oriented service; wraps SQLite reads and writes for mapping sets, overlays, stewardship, benchmark datasets, evaluation runs, corrections, transformation tests, catalog projections, and related audit metadata.

### Utilities

- `backend/app/utils/normalization.py`: text normalization helpers used for name cleanup, tokenization, and semantic preparation for matching.
- `backend/app/utils/similarity.py`: string and token similarity helpers plus small scoring utilities used by the ranking engine.
- `backend/app/utils/knowledge_text.py`: canonical alias normalization helpers, including numeric-only alias filtering used to keep glossary and overlay aliases clean.
- `backend/app/utils/tabular.py`: basic tabular parsing helpers for header normalization, nullish checks, payload decoding, and cell serialization.

## Backend Scripts

- `backend/scripts/run_scoring_profile_benchmark.py`: CLI tool that compares scoring profiles on a benchmark case file and recommends a default profile.
- `backend/scripts/run_saved_benchmark.py`: CLI tool that re-runs a saved benchmark dataset through the API and optionally prints recent evaluation runs.

## Streamlit UI

### Package And API Layer

- `streamlit_ui/__init__.py`: package marker for the Streamlit UI module set.
- `streamlit_ui/api.py`: HTTP client wrapper for the backend; centralizes API base URL handling, auth token usage, request helpers, and feature-specific API calls.

### Shared UI State And Helpers

- `streamlit_ui/mapping_state.py`: session-state utilities that keep mapping decisions, refinements, transformation choices, and current workflow state consistent across UI tabs.
- `streamlit_ui/mapping_helpers.py`: helper functions that derive selected mappings, transformation mode labels, canonical explanation lines, and trust-layer support data from current session state.
- `streamlit_ui/shared_views.py`: reusable rendering helpers for common UI blocks such as dataset summaries, last-action status, LLM runtime status, step indicators, and shared bounded `Workspace Copilot` behavior.
- `streamlit_ui/governance.py`: small governance-focused UI helper module that computes action block reasons and friendly API error messages for approved-only or accepted-only flows.

### Workspace Surfaces

- `streamlit_ui/workspace_views.py`: primary Workspace screen for upload, profiling, mapping execution, preview, transformation generation, main-panel `Workspace Copilot`, and core workflow actions.
- `streamlit_ui/workspace_review_views.py`: Workspace review surface for trust-layer inspection, per-row and batch LLM refinement, mapping analysis, review plan, and canonical gap guidance.
- `streamlit_ui/workspace_decision_views.py`: decision-management surface for saving reviewed mappings, mapping-set governance actions, corrections, and durable review outcomes.

### Catalog, Benchmarks, Governance, And System

- `streamlit_ui/catalog_views.py`: Catalog search, detail, concept-centric reuse, similar integration hints, and workspace reuse-fit explanation views.
- `streamlit_ui/benchmark_views.py`: benchmark dataset management, benchmark execution, profile comparison, correction impact, and benchmark explanation views.
- `streamlit_ui/admin_views.py`: Governance-facing `Canonical Console` and related system/observability support surfaces, including overlay lifecycle, stewardship queues, runtime status, config inspection, and observability readouts.

## Tests

### Backend Tests

- `backend/tests/test_api_smoke.py`: broad API smoke coverage across upload, mapping, catalog, evaluation, knowledge, and governance-adjacent happy paths.
- `backend/tests/test_canonical_gap_service.py`: verifies gap extraction and canonical suggestion logic.
- `backend/tests/test_canonical_mapping_api.py`: exercises canonical-only mapping flows through the API surface.
- `backend/tests/test_knowledge_overlay_service.py`: validates overlay parsing, lifecycle, and related knowledge behaviors.
- `backend/tests/test_llm_and_evaluation.py`: covers LLM-provider-facing flows and evaluation behavior.
- `backend/tests/test_mapping_job_service.py`: tests async mapping job lifecycle, limits, cancellation, and runtime status behavior.
- `backend/tests/test_mapping_service.py`: core ranking-engine regression suite for signals, assignment behavior, thresholds, and scoring profiles.
- `backend/tests/test_metadata_knowledge_mapping.py`: verifies integration between mapping and the metadata/knowledge/canonical runtime.
- `backend/tests/test_provider_and_persistence.py`: checks provider selection logic and persistence contracts.
- `backend/tests/test_spec_upload_api.py`: API tests for schema-spec detection and upload handling.
- `backend/tests/test_spec_upload_service.py`: service-level tests for schema-spec parsing and normalization.
- `backend/tests/test_tabular_utils.py`: tests lower-level row-data parsing and normalization utilities.
- `backend/tests/test_virtual_target_service.py`: verifies the virtual canonical target schema used in canonical-only mapping mode.

### Streamlit And UI Tests

- `tests/test_streamlit_api.py`: tests the Streamlit-side backend client wrapper.
- `tests/test_streamlit_admin_views.py`: tests Governance/System helper behavior around `Canonical Console`, overlays, and runtime-facing admin views.
- `tests/test_streamlit_benchmark_views.py`: tests benchmark UI helpers and state transitions.
- `tests/test_streamlit_catalog_views.py`: tests catalog UI helpers and reuse-oriented rendering logic.
- `tests/test_streamlit_shared_views.py`: tests common UI helper rendering support.
- `tests/test_streamlit_transformation_state.py`: tests transformation-related session-state logic.
- `tests/test_streamlit_workspace_decision_views.py`: tests decision/governance-related workspace helpers.
- `tests/test_streamlit_workspace_review_views.py`: tests review, explanation, and refinement support logic.
- `tests/test_streamlit_workspace_views.py`: tests the main workspace helper functions and workflow glue.

## Practical Mental Model For New Developers

When you change behavior in Semantra, ask which layer actually owns the contract:

- if the issue is parsing or schema inference, start in `tabular_upload_service.py`, `spec_upload_service.py`, `schema_snapshot_service.py`, or `profiling_service.py`
- if the issue is ranking or mapping confidence, start in `mapping_service.py`
- if the issue is canonical matching or overlay behavior, start in `metadata_knowledge_service.py` and `knowledge_overlay_service.py`
- if the issue is output generation or transformation preview, start in `transformation_service.py`, `preview_service.py`, or `codegen_service.py`
- if the issue is UI-only workflow state, start in `streamlit_ui/mapping_state.py` or the relevant `streamlit_ui/*_views.py`
- if the issue concerns durable artifacts, audit, or list/detail behavior, start in `persistence_service.py`

## Important Development Notes

- The product is deterministic-first. LLM usage is bounded and should stay optional, inspectable, and close to a concrete workflow step.
- Governance rules are enforced at the backend. Do not rely on Streamlit-only checks for approved-only or accepted-only flows.
- Mapping jobs are currently in-memory and thread-based. Do not assume they are restart-safe or cross-process-safe.
- Canonical and knowledge runtime are DB-first at runtime, but still support file-backed seed and reseed behavior.
- The largest blast-radius files today are `backend/app/services/persistence_service.py`, `backend/app/services/metadata_knowledge_service.py`, `backend/app/services/mapping_service.py`, and `streamlit_ui/admin_views.py`.

## Closing Orientation

Semantra is not organized like a thin CRUD app. The real product behavior sits in the service layer, while the Streamlit side mostly orchestrates user-facing flows over that backend. If you understand `mapping_service.py`, `metadata_knowledge_service.py`, `persistence_service.py`, `streamlit_app.py`, and the Workspace review views, you understand most of the system's current center of gravity.