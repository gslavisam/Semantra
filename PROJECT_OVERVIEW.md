# Project Overview

## What Semantra Is

Semantra is a backend-first AI semantic bridge MVP for explainable data mapping between source and target tabular schemas.

The project focuses on a controlled mapping workflow:
- ingest source and target datasets
- profile both schemas
- rank candidate field mappings with multiple signals
- optionally use a constrained LLM validator for ambiguous cases
- optionally ask the active LLM runtime to generate pandas transformation code from a natural-language instruction
- return final mapping decisions plus top-k alternatives
- preview transformed rows, including reviewed transformations
- generate starter Pandas transformation code from accepted mapping decisions
- log decisions, capture user corrections, and evaluate mapping quality

Semantra is not a full ETL platform yet. It is currently the semantic mapping and quality-control engine that can later sit behind a UI, a workflow runner, or a larger migration product.

## Product Goal

The goal of Semantra is to make schema mapping:
- explainable
- measurable
- reviewable
- improvable over time

Instead of relying on a free-form LLM to "map everything", Semantra uses a deterministic-first pipeline with tightly constrained AI assistance.

## Current Scope

Current MVP scope includes:
- CSV, JSON, XML, and XLSX row-data upload for source and target datasets
- SQL schema snapshot upload for source and target datasets
- SQL table discovery and explicit table selection for multi-table schema snapshots
- schema profiling
- multi-signal mapping heuristics
- top-k candidate ranking per source field
- global one-to-one target assignment
- optional constrained LLM validation in ambiguity-band cases
- prompt-driven transformation generation for reviewed source-to-target pairs
- preview of projected target rows with transformation execution
- manual mapping editor in the Streamlit review UI (add / override / remove manual mappings, persisted as corrections)
- Pandas code generation for selected mappings, including reviewed transformation statements
- observability endpoints for decision logs and runtime config
- persisted user corrections and benchmark datasets in SQLite
- persisted evaluation run history in SQLite
- benchmark evaluation endpoints and internal test fixtures
- Streamlit internal-alpha UI for upload, trust-layer review, transformations, corrections, benchmarks, and admin/debug flows, including knowledge-match inspection for the active mapping response

Out of scope for the current slice:
- authentication and role-based access control
- production-grade frontend
- database connectors beyond the current flat-file workflow
- distributed job orchestration
- complex multi-table graph mapping
- production writeback into destination systems

## Core Concept

Semantra treats data mapping as a multi-signal inference problem.

Each source field is compared against target fields using several signals:
- lexical similarity
- semantic similarity after normalization and synonym expansion
- internal metadata knowledge and vendor context priors
- data pattern similarity
- statistical similarity
- sample value overlap
- optional embedding similarity
- historical correction feedback
- optional constrained LLM validator signal

This produces a ranked candidate list, not a blind single guess.

## Main Functional Areas

### 1. Dataset Ingestion

Purpose:
- accept uploaded row-based files and schema snapshots
- assign dataset identifiers
- store raw rows in memory for active workflow use

Key behavior:
- source and target datasets are uploaded separately
- row-based uploads currently support CSV, JSON, XML, and XLSX
- SQL uploads remain schema-only and can require explicit table selection for multi-table snapshots
- each upload produces a dataset handle and schema profile
- preview rows are retained for fast downstream inspection

Implementation anchor:
- `backend/app/api/routes/upload.py`
- `backend/app/services/tabular_upload_service.py`
- `backend/app/services/upload_store.py`

### 2. Schema Profiling

Purpose:
- understand each field before attempting semantic mapping

For each column, Semantra extracts:
- name
- normalized name
- tokenized name
- inferred dtype
- null ratio
- unique ratio
- average value length
- sample values
- distinct sample values
- detected patterns such as `phone`, `email`, `date`, `numeric_id`, `categorical`, or `text`

Implementation anchor:
- `backend/app/services/profiling_service.py`

### 3. Mapping Engine

Purpose:
- generate explainable mapping candidates from source schema to target schema

Current engine behavior:
- compute candidate scores across all source-target combinations
- sort candidates per source field
- return top-k alternatives
- apply a global one-to-one assignment step to reduce conflicting target reuse
- return selected mappings plus ranked alternatives

