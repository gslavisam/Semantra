# Semantra: Capability Analysis — Web App vs. New Framework Approach

> **Purpose:** Document what the original Semantra web application offered, what the new Semantra Core SDK + Adapter + LangGraph approach offers, and where the gaps are.
> **Date:** 2026-06-06
> **Scope:** End-to-end comparison across the full product surface.

---

## 1. Original Web Application — Capability Inventory

The original Semantra is a **pilot-ready semantic integration workbench** with a FastAPI backend and a Streamlit UI. Its capabilities, as documented in the project README, fall into four top-level UI areas and one set of cross-cutting core capabilities.

### 1.1 Core Implemented Capabilities (deterministic + bounded AI)

| # | Capability | Notes |
|---|---|---|
| 1 | Multi-format ingestion (CSV, JSON, XML, XLSX, SQL snapshot, schema-spec) | Upload + parse. |
| 2 | Source-side and target-side companion metadata enrichment | Merged into dataset handles. |
| 3 | Source-to-target mapping and canonical-only source-to-concept mapping | Two mapping modes. |
| 4 | Explainable multi-signal ranking with optional closed-set LLM validation | Deterministic fallback. |
| 5 | Configurable canonical candidate pool shortlisting | Performance optimization. |
| 6 | Mapping Analysis Overview with optional narration/audio generation | Advisory output. |
| 7 | Review Queue Plan and Gap Queue Summary | Queue-level guidance. |
| 8 | Opportunistic LLM decision proposals for `needs_review` rows | With live LLM fill. |
| 9 | Proposal apply workflows (`Apply selected`, `Apply safe`) | With stale-state protection. |
| 10 | Local decision-origin audit trail | `manual_mapping` / `llm_proposal`. |
| 11 | Per-row and batch LLM mapping refinement | With accept/revert controls. |
| 12 | Transformation generation (Pandas, PySpark, dbt starter) | Advisory preview. |
| 13 | LLM-based artifact refinement with split-view compare | Accept/discard actions. |
| 14 | Governed mapping-set persistence with status, audit, diff | Approved-only reuse. |
| 15 | Correction persistence and reusable correction-rule promotion | Learning loop. |
| 16 | Canonical glossary import/export, knowledge overlays, stewardship | Canonical Console. |
| 17 | Integration catalog search/detail/reuse flows | Workspace reuse-fit assessment. |
| 18 | Benchmark datasets, evaluation runs, scoring-profile comparison | Correction impact. |
| 19 | Compact sidebar operations strip and unified status legend | UX consistency. |
| 20 | Dismissible onboarding hints per top-level area | Discoverability. |
| 21 | `Workspace Copilot` closure/readiness/output guidance | Main + sidebar mirrored. |
| 22 | Rerun-safe `Workspace Copilot` section handoffs | Queue pending navigation. |

### 1.2 Bounded AI Surfaces (LLM is used only here)

| # | Surface | Where |
|---|---|---|
| A | Closed-set mapping validation inside the ambiguity band | `mapping_service` |
| B | Mapping Analysis Overview, narration, audio generation | `mapping_analysis_service`, `mapping_audio_service` |
| C | Transformation code generation | `transformation_service`, `codegen_service` |
| D | Artifact refinement in `Workspace > Output` | `transformation_service` |
| E | Review queue planning in `Workspace > Review` | `review_plan_service` |
| F | `Workspace Copilot` guidance | `workspace_copilot_service` |
| G | Canonical-gap suggestion and queue summary | `canonical_gap_triage_service` |
| H | Benchmark explanation | `benchmark_explanation_service` |
| I | Catalog workspace reuse-fit explanation | `catalog_reuse_fit_service` |

### 1.3 Top-Level UI Areas

1. **Workspace** — upload → profile → map → review → decide → preview → codegen → refine.
2. **Governance** — Canonical Console, registry, overlays, stewardship, glossary promotion.
3. **Catalog** — searchable integration inventory, reuse views, workspace-fit assessment.
4. **Benchmarks** — dataset save/run, scoring comparison, correction impact, history.
5. **System** — runtime config, observability, reset/runtime checks.

### 1.4 Product Boundaries (what it is NOT)

- Not a production batch orchestration platform.
- Not a connector-heavy ingestion platform.
- Not a multi-step enterprise workflow engine.
- Not a DB-only canonical authoring platform without file-backed reseed.
- Not a durable multi-user job runtime.

---

## 2. New Framework Approach — Capability Inventory

The new approach is the **Semantra Agent SDK** (distributed as `semantra-agent`, source rooted at `semantra_agent/src/`) with three layers:

