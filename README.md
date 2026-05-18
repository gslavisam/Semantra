# Semantra

Semantra is a pilot-ready semantic integration workbench for analyst-guided schema mapping, review, governance, and reuse.

It combines deterministic profiling and ranking with bounded AI assistance so a team can:

- upload source and target structures from row data, schema specs, or SQL snapshots
- generate explainable source-to-target or source-to-canonical mapping proposals
- review explicit source -> concept -> target paths and canonical coverage
- generate technical mapping analysis summaries and optional narration/audio
- author transformations, preview output, and generate starter Pandas or PySpark artifacts
- refine generated artifacts through controlled LLM prompts with accept/discard workflow
- persist governed mapping sets, benchmark datasets, transformation test sets, and correction history
- manage canonical concepts, overlays, and stewardship workflows through a dedicated Canonical Console
- search, inspect, and reuse approved integration knowledge through the Catalog
- measure quality through benchmark runs, profile comparison, correction impact, and explanation surfaces

The current product shape is a FastAPI backend plus a Streamlit product UI. It is already useful for demos, pilot workflows, and controlled analyst/governance review. It is not yet a production ETL runtime, scheduler, or connector-heavy integration platform.

## Current Product Surface

Top-level UI areas:

- `Workspace`
	- upload, profile, map, review, decide, preview, codegen, and artifact refinement
- `Canonical Console`
	- canonical concept registry, overlay lifecycle, canonical-gap stewardship, and stable glossary promotion
- `Catalog`
	- searchable integration inventory, concept-centric reuse views, and workspace-fit explanation for approved reuse candidates
- `Benchmarks`
	- benchmark dataset save/run flows, scoring-profile comparison, correction impact, run history, and bounded explanation
- `Admin / Debug`
	- runtime config, observability, and supporting admin surfaces

Core implemented capabilities:

- CSV, JSON, XML, XLSX, SQL snapshot, and schema-spec ingestion
- source-side and target-side companion metadata enrichment over uploaded dataset handles
- standard source-to-target mapping and canonical-only source-to-concept mapping
- explainable multi-signal ranking with optional closed-set LLM validation
- configurable canonical candidate pool shortlisting before full canonical scoring
- Mapping Analysis Overview with optional narration/audio generation
- Review Queue Plan and Gap Queue Summary for queue-level review guidance
- per-row and batch LLM mapping refinement with transient field context and accept/revert controls
- transformation generation, templates, advisory preview, and Pandas/PySpark starter generation
- canonical-mode manual mapping and canonical-mode code generation against virtual canonical targets
- LLM-based artifact refinement with split-view compare and accept/discard actions
- governed mapping-set persistence with status, audit, diff, and approved-only reuse
- correction persistence and reusable correction-rule promotion
- canonical glossary import/export, knowledge overlays, stewardship items, and Canonical Console workflows
- integration catalog search/detail/reuse flows with workspace reuse-fit assessment
- benchmark datasets, evaluation runs, scoring-profile comparison, correction impact, and benchmark explanation

For the full grounded feature inventory, see `project_docs/current_state.md`.

## Guided AI Surfaces

Semantra does not use LLMs as an autonomous mapper. The current bounded AI surfaces are:

- closed-set mapping validation inside the ambiguity band
- Mapping Analysis Overview, narration, and audio generation
- transformation code generation
- artifact refinement in `Workspace > Output`
- review queue planning in `Workspace > Review`
- canonical-gap suggestion and queue summary
- benchmark explanation
- catalog workspace reuse-fit explanation

Each of these surfaces is optional, inspectable, and backed by deterministic fallback behavior where applicable.

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

The app supports bounded LLM use for validation, review guidance, transformation generation, artifact refinement, benchmark explanation, canonical-gap assistance, and reuse-fit assessment.

Example for LM Studio:

- `SEMANTRA_LLM_PROVIDER=lmstudio`
- `SEMANTRA_LLM_MODEL=<model-identifier>` or `SEMANTRA_LLM_MODEL=auto`
- `SEMANTRA_LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1/chat/completions`

### Scoring note

The mapping confidence score is a normalized multi-signal heuristic, not a calibrated probability.

- the final score is normalized into `0..1`
- current thresholds are `high >= 0.85`, `medium >= 0.65`, otherwise `low`
- current auto-accept threshold is `>= 0.75`, separate from the confidence-label buckets
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
- a durable multi-user job runtime with persistent queue semantics

## Documentation Map

Read the docs in this order:

1. `project_docs/current_state.md`
	 - what the product actually supports today
2. `PROJECT_OVERVIEW.md`
	 - broader product, architecture, and governance explanation
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

## Immediate Next Steps

The next project focus is not more feature sprawl. It is:

1. productizing the new bounded guidance surfaces so they are easier to discover and use consistently in pilot flows
2. expanding catalog and concept-level reuse discovery beyond the initial slice
3. continuing regression hardening and runtime discipline on the existing pilot surfaces
4. separating persistence/runtime concerns where the current local model is starting to show strain