Current scoring model:
- each source-target pair is scored independently first
- the final heuristic score is a weighted sum of nine signals
- current weights are: name `0.20`, semantic `0.12`, knowledge `0.10`, pattern `0.20`, statistical `0.15`, overlap `0.10`, embedding `0.12`, correction `0.10`, LLM `0.05`
- because those weights currently sum to `1.04`, the score is best understood as a ranking signal rather than a calibrated probability

Current signal implementation:
- name similarity blends `0.6 * fuzzy_similarity(normalized_name)` and `0.4 * jaccard_similarity(tokenized_name)`
- semantic similarity compares normalized semantic token sets after synonym expansion and metadata-driven alias enrichment
- knowledge similarity uses curated internal business concepts plus SAP/QAD/Workday field and object context from the local metadata assets under `metadata_dict/`
- pattern similarity compares detected pattern tags such as `email`, `phone`, or `date`
- statistical similarity averages distance-based similarity across `unique_ratio`, `null_ratio`, and capped normalized `avg_length`
- overlap similarity measures shared distinct sample values
- embedding similarity is cosine similarity over normalized field-name embeddings when an embedding provider is enabled, otherwise `0`
- correction feedback comes from persisted user corrections and can both boost corrected targets and penalize previously wrong suggestions
- the LLM signal starts at `0` and is populated only if the ambiguity-band validator is invoked and accepts a candidate

Current knowledge sources:
- `metadata_dict/metadata_dict.csv` provides multilingual canonical concepts, aliases, naming conventions, and vendor-style column names
- `metadata_dict/metadata_dictionary.xlsx` adds curated SAP/QAD/Workday field mappings and business notes
- `metadata_dict/sap_tables_mostUsed.xlsx`, `metadata_dict/qad_tables_mostUsed.xlsx`, and `metadata_dict/WD_entities_mostUsed.xlsx` contribute object-level descriptions that are used as context priors

Assignment and labeling behavior:
- after per-source ranking, Semantra performs a greedy global one-to-one assignment across all source-target edges
- the global sort order prefers higher final score first, then pattern, semantic, and embedding signal values as tie-breakers
- the API still returns top-k ranked alternatives per source field for review, even when the selected target comes from the global assignment step
- default confidence thresholds are `>= 0.85` for `high_confidence`, `>= 0.65` for `medium_confidence`, otherwise `low_confidence`

Implementation anchor:
- `backend/app/services/mapping_service.py`

### 4. Constrained LLM Validation

Purpose:
- resolve uncertainty in borderline mapping cases without giving full control to a generative model

Current design:
- LLM is only used inside a score gate defined by ambiguity thresholds
- it receives only a closed set of candidates
- it must return strict JSON
- it can choose one of the provided targets or `no_match`
- invalid or hallucinated outputs are discarded
- by default it is only called when the best heuristic score is strictly between `0.40` and `0.75`
- when it selects one of the provided candidates, its confidence is written into the dedicated `llm` signal and the candidate is re-scored and re-ranked inside that closed candidate set

Provider support currently exists for:
- OpenAI Responses API
- OpenAI-compatible LM Studio responses endpoints
- Ollama
- static/mock provider for tests

Implementation anchor:
- `backend/app/services/llm_service.py`

### 5. Preview and Code Generation

Purpose:
- show what the mapping will do before execution
- provide a deterministic transformation artifact

Outputs:
- projected preview rows for accepted mappings, including reviewed transformation code when present
- generated Pandas code for building a target dataframe from source columns and transformation statements

Implementation anchors:
- `backend/app/services/preview_service.py`
- `backend/app/services/codegen_service.py`

### 6. Prompt-Driven Transformation Generation

Purpose:
- let an operator describe a desired field-level transformation in natural language
- convert that instruction into pandas-oriented Python scoped to the chosen source and target columns

Current design:
- generation is explicit and user-invoked from the Streamlit trust layer
- the backend inspects the selected source and target column profiles before building the prompt
- the LLM must return strict JSON containing `transformation_code`
- generated code is shown in the UI first and is only used for preview/codegen after the operator applies it
- if the target changes, stale suggested transformation code is not reused automatically

