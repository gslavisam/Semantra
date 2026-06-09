# Semantra Agent

> **Domain-Specific Agentic Framework** for [Semantra](https://github.com/gslavisam/Semantra) semantic integration.

This package bundles everything you need to use Semantra's mapping, knowledge, and bounded-LLM logic from **agents, notebooks, and Python scripts** — with or without the original Semantra web app running.

## What is in this folder

```
semantra_agent/
├── src/
│   ├── semantra_core/                # Pydantic models + Protocol contracts + reference impls
│   ├── semantra_backend_adapter/     # Adapter that exposes the Semantra FastAPI backend
│   └── semantra_agent/               # NEW: higher-level LangChain / LangGraph helpers
├── tests/                            # 145+ tests (unit + regression + e2e)
├── examples/                         # 5 runnable demos (3 notebooks + 2 scripts)
├── docs/                             # Technical guide, capability analysis, presentation
├── pyproject.toml
└── README.md (this file)
```

## Install

From this folder:

```bash
pip install -e .                          # core only
pip install -e ".[langgraph]"             # + LangGraph workflow helpers
pip install -e ".[langchain]"             # + LangChain tools wrapper
pip install -e ".[backend]"               # + FastAPI backend deps (for e2e tests)
pip install -e ".[all]"                   # everything
```

## Quick start

```python
from semantra_core.models.schema import DatasetHandle, SchemaProfile, ColumnProfile
from semantra_core.services import InMemoryMappingEngine, InMemoryKnowledgeBase, BoundedLLMService

# Use the in-memory stubs (no backend needed).
source = DatasetHandle(...)   # build a source dataset
target = SchemaProfile(...)   # build a target schema
engine = InMemoryMappingEngine()
candidates = engine.map_source_to_target(source, target)
```

Or plug the SDK into a real Semantra backend:

```python
from semantra_backend_adapter import create_backend_adapters
adapters = create_backend_adapters()
candidates = adapters["engine"].map_source_to_target(source, target)
```

If you want non-blocking backend mapping in an async agent flow, request the async engine and pass it to LangChain:

```python
from semantra_backend_adapter import create_backend_adapters
from semantra_agent.langchain_tools import build_semantra_tools

adapters = create_backend_adapters(include_async_engine=True)
tools = build_semantra_tools(
    async_engine=adapters["async_engine"],
    knowledge=kb,
    llm=llm,
)
```

Or build a LangGraph state machine:

```python
from semantra_core.langgraph_workflow import build_semantra_graph
graph = build_semantra_graph(engine=engine, llm=llm)
result = graph.invoke({"source": source, "target": target})
```

Or wrap the services as LangChain tools:

```python
from semantra_agent.langchain_tools import build_semantra_tools
tools = build_semantra_tools(engine=engine, knowledge=kb, llm=llm)
# `tools` is a list of langchain.tools.BaseTool ready for an agent.
```

## Examples

| File | What it shows |
|---|---|
| `examples/01_sdk_basics.ipynb` | Pydantic models, in-memory reference implementations |
| `examples/02_backend_adapter.ipynb` | Adapter that delegates to the Semantra FastAPI backend |
| `examples/03_langgraph_workflow.ipynb` | LangGraph state machine (`propose → validate → END`) |
| `examples/04_real_file_mapping_demo.py` | Real file-to-file mapping (CSV → CSV, InMemory vs Backend) |
| `examples/04b_supplier_rich_mapping_demo.py` | Rich MappingDecision table with 12 columns + per-field review |
| `examples/05_async_backend_demo.py` | Async backend LangChain tool demo using `async_engine` |

Run an example:

```bash
cd semantra_agent
../.venv/bin/python examples/04_real_file_mapping_demo.py
../.venv/bin/python examples/04b_supplier_rich_mapping_demo.py
```

## Tests

```bash
cd semantra_agent
.venv/bin/pytest tests/                       # all 145+ tests
.venv/bin/pytest tests/test_schema_models.py  # narrow slice
.venv/bin/pytest tests/test_e2e_rich_mapping.py -v  # full mapping payload
```

## Documentation

| Doc | What's in it |
|---|---|
| `docs/AGENTIC_FRAMEWORK_PRESENTATION.md` | High-level overview, how to use, demo walkthrough, add-on question |
| `docs/TECHNICAL_GUIDE.md` | Architecture, protocol contracts, extension points |
| `docs/CAPABILITY_ANALYSIS.md` | Web app vs. new framework — what's covered, what's not |
| `docs/README_semantra_core.md` | Original README for the core SDK (now part of this package) |
| `docs/README_semantra_backend_adapter.md` | Original README for the adapter |

## License

MIT
