# Semantra

Semantra is a pilot-ready semantic integration workbench for analyst-guided schema mapping.

It combines deterministic profiling and ranking with controlled AI assistance so a team can:

- upload source and target structures from row data, schema specs, or SQL snapshots
- generate explainable source-to-target or source-to-canonical mapping proposals
- review explicit source -> concept -> target paths and canonical coverage
- author and validate Pandas transformations
- preview mapped output and generate starter Pandas code
- persist governed mapping sets, benchmark datasets, transformation test sets, and review memory
- manage canonical concepts, overlays, and stewardship workflows through a dedicated Canonical Console
- search and reuse approved integration knowledge through the Catalog

The current product shape is a FastAPI backend plus a Streamlit product UI. It is already useful for demos, pilot workflows, and controlled analyst/governance review. It is not yet a production ETL runtime, scheduler, or connector-heavy integration platform.

## Current Product Surface

Top-level UI areas:

- `Workspace`
  - upload, profile, map, review, decide, preview, and codegen
- `Canonical Console`
  - canonical concept registry, overlay lifecycle, canonical-gap stewardship, and stable glossary promotion
- `Catalog`
  - searchable integration and concept reuse inventory based on saved mapping sets
- `Benchmarks`
  - benchmark dataset save/run flows, correction impact, and run history
- `Admin / Debug`
  - runtime config, observability, and supporting admin surfaces

Core implemented capabilities:

- CSV, JSON, XML, XLSX, SQL snapshot, and schema-spec ingestion
- standard source-to-target mapping and canonical-only source-to-concept mapping
- explainable multi-signal ranking with optional closed-set LLM validation
- trust-layer review with canonical path visibility and coverage summaries
- transformation generation, templates, preview validation, and Pandas code generation
- governed mapping-set persistence with status, audit, diff, and approved-only reuse
- correction persistence and reusable correction-rule promotion
- canonical glossary import/export, knowledge overlays, and stewardship items
- integration catalog search/detail/reuse flows
- benchmark datasets, evaluation runs, and correction-impact measurement

For the full grounded feature inventory, see `project_docs/current_state.md`.

## Quick Start

### 1. Install dependencies

Use a Python environment and install the project requirements from the repo root.

```bash
pip install -r requirements.txt
```

### 2. Configure optional runtime settings

If needed, create `backend/.env` and set values such as:

- `SEMANTRA_ADMIN_API_TOKEN`
- `SEMANTRA_LLM_PROVIDER`
- `SEMANTRA_LLM_MODEL`
- `SEMANTRA_LMSTUDIO_BASE_URL`
- `SEMANTRA_OPENAI_API_KEY`
- `SEMANTRA_GEMINI_API_KEY`

### 3. Start the app

Windows-friendly launcher:

```powershell
./start_semantra.ps1
```

This starts:

- API at `http://127.0.0.1:8000`
- Streamlit UI at `http://127.0.0.1:8501`

Manual start is also possible:

```bash
python -m uvicorn app.main:app --reload --app-dir backend --reload-dir backend
python -m streamlit run streamlit_app.py
```

## Runtime Notes

### Admin token

If you want protected governance/admin flows enabled, set `SEMANTRA_ADMIN_API_TOKEN` in `backend/.env`, then restart the backend or call `POST /observability/config/reload` with the token in `X-Admin-Token`.

### LLM providers

The app supports bounded LLM use for validation, transformation generation, and canonical-gap assistance.

Example for LM Studio:

- `SEMANTRA_LLM_PROVIDER=lmstudio`
- `SEMANTRA_LLM_MODEL=<model-identifier>` or `SEMANTRA_LLM_MODEL=auto`
- `SEMANTRA_LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1/chat/completions`

### Scoring note

The mapping confidence score is a normalized multi-signal heuristic, not a calibrated probability.

- the final score is normalized into `0..1`
- current thresholds are `high >= 0.85`, `medium >= 0.65`, otherwise `low`
- treat the score as review prioritization, not as a guarantee that a mapping is correct
- the active score profile is configurable via `SEMANTRA_SCORING_PROFILE` (`balanced`, `schema_only`, `data_rich`, `canonical_first`)
- the active profile can be fine-tuned with `SEMANTRA_SCORING_WEIGHT_OVERRIDES` as a JSON object in `backend/.env`
- compare built-in scoring profiles locally with `backend/scripts/run_scoring_profile_benchmark.py`

For the detailed reference on signals, weights, confidence labels, and bounded LLM validation cases, see `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`.

For the detailed reference on benchmark metrics, confidence buckets, and correction-impact interpretation, see `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`.

## Product Boundaries

Semantra today is:

- a pilot-grade semantic mapping and governance workbench
- deterministic-first, with bounded AI assistance
- centered on reviewability, explainability, and reusable semantic knowledge

Semantra today is not yet:

- a production batch orchestration platform
- a connector-heavy ingestion platform
- a multi-step enterprise workflow engine
- a DB-only canonical authoring platform without file-backed reseed inputs

## Documentation Map

Read the docs in this order:

1. `project_docs/current_state.md`
	- what the product actually supports today
2. `PROJECT_OVERVIEW.md`
	- broader product and architecture explanation
3. `project_docs/completed_slices.md`
	- chronological delivery history
4. `project_docs/plan.md`
	- forward-looking priorities and sequencing
5. `project_docs/epics.md`
	- backlog map and epic status
6. `project_docs/implementation_checklists.md`
	- active execution checklists
7. `help.md` / `help.en.md`
	- practical UI usage guides

Supporting docs:

- `docs/pilot/REAL_LIFE_PILOT_TEST_PLAN.md`
- `docs/vision/INTEGRATION_CATALOG_VISION.md`
- `docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md`
- `docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md`
- `docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md`
- `docs/reference/MAPPING_SIGNALS_AND_SCORING.md`
- `docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md`
- `docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md`
- `docs/presentation/presentation.md`