Implementation anchors:
- `backend/app/api/routes/mapping.py`
- `backend/app/services/llm_service.py`
- `streamlit_app.py`

### 7. Observability and Feedback

Purpose:
- make mapping decisions inspectable
- allow the system to improve from explicit user corrections

Current capabilities:
- decision log listing
- user correction creation and listing
- runtime config inspection and reload
- correction-aware scoring in future runs
- correction boost for confirmed targets
- correction penalty for previously wrong suggestions

Implementation anchors:
- `backend/app/api/routes/observability.py`
- `backend/app/services/decision_log_service.py`
- `backend/app/services/correction_service.py`

### 8. Evaluation and Benchmarking

Purpose:
- measure mapping quality objectively

Current capabilities:
- run built-in benchmark fixture
- run ad hoc benchmark payloads
- save benchmark datasets in SQLite
- list saved benchmark datasets
- re-run saved benchmark datasets

Returned metrics:
- total cases
- total fields
- correct matches
- accuracy
- top-1 accuracy
- confidence-bucket performance

Implementation anchors:
- `backend/app/api/routes/evaluation.py`
- `backend/app/services/evaluation_service.py`
- `backend/app/tests/fixtures/mapping_gold.json`

## Main Workflows

Semantra currently supports six practical workflows.

### Workflow 1. Upload and Profile

Input:
- source CSV, JSON, XML, XLSX, or SQL
- target CSV, JSON, XML, XLSX, or SQL

Process:
- parse files
- create dataset IDs
- build schema profiles
- store preview rows
- inspect SQL snapshots for available tables when needed

Result:
- dataset handles
- profiled source schema
- profiled target schema

Endpoint:
- `POST /upload`

Related endpoint:
- `POST /upload/sql/tables`

### Workflow 2. Auto-Mapping

Input:
- source dataset ID
- target dataset ID

Process:
- score all candidate mappings
- rank top-k candidates per source field
- optionally run constrained LLM validation on ambiguity-band cases
- perform global one-to-one assignment
- log final decisions

Result:
- selected mappings
- ranked candidate lists
- explanations and signal breakdowns

Endpoint:
- `POST /mapping/auto`

### Workflow 3. Preview Transformation

Input:
- source dataset ID
- explicit mapping decisions

Process:
- project source rows into target-shaped preview rows
- execute reviewed `transformation_code` when present
- attach warnings for missing fields or unresolved cases
- fall back to direct mapping if a transformation fails at preview time

Result:
- preview rows
- unresolved targets list

Endpoint:
- `POST /mapping/preview`

### Workflow 4. Generate Transformation from Prompt

Input:
- source dataset ID
- target dataset ID
- source column
- target column
- natural-language instruction

Process:
- build a prompt from source and target field profiles plus the user's intent
- call the configured runtime LLM provider
- validate and sanitize returned JSON
- surface the resulting pandas code back to the review UI

Result:
- generated transformation code
- LLM reasoning and warnings

Endpoint:
- `POST /mapping/transformation/generate`

### Workflow 5. Generate Pandas Code

Input:
- explicit mapping decisions

Process:
- emit starter Pandas assignments or reviewed transformation statements

Result:
- generated Python artifact
- warnings for rejected mappings

Endpoint:
- `POST /mapping/codegen`

### Workflow 6. Observe, Correct, and Evaluate

Input:
- decision logs, correction entries, benchmark cases, saved benchmark datasets

Process:
- inspect decisions
- persist user feedback
- reload runtime config
- run default or custom evaluation sets
- save and re-run benchmark datasets

Result:
- audit trail
- reusable feedback memory
- benchmark metrics
- runtime settings visibility

Endpoints:
- `GET /observability/decision-logs`
- `GET /observability/corrections`
- `POST /observability/corrections`
- `GET /observability/config`
- `POST /observability/config/reload`
- `GET /evaluation/benchmark`
- `POST /evaluation/run`
- `POST /evaluation/datasets`
- `GET /evaluation/datasets`
- `POST /evaluation/datasets/{dataset_id}/run`
- `GET /evaluation/runs`

### Workflow 7. Review in Streamlit UI

Input:
- uploaded source and target files
- reviewed mapping decisions
- optional correction notes and benchmark names

