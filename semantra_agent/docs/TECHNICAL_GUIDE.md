# Semantra Core SDK — Technical Guide

> **Audience:** Engineers extending or integrating the Semantra core SDK.
> **Scope:** Detailed architecture, contract definitions, extension points,
> and usage examples. For a high-level overview see [`README.md`](../README.md).

---

## 1. Goals & Design Principles

The Semantra Core SDK was extracted from the main Semantra backend
(`backend/app/`) to achieve three goals:

1. **Reusability** — let external agent frameworks (LangGraph, CrewAI,
   custom orchestrators) consume Semantra without depending on FastAPI,
   Streamlit, or SQLite.
2. **Determinism** — the data models are pure Pydantic v2; no hidden state,
   no I/O, no network calls. All side effects are behind explicit service
   protocols.
3. **Pluggability** — implementations of the service contracts can be
   swapped at runtime (e.g. an in-memory mapping engine for tests, a
   backend-backed one for production).

The SDK follows a **"domain-specific agentic framework"** philosophy:
general-purpose LLM libraries (LangChain, CrewAI) treat all domains
equally. Semantra is opinionated about *semantic integration of
structured business data* and exposes contracts that reflect that
opinion (canonical concepts, bounded validation, audit-friendly
decisions).

---

## 2. Package Layout

```
semantra_core/
├── __init__.py                # Re-exports models + services
├── models/
│   ├── __init__.py
│   ├── schema.py              # DatasetHandle, SchemaProfile, ColumnProfile
│   ├── mapping.py             # CandidateOption, ScoringSignals, MappingDecision, ...
│   └── knowledge.py           # CanonicalGlossaryEntry, KnowledgeOverlayEntry, ...
└── services/
    ├── __init__.py            # Re-exports protocols + implementations
    ├── protocols.py           # MappingEngine, KnowledgeBase, LLMService, Connector
    └── implementations.py     # In-memory / stub reference implementations
```

