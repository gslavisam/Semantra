# Semantra

Semantra is the first implementation slice of an AI semantic bridge MVP.

Current scope:
- CSV, JSON, XML, XLSX row-data upload or SQL schema snapshot upload for source and target datasets
- Any-to-any row-based mapping across CSV, JSON, XML, and XLSX on source and target sides
- Schema profiling with pattern and statistical hints
- Multi-signal auto-mapping heuristics
- Top-k ranked mapping candidates per source field
- Optional constrained LLM validator for ambiguous cases
- Prompt-driven LLM transformation suggestion generation for selected source-to-target pairs
- Transformation-aware preview and Pandas code generation from accepted mapping decisions
- API observability for decision logs and benchmark metrics
- SQLite-backed decision logs and user corrections
- Streamlit trust-layer review UI with manual mapping edits and generated/custom transformations
- Automated any-to-any 4x4 row-format regression tests covering CSV, JSON, XML, and XLSX
- `.env`-driven provider and runtime configuration
- Correction-aware score boost from historical user feedback
- Evaluation harness for mapping benchmark cases
- Preview projection of mapped rows
- Pandas code generation for accepted mappings

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

## Quick Ops

The Streamlit alpha UI currently covers:
- upload source and target files
- inspect `.sql` snapshots and choose `source_table` / `target_table`
- run auto-mapping and review ranked candidates
- inspect the trust-layer view for source, target, confidence, and transformation mode
- prompt the active runtime LLM for a pandas transformation suggestion for the currently selected target field
- review and apply suggested or custom transformation code before preview/codegen
- manually adjust accepted / needs review / rejected mapping decisions per source column
- filter mapping review by source column, status, and confidence label
- export active mapping decisions as JSON and import them back into the current review state
- save changed mapping selections as user corrections through the protected observability API
- request preview rows and generated Pandas code
- save the current mapping context as a benchmark dataset and run saved benchmark datasets from the UI
- view runtime config, decision logs, saved corrections, and evaluation runs in an admin/debug tab
- inspect metadata-driven knowledge match explanations for the current mapping response in the admin/debug tab
- inspect saved benchmark datasets and benchmark run history in a dedicated benchmark tab
- reset the current flow state from the sidebar when starting a new run
- track the current step and last action result through the UI status banners
- detect at runtime whether backend admin actions actually require an admin token, instead of blocking those flows unconditionally

If you want protected admin flows enabled, set `SEMANTRA_ADMIN_API_TOKEN` in `backend/.env`, then restart the API or call `POST /observability/config/reload` with the same token in the `X-Admin-Token` header.

For LM Studio or another OpenAI-compatible local runtime, configure these in `backend/.env`:
- `SEMANTRA_LLM_PROVIDER=lmstudio`
- `SEMANTRA_LLM_MODEL=<model-identifier>`
- `SEMANTRA_LMSTUDIO_BASE_URL=http://<host>:1234/v1/responses`

The transformation helper in the Streamlit trust layer has been browser-validated against an OpenAI-compatible LM Studio `responses` endpoint and now fills the pandas code field directly from a natural-language instruction.

To run a saved benchmark from the terminal and immediately inspect recent regression history:

```bash
cd backend
python scripts/run_saved_benchmark.py --dataset-id 1 --with-llm
```

If you do not want to export env vars manually, use the PowerShell wrapper that auto-loads `backend/.env`:

```powershell
cd Semantra/backend
./scripts/run_saved_benchmark.ps1 -DatasetId 1 -WithLlm
```

Ako želiš prvo samo da proveriš da li je `.env` pravilno učitan i koju će komandu skripta da pozove:

```powershell
./scripts/run_saved_benchmark.ps1 -DatasetId 1 -DryRun
```

The script reads these env vars automatically:
- `SEMANTRA_API_BASE_URL`
- `SEMANTRA_ADMIN_API_TOKEN`

There is also an optional GitHub Actions workflow in `.github/workflows/semantra-regression-benchmark.yml` for scheduled or manual benchmark runs against a deployed API.

## Current API

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

`POST /mapping/auto` now returns both:
- `mappings`: selected one-to-one mapping decisions after global assignment
- `ranked_mappings`: top-k candidate lists per source field for review UIs