Process:
- upload source and target datasets through the UI
- inspect schema summaries and SQL table selections
- generate and review mapping suggestions
- inspect transformation mode and prompt the active LLM runtime for pandas transformation code
- apply generated/custom transformation code before preview/codegen
- edit decisions manually
- save corrections
- save and run benchmark datasets
- inspect runtime config and benchmark history

Result:
- internal-alpha operator workflow over the existing backend
- faster product validation for real scenarios

Implementation anchor:
- `streamlit_app.py`

## Architecture

Semantra uses a layered backend architecture.

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
- preview
- code generation
- decision logging
- correction handling
- persistence
- evaluation

Location:
- `backend/app/services/`

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
   - saved benchmark datasets
   - saved evaluation runs

## Current API Surface

Semantra currently exposes these endpoints:

- `POST /upload`
- `POST /upload/sql/tables`
- `POST /mapping/auto`
- `POST /mapping/preview`
- `POST /mapping/codegen`
- `POST /mapping/transformation/generate`
- `GET /observability/decision-logs`
- `GET /observability/corrections`
- `POST /observability/corrections`
- `GET /observability/config`
- `POST /observability/config/reload`
- `GET /evaluation/benchmark`
- `POST /evaluation/run`
- `POST /evaluation/datasets`
- `GET /evaluation/datasets`
- `POST /evaluation/datasets/{dataset_id}/run`
- `GET /evaluation/runs`

## Outputs the Project Produces

The project currently produces the following categories of output:

### Mapping Outputs
- selected mapping decisions
- top-k ranked alternatives
- confidence labels
- signal breakdowns
- explanations
- generated transformation suggestions and transformation mode

### Execution Outputs
- projected target preview rows
- generated Pandas code

### Observability Outputs
- decision logs
- correction records
- runtime config snapshot

### Evaluation Outputs
- benchmark metrics
- saved benchmark dataset records
- persisted evaluation run records

## Current Milestone Status

The current ingestion-and-review milestone is complete for internal alpha.

It now includes:
- row-based uploads across CSV, JSON, XML, and XLSX
- SQL schema snapshot support with multi-table discovery and explicit table selection
- persisted corrections, benchmark datasets, and evaluation run history
- Streamlit review UI for upload, mapping review, transformation prompting, corrections, benchmarks, and admin/debug inspection
- real browser validation across CSV, JSON, XML, and XLSX review flows
- prompt-driven transformation generation validated end-to-end against an OpenAI-compatible LM Studio runtime
- Add Manual Mapping UI with add/override/remove behavior and persisted corrections
- full any-to-any row-format regression test coverage across CSV, JSON, XML, and XLSX (4x4 matrix)

There is no urgent blocker at this point.

## Next Recommended Milestone

The next practical milestone should focus on hardening and broadening the product surface rather than adding more core mapping logic.

Recommended next steps:
- expand real-scenario browser validation for mixed-format and multi-table SQL flows
- add more benchmark cases that reflect messy enterprise data
- refine review UX and import/export ergonomics in the Streamlit app
- prepare the connector path beyond flat files when the ingestion scope needs to grow

## Result for the User

From a user perspective, the result of using Semantra is not just a guessed field mapping.

The result is a controlled semantic-mapping package made of:
- dataset understanding
- candidate ranking
- final mapping decisions
- explanation of why decisions were made
- preview of transformed data
- starter implementation code
- audit trail of decisions
- reusable correction memory
- measurable quality metrics

## Current Technical Status

At the current stage, Semantra is no longer just a scaffold. It already contains:
- a real mapping engine
- constrained LLM validation hooks
- runtime observability
- persisted feedback and benchmark storage
- evaluation tooling
- a working internal-alpha Streamlit UI
- focused automated tests across core workflows

The product is now in a strong internal-alpha state. The biggest remaining areas for future growth are:
- access control around sensitive endpoints
- richer connectors beyond the current flat-file set
- stronger benchmark coverage
- a more production-ready review UI layer
- broader transformation support beyond direct column assignment

## Short Summary

Semantra is an explainable semantic mapping product slice that profiles source and target schemas, ranks and validates mapping candidates, previews the result, generates starter transformation code, and improves through feedback, observability, and benchmark-driven evaluation, now with an internal-alpha review UI on top of the backend.