- **`semantra_core`** — pure Pydantic v2 models + `@runtime_checkable` Protocol contracts + in-memory reference implementations. No FastAPI/Streamlit/DB dependency.
- **`semantra_backend_adapter`** — concrete adapters that wrap the existing Semantra FastAPI backend (lazy import; gracefully falls back to the in-memory stub if the backend package is not importable).
- **`semantra_agent`** — higher-level wrappers: `build_semantra_tools()` (LangChain) and `build_semantra_graph()` (LangGraph), polymorphic over the protocols so the same code works against stubs, the backend, or a custom engine.

It targets a different audience: external agent developers, embedding Semantra into other orchestrators.

### 2.1 What We Have Built So Far

| # | Component | Status | File / Path |
|---|---|---|---|
| 1 | Pure Pydantic v2 models (schema, mapping, knowledge) | ✅ Done | `semantra_agent/src/semantra_core/models/` |
| 2 | Abstract service protocols (`MappingEngine`, `KnowledgeBase`, `LLMService`, `Connector`) | ✅ Done | `semantra_agent/src/semantra_core/services/protocols.py` |
| 3 | Reference stub implementations | ✅ Done | `semantra_agent/src/semantra_core/services/implementations.py` |
| 4 | Optional LangGraph state-machine integration | ✅ Done | `semantra_agent/src/semantra_core/langgraph_workflow.py` |
| 5 | Unified README | ✅ Done | `semantra_agent/README.md` |
| 6 | Detailed technical guide | ✅ Done | `semantra_agent/docs/TECHNICAL_GUIDE.md` |
| 7 | Editable install + dependency wiring into backend | ✅ Done | `Semantra/requirements.txt` (`-e ./semantra_agent`) |
| 8 | `BackendMappingEngine` adapter | ✅ Done | `semantra_agent/src/semantra_backend_adapter/mapping.py` |
| 9 | `BackendKnowledgeBase` adapter | ✅ Done | `semantra_agent/src/semantra_backend_adapter/knowledge.py` |
| 10 | `BackendLLMService` adapter | ✅ Done | `semantra_agent/src/semantra_backend_adapter/llm.py` |
| 11 | `BackendConnector` adapter | ✅ Done | `semantra_agent/src/semantra_backend_adapter/connector.py` |
| 12 | Factory + convenience exports | ✅ Done | `semantra_agent/src/semantra_backend_adapter/factory.py` |
| 13 | LangChain tool wrappers | ✅ Done | `semantra_agent/src/semantra_agent/langchain_tools.py` |
| 14 | E2E mapping tests (real showcase files, 3 formats) | ✅ Done | `semantra_agent/tests/test_e2e_mapping.py` (16 tests) |
| 15 | Rich-mapping E2E tests (full `MappingCandidate` payload) | ✅ Done | `semantra_agent/tests/test_e2e_rich_mapping.py` (5 tests) |
| 16 | Test suite | ✅ 145 passing | `semantra_agent/tests/` (8 modules) |

_Note: items 8–16 (the "Phase 3" deliverables) were originally tracked as planned in earlier drafts of this document; they are now implemented and shipped in the `semantra_agent` package. See the [presentation](AGENTIC_FRAMEWORK_PRESENTATION.md) for the current architecture._

---

## 3. Capability Mapping — Original → New

### 3.1 Fully Covered by the New Framework

| Original Capability | New Framework Equivalent |
|---|---|
| Source-to-target mapping (deterministic) | `MappingEngine.map_source_to_target` protocol + `BackendMappingEngine` adapter. |
| Canonical concept lookup & search | `KnowledgeBase.get_canonical_concept` / `search_concepts` + `BackendKnowledgeBase`. |
| Closed-set LLM validation | `LLMService.validate_mapping` + `BackendLLMService`. |
| Transformation code generation (Pandas/PySpark/dbt) | `LLMService.generate_transformation` (protocol exists; adapter will delegate). |
| Bounded LLM use (no autonomy) | Enforced by the protocol contracts themselves. |
| Reusable, framework-agnostic contracts | ✅ Built-in. |

### 3.2 Partially Covered (protocol exists, full backend logic not yet wired)

| Original Capability | New Framework Status |
|---|---|
| Multi-format ingestion (CSV, JSON, XML, XLSX, SQL, schema-spec) | Protocol `Connector` exists; `BackendConnector` reads from the upload store. Full format-specific connectors (one per format) are **out of scope** — they belong to a future `semantra-connectors` pack. |
| Mapping Analysis Overview + narration/audio | Protocol does **not** expose this; would need a new `AnalysisService` protocol. |
| Review Queue Plan | Protocol does **not** expose this. |
| Catalog search/reuse | Protocol does **not** expose this; would need a `CatalogService` protocol. |
| Benchmark runs | Protocol does **not** expose this. |
| Governance & stewardship workflows | The `KnowledgeBase` protocol is read-only by design; stewardship is a write-side concern. |

### 3.3 Not Covered (and intentionally not in the SDK)