The `langgraph_workflow.py` module at the package root is optional
(see [§ 6. LangGraph Integration](#6-langgraph-integration)).

---

## 3. Data Models

All models inherit from `pydantic.BaseModel` and use `Field(default_factory=...)`
for mutable defaults. They are fully serialisable to JSON and round-trip
safely.

### 3.1 `semantra_core.models.schema`

| Model | Purpose |
|---|---|
| `ColumnProfile` | Profile of one dataset column (dtype, null ratio, sample values, detected patterns). |
| `SchemaProfile` | Profile of an entire dataset (id, name, row count, list of `ColumnProfile`). |
| `DatasetHandle` | A `SchemaProfile` plus a small batch of preview rows. |
| `PersistedDatasetRecord` | Durable payload stored by the upload runtime facade. |
| `SpecLayoutHint`, `SpecRecoverySuggestion`, `SpecRecoveryResponse` | Helpers for schema-spec ingestion flows. |
| `UploadResponse`, `MetadataEnrichmentResponse`, `SqlTableDiscoveryResponse` | API response envelopes. |

### 3.2 `semantra_core.models.mapping`

| Model | Purpose |
|---|---|
| `ScoringSignals` | Per-signal score breakdown (name, semantic, knowledge, canonical, pattern, statistical, overlap, embedding, correction, llm). |
| `CandidateOption` | One candidate target option for a source field (target, confidence, signals, canonical details, explanation). |
| `LLMValidationResult` | Output of a bounded closed-set LLM validator. |
| `LLMDecisionProposition` | Explanation of how an LLM recommendation related to the final decision. |
| `MappingDecision`, `MappingSetRecord`, `MappingCandidate` | Governance-facing decision types. |
| `TransformationSpec`, `TransformationPreviewResult`, `GeneratedArtifact` | Transformation code-gen payloads. |
| `EvaluationMetrics`, `CorrectionImpactMetrics` | Benchmark and correction-impact payloads. |

### 3.3 `semantra_core.models.knowledge`

| Model | Purpose |
|---|---|
| `CanonicalGlossaryEntry` | One canonical concept with aliases and privacy metadata. |
| `KnowledgeOverlayVersion`, `KnowledgeOverlayEntry` | Aliases / synonyms / field-alias overlays. |
| `KnowledgeOverlayValidationResult` | Summary of overlay upload validation. |
| `KnowledgeRuntimeStatus` | Snapshot of the active knowledge base state. |
| `KnowledgeConceptUpdateRequest` / `PromotionRequest` | Stewardship payloads. |

> **Note:** Models are intentionally decoupled from any persistence
> concern. They are safe to import in any environment that has Pydantic
> v2 installed.

---

## 4. Service Protocols

Defined in `semantra_core.services.protocols`. Each protocol is decorated
with `@runtime_checkable` so that `isinstance(obj, ProtocolType)` works
at runtime.

### 4.1 `MappingEngine`

```python
class MappingEngine(Protocol):
    def map_source_to_target(
        self, source: DatasetHandle, target: SchemaProfile
    ) -> list[CandidateOption]: ...
    def get_scoring_signals(self) -> ScoringSignals: ...
```

**Contract:** given a `DatasetHandle` and a `SchemaProfile`, return a
list of candidate target options ranked by confidence. The
implementation is free to use any combination of signals (name
similarity, embeddings, canonical concepts, etc.).

### 4.2 `KnowledgeBase`

```python
class KnowledgeBase(Protocol):
    def get_canonical_concept(self, concept_id: str) -> CanonicalGlossaryEntry | None: ...
    def search_concepts(self, query: str, limit: int = 10) -> list[CanonicalGlossaryEntry]: ...
    def get_active_overlay_entries(self) -> list[KnowledgeOverlayEntry]: ...
```

**Contract:** provide read-only access to canonical concepts and the
currently active knowledge overlay. Implementations may add write
methods (e.g. `add_concept`) but they are not part of the protocol.

### 4.3 `LLMService`

```python
class LLMService(Protocol):
    def validate_mapping(self, source_field: str, candidate_targets: list[str], context: dict) -> dict: ...
    def generate_transformation(self, mapping_decision: MappingDecision, context: dict) -> str: ...
```

**Contract:** the LLM is used **only** in two bounded scenarios:
1. Closed-set validation (pick one of the given candidates).
2. Starter code generation for an already-accepted mapping.

Implementations must never call the LLM with open-ended prompts; they
must respect the `candidate_targets` list as a hard constraint.

### 4.4 `Connector`

```python
class Connector(Protocol):
    def fetch_schema(self) -> SchemaProfile: ...
    def fetch_preview(self, limit: int = 100) -> DatasetHandle: ...
```

**Contract:** the minimal interface for any data source. Concrete
connectors (`CsvConnector`, `SapConnector`, `QadConnector`,
`GenericSqlConnector`) should implement this protocol and live in a
separate package (e.g. `semantra-connectors`).

---

## 5. Reference Implementations

Located in `semantra_core.services.implementations`. They are minimal,
side-effect-free, and safe to use as test doubles.

| Class | Role | Notes |
|---|---|---|
| `InMemoryMappingEngine` | Returns `[]` candidates. | Deterministic, no I/O. |
| `InMemoryKnowledgeBase` | Holds concepts in a `dict`. | Add via `.add(concept)`. |
| `BoundedLLMService` | Echoes the first candidate; returns an empty transformation. | Logs a "stub used" warning. |
| `StaticConnector` | Returns a pre-built `SchemaProfile`. | Useful for examples. |

These classes structurally satisfy the protocols — no explicit
inheritance is required.

---

## 6. LangGraph Integration

Optional module: `semantra_core.langgraph_workflow`.

### 6.1 Installation

```bash
pip install -e "./semantra-core[langgraph]"
```

### 6.2 State

```python
class SemantraState(TypedDict, total=False):
    source: NotRequired[DatasetHandle]
    target: NotRequired[SchemaProfile]
    candidates: NotRequired[list[CandidateOption]]
    selected_target: NotRequired[str]
    confidence: NotRequired[float]
    reasoning: NotRequired[list[str]]
    error: NotRequired[str]
```

All keys are `NotRequired` because the graph is invoked with a partial
state (`source` + `target`) and gradually fills the rest.

### 6.3 Nodes

- **`propose_candidates_node`** — calls `engine.map_source_to_target`.
- **`validate_with_llm_node`** — calls `llm.validate_mapping` on the
  first source column and the produced candidate targets.

### 6.4 Graph Assembly

```python
from semantra_core.langgraph_workflow import build_semantra_graph
graph = build_semantra_graph(engine=engine, llm=llm)
result = graph.invoke({"source": source, "target": target})
```

### 6.5 Extending the Graph

The default graph has two nodes. To add a canonical-lookup step before
LLM validation:

```python
def canonical_lookup_node(state, knowledge: KnowledgeBase):
    if state.get("error"): return state
    first_col = state["source"].schema_profile.columns[0].name
    concepts = knowledge.search_concepts(first_col, limit=3)
    return {**state, "canonical_candidates": [c.concept_id for c in concepts]}

graph.add_node("canonical_lookup", canonical_lookup_node)
graph.add_edge("propose", "canonical_lookup")
graph.add_edge("canonical_lookup", "validate")
```

---

## 7. Extending the SDK

### 7.1 Adding a New Model

1. Add the class to the appropriate `models/<module>.py` file.
2. Keep the class dependency-free (no I/O, no async unless absolutely
   necessary).
3. Re-export it from `semantra_core.models.__init__`.

### 7.2 Adding a New Protocol

1. Define the protocol in `services/protocols.py` with
   `@runtime_checkable`.
2. Add a stub implementation in `services/implementations.py`.
3. Export both from `services/__init__.py` and the package root.

### 7.3 Implementing a Real Adapter

To plug the real backend into the SDK, create an adapter class that
imports the existing service (e.g. `backend.app.services.mapping_service`)
and forwards calls. In the current `semantra_agent` package the adapter
lives at `src/semantra_backend_adapter/mapping.py`; it does a **lazy
import** of the backend inside `__init__` so the SDK is still usable
when the backend package is not on `PYTHONPATH` (it then falls back to
the in-memory stub).

```python
# semantra_agent/src/semantra_backend_adapter/mapping.py
from semantra_core.services.protocols import MappingEngine
from semantra_core.models.schema import DatasetHandle, SchemaProfile
from semantra_core.models.mapping import CandidateOption

class BackendMappingEngine:
    def map_source_to_target(self, source, target):
        # delegate to the existing backend logic
        ...
    def get_scoring_signals(self):
        ...
```

---

## 8. Testing

- **Unit tests** for the SDK live in `semantra_agent/tests/`. The
  `conftest.py` exposes shared `ColumnProfile`, `SchemaProfile`, and
  `DatasetHandle` fixtures; e2e tests for real CSV/JSON/XLSX inputs
  live in `test_e2e_mapping.py` and `test_e2e_rich_mapping.py`.
- Use the reference implementations as fixtures; they are deterministic
  and require no external services.
- For protocol conformance, write a small test that calls
  `isinstance(impl, ProtocolType)` after instantiating the
  implementation.

Example:

```python
from semantra_core.services import (
    InMemoryMappingEngine, InMemoryKnowledgeBase,
    BoundedLLMService, StaticConnector,
    MappingEngine, KnowledgeBase, LLMService, Connector,
)

def test_protocols():
    assert isinstance(InMemoryMappingEngine(), MappingEngine)
    assert isinstance(InMemoryKnowledgeBase(), KnowledgeBase)
    assert isinstance(BoundedLLMService(), LLMService)
    assert isinstance(StaticConnector(...), Connector)
```

---

## 9. Versioning

The SDK follows **semantic versioning**:

- **0.x.y** — pre-1.0, minor versions may contain breaking changes;
  the public API is defined by:
  - the contents of `semantra_core.models`
  - the protocols in `semantra_core.services.protocols`
- **1.0.0** — once the contracts are considered stable.

Current version: **0.2.0** (see `pyproject.toml`).

---

## 10. Roadmap

- **Phase 3 — Backend adapter:** ✅ Done. The adapter lives at
  `semantra_agent/src/semantra_backend_adapter/` and ships four
  adapter classes (`BackendMappingEngine`, `BackendKnowledgeBase`,
  `BackendLLMService`, `BackendConnector`) plus a `factory.py` that
  wires them all up.
- **Phase 4 — Connector pack:** ship a separate `semantra-connectors`
  package with CSV, SQL, SAP, and QAD adapters.
- **Phase 5 — Agent templates:** add ready-to-use LangGraph /
  CrewAI templates for the Discovery → Mapping → Validation flow
  described in the Semantra vision.

---

## 11. References

- Main project: <https://github.com/gslavisam/Semantra>
- LangGraph: <https://langchain-ai.github.io/langgraph/>
- Pydantic v2: <https://docs.pydantic.dev/2.0/>
- CrewAI: <https://docs.crewai.com/>
