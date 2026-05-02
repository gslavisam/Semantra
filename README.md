# Semantra

Semantra is an explainable semantic mapping workbench for source-to-target schemas.

In short, the project combines deterministic profiling and ranking with controlled AI assistance so a team can:
- upload source and target datasets or SQL schema snapshots
- rank mapping candidates with explainable multi-signal scoring
- enrich matching with metadata knowledge, custom knowledge overlays, correction history, and promoted reusable rules
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

5. Optionally start the Streamlit internal-alpha UI:

```bash
streamlit run streamlit_app.py
```

## What It Covers

The current product slice covers:
- source and target upload from CSV, JSON, XML, XLSX, or SQL schema snapshots
- schema profiling with lexical, semantic, pattern, and statistical hints
- explainable auto-mapping with top-k ranked candidates per source field
- optional constrained LLM validation for ambiguous matches
- prompt-driven pandas transformation generation for reviewed mappings
- transformation preview with syntax/runtime validation, before/after samples, and structured warnings
- custom knowledge overlays on top of the built-in metadata dictionary
- persisted user corrections, promoted reusable rules, benchmark datasets, evaluation runs, transformation test sets, and versioned mapping sets
- internal Streamlit review UI for trust-layer review, admin/debug flows, corrections, benchmarks, and saved mapping-set workflows

## Project Shape

Semantra currently runs as:
- a FastAPI backend for upload, mapping, observability, knowledge, and evaluation APIs
- a Streamlit internal review UI for analysts and pilot/demo workflows
- a SQLite persistence layer for durable review memory and governance artifacts

This is already a strong internal-alpha / pilot-grade mapping product slice. It is not yet a production orchestration platform, a connector-heavy ingestion platform, or a full semantic operating model.

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
- `epics.md`: roadmap, phase plan, and backlog direction