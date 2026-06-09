 # AGENTS

## Scope

These instructions apply to the Semantra project in this folder.

Semantra is a pilot-ready semantic integration workbench with a FastAPI backend, a Streamlit UI, and a SQLite persistence layer. It is deterministic-first and uses bounded AI only in inspectable, workflow-local surfaces.

## Start Here

Read project docs in this order before changing behavior that is not obviously local:

1. [project_docs/current_state.md](project_docs/current_state.md) for the authoritative product surface and current constraints.
2. [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) for architecture and bounded-AI operating model.
3. [project_docs/completed_slices.md](project_docs/completed_slices.md) for recent delivered waves.
4. [project_docs/plan.md](project_docs/plan.md) for forward-looking priorities.
5. [project_docs/epics.md](project_docs/epics.md) for backlog status.
6. [project_docs/implementation_checklists.md](project_docs/implementation_checklists.md) for currently active execution checklists.

Prefer links over copying documentation into new markdown files. Do not create new status/snapshot markdown docs when the change belongs in the existing docs above.

## Key Code Surfaces

- Backend entrypoint: [backend/app/main.py](backend/app/main.py)
- API routes: [backend/app/api/routes](backend/app/api/routes)
- Core mapping engine: [backend/app/services/mapping_service.py](backend/app/services/mapping_service.py)
- Mapping jobs: [backend/app/services/mapping_job_service.py](backend/app/services/mapping_job_service.py)
- Persistence layer: [backend/app/services/persistence_service.py](backend/app/services/persistence_service.py)
- Canonical and knowledge runtime: [backend/app/services/metadata_knowledge_service.py](backend/app/services/metadata_knowledge_service.py)
- Streamlit shell: [streamlit_app.py](streamlit_app.py)
- Main Streamlit surfaces: [streamlit_ui/workspace_views.py](streamlit_ui/workspace_views.py), [streamlit_ui/workspace_review_views.py](streamlit_ui/workspace_review_views.py), [streamlit_ui/admin_views.py](streamlit_ui/admin_views.py), [streamlit_ui/catalog_views.py](streamlit_ui/catalog_views.py)

## Working Conventions

- Preserve the deterministic-first product model. Do not turn LLM-assisted surfaces into autonomous or hidden-decision paths.
- Keep governance enforcement in backend contracts, not only in Streamlit UI checks.
- Treat preview and explanation surfaces as advisory unless the existing contract explicitly makes them durable.
- For canonical changes, prefer the overlay-first workflow and explicit promotion path instead of bypassing stewardship.
- When docs conflict, prefer [project_docs/current_state.md](project_docs/current_state.md) for what exists today and [project_docs/plan.md](project_docs/plan.md) only for future direction.
- Follow the existing documentation discipline in [project_docs/README.md](project_docs/README.md): update current state, completed slices, and plan in place instead of adding duplicate project-management docs.

## Local Runtime Notes

- Install dependencies from the repo root with `pip install -r requirements.txt`.
- The Windows launcher is [start_semantra.ps1](start_semantra.ps1).
- The launcher expects the Python executable at `../.venv/Scripts/python.exe` relative to the Semantra folder. If startup fails, check that shared workspace virtualenv first.
- Manual backend start uses Uvicorn with `--app-dir backend`; manual UI start uses Streamlit on [streamlit_app.py](streamlit_app.py).
- SQLite database is `backend/semantra.sqlite3`.

## Validation

- Prefer narrow tests over broad suites.
- Backend tests live in [backend/tests](backend/tests); Streamlit/UI helper tests live in [tests](tests).
- Typical targeted commands from the Semantra root:
  - `d:/py_radno/.venv/Scripts/python.exe -m pytest backend/tests/test_api_smoke.py -k "<slice>"`
  - `d:/py_radno/.venv/Scripts/python.exe -m pytest backend/tests/test_mapping_service.py -k "<slice>"`
  - `d:/py_radno/.venv/Scripts/python.exe -m pytest tests/test_streamlit_admin_views.py -k "<slice>"`
- If you edit Streamlit helpers, prefer the smallest relevant `tests/test_streamlit_*.py` target.
- If you edit governance, persistence, or runtime behavior, add or run a backend test that proves the contract instead of relying on UI checks.

## Known Boundaries And Risks

- [backend/app/services/persistence_service.py](backend/app/services/persistence_service.py), [backend/app/services/metadata_knowledge_service.py](backend/app/services/metadata_knowledge_service.py), and [backend/app/services/mapping_service.py](backend/app/services/mapping_service.py) are large, high-blast-radius files. Make narrow edits and validate immediately.
- [streamlit_ui/admin_views.py](streamlit_ui/admin_views.py), [streamlit_ui/workspace_review_views.py](streamlit_ui/workspace_review_views.py), and [streamlit_ui/catalog_views.py](streamlit_ui/catalog_views.py) are large UI surfaces; avoid opportunistic refactors while fixing local behavior.
- Mapping jobs are currently in-memory/thread based. Do not assume restart-safe or cross-process-safe background execution.
- The canonical/knowledge runtime is DB-first but still supports file-based reseed inputs. Do not accidentally reintroduce full reseed behavior into local canonical authoring changes.

## Useful References

- [docs/reference/MAPPING_SIGNALS_AND_SCORING.md](docs/reference/MAPPING_SIGNALS_AND_SCORING.md)
- [docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md](docs/reference/TRANSFORMATION_PREVIEW_AND_CODEGEN_WARNINGS.md)
- [docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md](docs/reference/TRANSFORMATION_TEST_SETS_AND_ASSERTIONS.md)
- [docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md](docs/reference/CANONICAL_CONSOLE_AND_STEWARDSHIP.md)
- [docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md](docs/reference/CATALOG_SEARCH_REUSE_AND_SIMILARITY.md)
- [docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md](docs/reference/BENCHMARK_METRICS_AND_CORRECTION_IMPACT.md)
- [docs/pilot/PILOT_REGRESSION_SUBSET.md](docs/pilot/PILOT_REGRESSION_SUBSET.md)