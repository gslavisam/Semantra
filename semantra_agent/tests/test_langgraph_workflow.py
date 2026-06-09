"""Smoke tests for the optional LangGraph workflow integration.

The LangGraph module used to carry a stray ``_ = knowledge`` statement at
module level that referenced a parameter of ``build_semantra_graph`` rather
than a module-scope name. The line was hidden behind a ``# type: ignore``
comment and was a latent ``NameError`` waiting to be triggered. This file
guards against regression by:

  1. importing the module (the cheapest possible smoke test),
  2. constructing a compiled graph, and
  3. invoking the graph with a minimal state to confirm the wiring works.

These tests are intentionally narrow — they do not exhaustively cover
LangGraph semantics, they just pin the import + construction path.
"""

from __future__ import annotations

import pytest

# The langgraph module raises ImportError at top level if langgraph is not
# installed. Skip the whole module in that case so the suite does not fail
# in environments where langgraph has not been added as an extra.
try:
    from semantra_core.langgraph_workflow import build_semantra_graph  # noqa: F401

    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _LANGGRAPH_AVAILABLE,
    reason="langgraph not installed (pip install -e 'semantra_agent[langgraph]')",
)

from semantra_core.models.schema import (  # noqa: E402
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)
from semantra_core.services.implementations import (  # noqa: E402
    BoundedLLMService,
    InMemoryMappingEngine,
)


def test_module_imports_without_nameerror() -> None:
    """The module must import cleanly. (Regression: stray NameError at module level.)"""
    # Re-import to confirm the import is fresh — this is the test that
    # would have failed before the audit fix (the `_ = knowledge` line
    # would raise NameError on first import).
    import importlib
    import semantra_core.langgraph_workflow

    importlib.reload(semantra_core.langgraph_workflow)
    assert hasattr(semantra_core.langgraph_workflow, "build_semantra_graph")


def test_build_semantra_graph_returns_compiled_graph() -> None:
    """``build_semantra_graph`` should return an object that has an ``invoke`` method."""
    engine = InMemoryMappingEngine()
    llm = BoundedLLMService()
    graph = build_semantra_graph(engine=engine, llm=llm)

    assert graph is not None
    assert hasattr(graph, "invoke"), "compiled LangGraph must expose .invoke"


def test_build_semantra_graph_invokes_propose_node() -> None:
    """Invoking with a source handle should populate ``candidates`` on the state."""
    engine = InMemoryMappingEngine()  # produces trivial name-match candidates
    llm = BoundedLLMService()
    graph = build_semantra_graph(engine=engine, llm=llm)

    source_schema = SchemaProfile(
        dataset_id="src",
        dataset_name="users",
        row_count=10,
        columns=[ColumnProfile(
            name="id", normalized_name="id", dtype="str",
            null_ratio=0.0, unique_ratio=1.0, non_null_count=10,
        )],
    )
    target_schema = SchemaProfile(
        dataset_id="tgt",
        dataset_name="users_tgt",
        row_count=20,
        columns=[ColumnProfile(
            name="user_id", normalized_name="user_id", dtype="str",
            null_ratio=0.0, unique_ratio=1.0, non_null_count=20,
        )],
    )
    source_handle = DatasetHandle(
        dataset_id="src",
        dataset_name="users",
        schema_profile=source_schema,
    )

    state = graph.invoke({"source": source_handle, "target": target_schema})

    # The propose node runs first; InMemory engine returns [], so the
    # downstream validate node has nothing to choose from but should still
    # have run without raising.
    assert "candidates" in state
    assert state["candidates"] == []


def test_build_semantra_graph_handles_missing_source_gracefully() -> None:
    """If the caller forgets to pass a source, the graph should set an error
    key in the state rather than raising."""
    engine = InMemoryMappingEngine()
    llm = BoundedLLMService()
    graph = build_semantra_graph(engine=engine, llm=llm)

    state = graph.invoke({})  # no source, no target

    assert "error" in state
    assert "source" in state["error"].lower() or "target" in state["error"].lower()


@pytest.mark.parametrize("knowledge", [None, "placeholder"])
def test_build_semantra_graph_accepts_knowledge_none_or_value(knowledge) -> None:
    """``knowledge`` is reserved for future graph extensions; the builder
    must accept it being either ``None`` or a real object without raising."""
    engine = InMemoryMappingEngine()
    llm = BoundedLLMService()
    # The parameter is currently unused (no KB-aware node), so passing either
    # value or None should succeed.
    graph = build_semantra_graph(engine=engine, llm=llm, knowledge=knowledge)
    assert graph is not None
