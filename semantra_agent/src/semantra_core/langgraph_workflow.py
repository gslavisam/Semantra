"""Optional LangGraph integration for Semantra Core.

This module provides a ready-to-use state graph that demonstrates how to wire
the `MappingEngine`, `KnowledgeBase`, and `LLMService` protocols into an
agentic workflow. It is intentionally lightweight and can be extended or
replaced with a more sophisticated graph in production.

Requirements:
    pip install semantra-core[langgraph]
"""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict

try:
    from langgraph.graph import END, StateGraph
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "LangGraph is required for this workflow. "
        "Install it with: pip install semantra-core[langgraph]"
    ) from e

from .models.schema import DatasetHandle, SchemaProfile
from .models.mapping import CandidateOption
from .services.protocols import KnowledgeBase, LLMService, MappingEngine


class SemantraState(TypedDict, total=False):
    """State object that flows through the LangGraph nodes.

    All fields are optional because the graph is invoked with a partial state
    (only `source` and `target`) and gradually fills the rest.
    """

    source: NotRequired[DatasetHandle]
    target: NotRequired[SchemaProfile]
    candidates: NotRequired[list[CandidateOption]]
    selected_target: NotRequired[str]
    confidence: NotRequired[float]
    reasoning: NotRequired[list[str]]
    error: NotRequired[str]


def propose_candidates_node(state: SemantraState, engine: MappingEngine) -> SemantraState:
    """Node 1: ask the mapping engine for candidate targets."""
    try:
        source = state.get("source")
        target = state.get("target")
        if source is None or target is None:
            return {**state, "error": "source and target are required for propose_candidates"}
        candidates = engine.map_source_to_target(source, target)
        return {**state, "candidates": candidates}
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"propose_candidates failed: {exc}"}


def validate_with_llm_node(state: SemantraState, llm: LLMService) -> SemantraState:
    """Node 2: use the LLM to choose the best candidate from the closed set."""
    if state.get("error"):
        return state
    try:
        source = state.get("source")
        if source is None:
            return {**state, "error": "source is required for validate_with_llm"}
        candidates = state.get("candidates", [])
        first_col = source.schema_profile.columns[0].name
        candidate_targets = [c.target for c in candidates]
        result = llm.validate_mapping(first_col, candidate_targets, context={})
        return {
            **state,
            "selected_target": result.get("selected_target", ""),
            "confidence": float(result.get("confidence", 0.0)),
            "reasoning": list(result.get("reasoning", [])),
        }
    except Exception as exc:  # noqa: BLE001
        return {**state, "error": f"validate_with_llm failed: {exc}"}


def build_semantra_graph(
    engine: MappingEngine,
    llm: LLMService,
    knowledge: KnowledgeBase | None = None,
) -> Any:
    """Construct a compiled LangGraph state graph.

    The graph is intentionally simple: it goes from `propose` to `validate` to `END`.
    Callers can extend it with additional nodes (e.g. canonical lookup, code generation).
    """
    graph = StateGraph(SemantraState)

    def _propose(state: SemantraState) -> SemantraState:
        return propose_candidates_node(state, engine)

    def _validate(state: SemantraState) -> SemantraState:
        return validate_with_llm_node(state, llm)

    graph.add_node("propose", _propose)
    graph.add_node("validate", _validate)
    graph.set_entry_point("propose")
    graph.add_edge("propose", "validate")
    graph.add_edge("validate", END)

    return graph.compile()