| Original Capability | Why It Is Not in the SDK |
|---|---|
| Streamlit UI surfaces (`Workspace`, `Governance`, `Catalog`, `Benchmarks`, `System`) | The SDK is a library, not an app. The Streamlit UI remains the pilot product. |
| RBAC + `X-Admin-Token` + principal bootstrap | Application-level concern; lives in the FastAPI backend. |
| SQLite persistence and migration | Application-level concern. |
| Workspace Copilot guidance in the main panel | UI concern. |
| Onboarding hints, sidebar operations strip | UX concern. |
| Apply selected / Apply safe workflows | These are stateful UI workflows; they can be re-implemented on top of the SDK but are not the SDK's responsibility. |

### 3.4 New Capabilities the Framework Adds (that the original web app did not have)

| New Capability | Why It Matters |
|---|---|
| **Framework-agnostic consumption** | Any agent runtime (LangGraph, CrewAI, custom) can use Semantra's mapping/knowledge logic. |
| **Programmatic API** | No need to run the Streamlit UI to use the engine; can be called from a script, a notebook, or a microservice. |
| **Pluggable implementations** | Swap the `MappingEngine` (e.g. a remote service, a different algorithm) without changing the agent code. |
| **Structured state for agents** | `SemantraState` TypedDict gives agents a typed, inspectable working memory. |
| **Bounded-AI guarantees as a contract** | The protocols enforce closed-set validation and bounded LLM use at the type level. |
| **Domain-specific agentic framework** | Fills the gap between general-purpose LLM libs and business-domain integration needs. |

---

## 4. Coverage Summary

| Category | Original Web App | New Framework | Coverage |
|---|---|---|---|
| Data models | Backend-local Pydantic | Shared, reusable Pydantic in SDK | ✅ 100% |
| Mapping engine | Tightly coupled to FastAPI | Abstract protocol + backend adapter | ✅ 100% |
| Knowledge runtime | Tightly coupled to FastAPI + DB | Abstract protocol + backend adapter | ✅ 100% |
| LLM service | Tightly coupled | Abstract protocol + backend adapter | ✅ 100% |
| Connectors (per-format) | Inline in upload store | Single `BackendConnector`; per-format pack is future work | ⚠️ ~30% |
| UI surfaces | 5 top-level areas, many panels | None (library only) | ❌ 0% (intentional) |
| Governance workflows | Full | None (read-only protocol) | ❌ 0% (intentional) |
| Benchmarking | Full | None | ❌ 0% (intentional) |
| Persistence | SQLite | Backend-only | ❌ 0% (intentional) |
| RBAC / Auth | Pilot slice | None | ❌ 0% (intentional) |
| **Agentic orchestration** | **None** | **LangGraph state machine, extensible** | **✅ New** |

---

## 5. Gaps and Recommended Next Steps

### 5.1 Short-term (Phase 4 — Connectors Pack)
- Create a separate `semantra-connectors` package.
- Ship CSV, SQL, SAP, QAD, and generic HTTP adapters as Protocol implementations.

### 5.2 Medium-term (Phase 5 — Agent Templates)
- Add ready-to-use LangGraph / CrewAI templates for the Discovery → Mapping → Validation flow.
- Add an `AnalysisService` and `CatalogService` protocol if those surfaces are needed in agent workflows.

### 5.3 Long-term (Phase 6 — Production Hardening)
- Async versions of the protocols.
- Distributed tracing hooks.
- Versioned migration of the SDK.
- Refactor adapter's getattr-based reconstruction of backend models into a single, validated `model_to_core()` mapper.
- ~~Extend `InMemoryMappingEngine` with trivial name-match (case-insensitive, equality, substring) so the SDK demo works without the backend.~~ ✅ Done — see `InMemoryMappingEngine.map_source_to_target` (exact match conf=1.0, substring conf=0.7).
- ~~Add CI matrix that tests each extras group independently (`core only`, `[langchain]`, `[langgraph]`, `[backend]`) to catch import-time bugs like the one fixed in the recent audit.~~ ✅ Done — see `.github/workflows/test.yml` (7 matrix rows: 4 extras on py3.12 + 3 Python versions on `[all]`).

---

## 6. Conclusion

The **new Semantra Core SDK** is a **strategic complement**, not a replacement, for the original web application:

- **Web app remains the pilot product** for human analysts.
- **SDK + adapters make Semantra consumable by agents** — the new "domain-specific agentic framework" surface.
- **Coverage of the original capabilities is high at the engine/knowledge/LLM layer** (where it matters for automation), and intentionally zero at the UI/persistence layer (where the web app lives).

The two surfaces can coexist: a team can use the web app for governance and review, while agents (LangGraph, CrewAI, custom) use the SDK for high-volume, bounded automation.
