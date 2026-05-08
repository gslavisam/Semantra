# Semantra

Semantra is an explainable semantic mapping workbench for source-to-target schemas.

In short, the project combines deterministic profiling and ranking with controlled AI assistance so a team can:
- upload source and target datasets or SQL schema snapshots
- rank mapping candidates with explainable multi-signal scoring
- enrich matching with metadata knowledge, a canonical business glossary, custom knowledge overlays, correction history, and promoted reusable rules
- inspect explicit source -> concept -> target paths and project-level canonical coverage in the trust layer
- generate and review field-level pandas transformations
- preview mapped output and generate starter Pandas code
- persist mapping sets, transformation test sets, benchmark datasets, and evaluation history

The current product shape is a FastAPI backend plus an internal Streamlit review UI. It is already useful for demos, pilot workflows, and controlled analyst review, but it is not a full ETL or orchestration platform yet.

## Run locally

1. Create or activate a Python environment.
2. Install dependencies from `requirements.txt` in the project root.
3. Optionally copy `backend/.env.example` to `backend/.env` and set your provider values.
4. Start the API:

```bash
uvicorn app.main:app --reload --app-dir backend
```

5. Optionally start the Streamlit internal-beta UI:

```bash
streamlit run streamlit_app.py
```

## What It Covers

The current product slice covers:
- source and target upload from CSV, JSON, XML, XLSX, or SQL schema snapshots
- schema profiling with lexical, semantic, pattern, and statistical hints
- explainable auto-mapping with top-k ranked candidates per source field
- canonical business glossary matching with concept-aware explanations, explicit source -> concept -> target review tables, and project-level canonical coverage
- optional constrained LLM validation for ambiguous matches
- prompt-driven pandas transformation generation for reviewed mappings
- transformation preview with syntax/runtime validation, before/after samples, and structured warnings
- custom knowledge overlays on top of the built-in metadata dictionary, including concept aliases bound to canonical business concepts
- canonical glossary CSV import/export from the admin/debug surface
- persisted user corrections, promoted reusable rules, benchmark datasets, evaluation runs, transformation test sets, and versioned mapping sets with lightweight governance metadata and version diff support
- internal Streamlit review UI for trust-layer review, admin/debug flows, corrections, benchmarks, and saved mapping-set workflows

## Project Shape

Semantra currently runs as:
- a FastAPI backend for upload, mapping, observability, knowledge, and evaluation APIs
- a Streamlit internal review UI for analysts and pilot/demo workflows
- a SQLite persistence layer for durable review memory and governance artifacts

The Streamlit side was recently decomposed so `streamlit_app.py` now acts mainly as a composition root over the extracted `streamlit_ui/*` modules.

Current roadmap note: canonical semantic layer MVP, Phase 1 cleanup, and Phase 2 Streamlit decomposition are done; Epic 6 Governance MVP has started with mapping-set owner/assignee/review-note metadata plus version diff and apply-audit support, while the separate Phase 0 hardening package remains open.

This is already a strong internal-beta / pilot-grade mapping product slice. It is not yet a production orchestration platform, a connector-heavy ingestion platform, or a full semantic operating model.

## Scoring Note

The mapping confidence score is a normalized multi-signal heuristic, not a calibrated probability.

- individual signals such as lexical, semantic, knowledge, pattern, overlap, optional embedding, historical correction, and optional LLM validation are combined into a weighted average
- the final score is normalized and clamped to the `0..1` range
- current confidence labels are threshold-based over that normalized score: `high_confidence >= 0.85`, `medium_confidence >= 0.65`, otherwise `low_confidence`

This makes the thresholds operationally easier to read, but they should still be treated as review heuristics rather than statistical confidence guarantees.

## Runtime Notes

If you want protected admin flows enabled, set `SEMANTRA_ADMIN_API_TOKEN` in `backend/.env`, then restart the API or call `POST /observability/config/reload` with the same token in the `X-Admin-Token` header.

For LM Studio or another OpenAI-compatible local runtime, configure these in `backend/.env`:
- `SEMANTRA_LLM_PROVIDER=lmstudio`
- `SEMANTRA_LLM_MODEL=<model-identifier>`
- `SEMANTRA_LMSTUDIO_BASE_URL=http://<host>:1234/v1/responses`

To run a saved benchmark from the terminal and inspect recent run history:

```bash
cd backend
python scripts/run_saved_benchmark.py --dataset-id 1 --with-llm
```

If you prefer the PowerShell wrapper that auto-loads `backend/.env`:

```powershell
cd Semantra/backend
./scripts/run_saved_benchmark.ps1 -DatasetId 1 -WithLlm
```

## Project Docs

Use these docs with different intent:
- `README.md`: quick project summary, local run instructions, and high-level capability list
- `PROJECT_OVERVIEW.md`: broader product and technical architecture overview
- `project_docs/plan.md`: strategic roadmap, technical phases, working order, and execution rules
- `project_docs/epics.md`: epic backlog and scope catalog
- `project_docs/implementation_checklists.md`: active MVP and release checklists
- `project_docs/completed_slices.md`: delivered slices and completed technical phases
- `docs/pilot/REAL_LIFE_PILOT_TEST_PLAN.md`: concrete pilot-validation plan for realistic source/target datasets before wider rollout or refactor
- `docs/vision/INTEGRATION_CATALOG_VISION.md`: deeper product and architecture memo for the integration catalog direction
- `docs/presentation/presentation.md`: presentation and demo narrative for stakeholder-facing walkthroughs
- `help.md`: practical usage guide in Serbian for the Streamlit `Workspace`, `Benchmarks`, and `Admin / Debug` tabs
- `help.en.md`: practical usage guide in English for the Streamlit `Workspace`, `Benchmarks`, and `Admin / Debug` tabs