## Scoring Mechanism

At the moment, Semantra scores every source-target field pair with a weighted multi-signal heuristic and then ranks the candidates per source field.

The current signal mix is:
- name similarity: `0.20`
- semantic similarity after normalization/synonym expansion: `0.12`
- internal metadata knowledge and vendor context prior: `0.10`
- detected pattern similarity: `0.20`
- statistical similarity: `0.15`
- sample-value overlap: `0.10`
- optional embedding similarity: `0.12`
- correction feedback adjustment: `0.10`
- optional constrained LLM signal: `0.05`

Implementation details:
- the name signal blends fuzzy similarity on normalized column names and Jaccard overlap on tokenized names
- the semantic layer is enriched by the internal metadata dictionary and vendor-style aliases loaded from `metadata_dict/metadata_dict.csv`
- the knowledge signal uses curated business concepts plus cross-system context from `metadata_dict/metadata_dictionary.xlsx`, `metadata_dict/sap_tables_mostUsed.xlsx`, `metadata_dict/qad_tables_mostUsed.xlsx`, and `metadata_dict/WD_entities_mostUsed.xlsx`
- workbook context is used as a prior when a field matches curated SAP/QAD/Workday aliases and object metadata
- the statistical signal averages distance-based similarity across `unique_ratio`, `null_ratio`, and normalized `avg_length`
- sample overlap compares distinct sample values from source and target profiles
- embedding similarity is `0` unless an embedding provider is enabled
- correction feedback can boost a previously confirmed mapping and penalize a previously wrong suggestion

After scoring all pairs, Semantra:
- sorts candidates per source field
- returns the top `3` candidates by default
- applies a greedy global one-to-one assignment step so the same target is not reused across multiple selected mappings
- maps confidence labels from score thresholds: `>= 0.85` is high, `>= 0.65` is medium, otherwise low

The LLM validator is not part of the first-pass scoring path. It is only invoked when the best heuristic score falls strictly inside the ambiguity gate, which defaults to `0.40 < score < 0.75`. In that case the LLM can re-rank only the closed top-k candidate set or return `no_match`.

The weighted score is a ranking heuristic, not a calibrated probability. In the current implementation the configured weights sum to `1.04`, so downstream confidence labels should be read as review guidance, not as probabilistic guarantees.

## Notes

- Milestone B alpha now supports CSV, JSON, XML, and XLSX row data, plus `.sql` schema snapshots on both source and target sides.
- If a `.sql` snapshot contains multiple `CREATE TABLE` blocks, `POST /upload` now requires `source_table` and/or `target_table` form fields so the mapping flow knows which table schema to profile.
- If a multi-table `.sql` upload is missing table selection, the API returns a `400` with the available table names.
- Datasets are stored in memory for development.
- Schema-only uploads map normally, but preview rows stay empty because no source row data exists.
- Embeddings are optional, and constrained LLM validation is available only for ambiguity-band cases through an injected provider.
- Prompt-driven transformation generation is separate from ambiguity-band validation and is invoked explicitly through `POST /mapping/transformation/generate` from the Streamlit trust layer.
- Preview and Pandas code generation both consume `transformation_code` when the reviewed mapping decisions include it.
- Settings now support `SEMANTRA_*` environment variables and `backend/.env` loading without adding native dependencies.
- Sensitive observability and saved benchmark endpoints can be protected with `SEMANTRA_ADMIN_API_TOKEN`.
- Optional embedding scoring is available through the built-in `hash` provider by setting `settings.embedding_provider = "hash"`.
- Internal metadata knowledge is loaded from the local `metadata_dict` assets and now contributes both semantic enrichment and a dedicated `knowledge` signal during mapping.
- Decision logs and user corrections are persisted in SQLite via `app/services/persistence_service.py`.
- Saved benchmark datasets are persisted with versions, can be re-run through the evaluation API, and produce persisted evaluation run history.
- `llm_service.py` now includes provider adapters for OpenAI Responses API, OpenAI-compatible LM Studio endpoints, and Ollama behind the same validator/generation interface.
- Historical user corrections now both boost corrected targets and penalize previously wrong suggested targets for the same source field, with versioned correction history metadata.
- Runtime configuration can be inspected and reloaded from `backend/.env` through the observability API.