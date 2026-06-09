"""Unit tests for the LangChain tool wrappers in ``semantra_agent.langchain_tools``.

The wrappers expose the three semantra_core services (MappingEngine,
KnowledgeBase, LLMService) as LangChain ``BaseTool`` instances. The
factory ``build_semantra_tools`` must return only the tools for the
services that were provided, and each tool's ``_run`` method must
delegate to the underlying service.

These tests use the in-memory reference implementations — no LangChain
LLM, no Semantra backend required.
"""

from __future__ import annotations

import asyncio

import pytest

from semantra_core.models.knowledge import CanonicalGlossaryEntry
from semantra_core.models.mapping import (
    CandidateOption,
    MappingDecision,
    ScoringSignals,
)
from semantra_core.services.implementations import (
    BoundedLLMService,
    InMemoryKnowledgeBase,
    InMemoryMappingEngine,
    StaticConnector,
)

# Skip the entire module if langchain_core is not available — the tool
# classes can't be instantiated without it.
try:
    from langchain_core.tools import BaseTool  # noqa: F401

    _LANGCHAIN_AVAILABLE = True
except Exception:  # noqa: BLE001
    _LANGCHAIN_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _LANGCHAIN_AVAILABLE, reason="langchain_core not installed"
)

if _LANGCHAIN_AVAILABLE:
    from semantra_agent.langchain_tools import (
        GenerateTransformationTool,
        GetCanonicalConceptTool,
        MapSourceToTargetTool,
        SearchConceptsTool,
        ValidateMappingTool,
        build_semantra_tools,
    )


# ---------------------------------------------------------------------------
# build_semantra_tools factory
# ---------------------------------------------------------------------------


def test_factory_with_no_services_returns_empty_list() -> None:
    """No services → no tools. The factory must not synthesise a tool."""
    tools = build_semantra_tools()
    assert tools == []


def test_factory_with_engine_only_returns_one_tool() -> None:
    tools = build_semantra_tools(engine=InMemoryMappingEngine())
    assert len(tools) == 1
    assert isinstance(tools[0], MapSourceToTargetTool)


def test_factory_with_knowledge_only_returns_two_tools() -> None:
    tools = build_semantra_tools(knowledge=InMemoryKnowledgeBase())
    assert len(tools) == 2
    names = {t.name for t in tools}
    assert "semantra_get_canonical_concept" in names
    assert "semantra_search_concepts" in names


def test_factory_with_llm_only_returns_two_tools() -> None:
    tools = build_semantra_tools(llm=BoundedLLMService())
    assert len(tools) == 2
    names = {t.name for t in tools}
    assert "semantra_validate_mapping" in names
    assert "semantra_generate_transformation" in names


def test_factory_with_all_three_services_returns_five_tools() -> None:
    tools = build_semantra_tools(
        engine=InMemoryMappingEngine(),
        knowledge=InMemoryKnowledgeBase(),
        llm=BoundedLLMService(),
    )
    # 1 (engine) + 2 (knowledge) + 2 (llm) = 5
    assert len(tools) == 5
    assert all(isinstance(t, BaseTool) for t in tools)


def test_factory_accepts_connector_parameter_without_using_it() -> None:
    """The connector parameter is reserved for future tools. Passing it
    must not raise or alter the tool list."""
    from semantra_core.models.schema import SchemaProfile

    connector = StaticConnector(
        schema=SchemaProfile(
            dataset_id="c", dataset_name="c", row_count=0, columns=[]
        )
    )
    tools = build_semantra_tools(
        engine=InMemoryMappingEngine(),
        connector=connector,
    )
    # Only engine tools returned; connector doesn't add anything yet.
    assert len(tools) == 1


def test_factory_accepts_async_engine_parameter() -> None:
    class _StubAsyncEngine:
        async def map_source_to_target(self, source, target):  # noqa: ARG002
            return []

    tools = build_semantra_tools(async_engine=_StubAsyncEngine())
    assert len(tools) == 1
    assert isinstance(tools[0], MapSourceToTargetTool)


# ---------------------------------------------------------------------------
# MapSourceToTargetTool._run
# ---------------------------------------------------------------------------


def test_map_source_to_target_tool_returns_dicts_for_in_memory_engine(
    source_handle, target_schema
) -> None:
    """The in-memory engine returns candidates and the tool serialises them."""
    engine = InMemoryMappingEngine()
    tool = MapSourceToTargetTool(engine=engine)  # type: ignore[arg-type]

    result = tool._run(
        source=source_handle.model_dump(),
        target=target_schema.model_dump(),
    )

    assert isinstance(result, list)
    assert all(isinstance(item, dict) for item in result)


def test_map_source_to_target_tool_returns_candidate_dicts(source_handle, target_schema) -> None:
    """A custom engine that returns a candidate should be serialised as a list of dicts."""
    from semantra_core.models.mapping import CandidateOption

    class _StubEngine:
        def map_source_to_target(self, source, target):  # noqa: ARG002
            return [
                CandidateOption(
                    target="user_id",
                    confidence=0.92,
                    confidence_label="high_confidence",
                    method="stub",
                    explanation=["names match"],
                    signals=ScoringSignals(name=1.0),
                )
            ]

    tool = MapSourceToTargetTool(engine=_StubEngine())  # type: ignore[arg-type]
    result = tool._run(
        source=source_handle.model_dump(),
        target=target_schema.model_dump(),
    )

    assert len(result) == 1
    assert result[0]["target"] == "user_id"
    assert result[0]["confidence"] == pytest.approx(0.92)
    assert result[0]["confidence_label"] == "high_confidence"
    assert result[0]["method"] == "stub"


def test_map_source_to_target_tool_arun_uses_async_engine(
    source_handle, target_schema
) -> None:
    from semantra_core.models.mapping import CandidateOption

    class _StubAsyncEngine:
        async def map_source_to_target(self, source, target):  # noqa: ARG002
            return [
                CandidateOption(
                    target="user_id",
                    confidence=0.92,
                    confidence_label="high_confidence",
                    method="stub",
                    explanation=["names match"],
                    signals=ScoringSignals(name=1.0),
                )
            ]

    tool = MapSourceToTargetTool(engine=_StubAsyncEngine())  # type: ignore[arg-type]
    result = asyncio.run(
        tool._arun(
            source=source_handle.model_dump(),
            target=target_schema.model_dump(),
        )
    )

    assert len(result) == 1
    assert result[0]["target"] == "user_id"
    assert result[0]["confidence"] == pytest.approx(0.92)
    assert result[0]["confidence_label"] == "high_confidence"
    assert result[0]["method"] == "stub"


# ---------------------------------------------------------------------------
# GetCanonicalConceptTool._run
# ---------------------------------------------------------------------------


def test_get_canonical_concept_tool_returns_dict_for_known_id() -> None:
    kb = InMemoryKnowledgeBase()
    kb.add(
        CanonicalGlossaryEntry(
            concept_id="customer.email",
            entity="customer",
            attribute="email",
            display_name="Customer Email",
        )
    )
    tool = GetCanonicalConceptTool(knowledge=kb)  # type: ignore[arg-type]

    result = tool._run(concept_id="customer.email")
    assert result is not None
    assert result["concept_id"] == "customer.email"
    assert result["display_name"] == "Customer Email"


def test_get_canonical_concept_tool_returns_none_for_unknown_id() -> None:
    tool = GetCanonicalConceptTool(knowledge=InMemoryKnowledgeBase())  # type: ignore[arg-type]
    result = tool._run(concept_id="does.not.exist")
    assert result is None


# ---------------------------------------------------------------------------
# SearchConceptsTool._run
# ---------------------------------------------------------------------------


def test_search_concepts_tool_finds_matching_entries() -> None:
    kb = InMemoryKnowledgeBase()
    kb.add(
        CanonicalGlossaryEntry(
            concept_id="customer.email",
            entity="customer",
            attribute="email",
            display_name="Customer Email",
        )
    )
    kb.add(
        CanonicalGlossaryEntry(
            concept_id="supplier.email",
            entity="supplier",
            attribute="email",
            display_name="Supplier Email",
        )
    )
    tool = SearchConceptsTool(knowledge=kb)  # type: ignore[arg-type]

    result = tool._run(query="customer", limit=10)
    assert len(result) == 1
    assert result[0]["concept_id"] == "customer.email"


def test_search_concepts_tool_respects_limit() -> None:
    kb = InMemoryKnowledgeBase()
    for i in range(5):
        kb.add(
            CanonicalGlossaryEntry(
                concept_id=f"x.{i}",
                entity="x",
                attribute=str(i),
                display_name=f"Item {i}",
            )
        )
    tool = SearchConceptsTool(knowledge=kb)  # type: ignore[arg-type]
    result = tool._run(query="item", limit=2)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# ValidateMappingTool._run
# ---------------------------------------------------------------------------


def test_validate_mapping_tool_delegates_to_llm() -> None:
    captured: dict = {}

    class _StubLLM:
        def validate_mapping(self, source_field, candidate_targets, context):  # noqa: ARG002
            captured["source_field"] = source_field
            captured["candidate_targets"] = candidate_targets
            captured["context"] = context
            return {
                "selected_target": "user_id",
                "confidence": 0.8,
                "reasoning": ["first match"],
            }

    tool = ValidateMappingTool(llm=_StubLLM())  # type: ignore[arg-type]
    result = tool._run(
        source_field="id",
        candidate_targets=["user_id", "uuid"],
        context={"hint": "primary key"},
    )

    assert captured["source_field"] == "id"
    assert captured["candidate_targets"] == ["user_id", "uuid"]
    assert captured["context"] == {"hint": "primary key"}
    assert result["selected_target"] == "user_id"


# ---------------------------------------------------------------------------
# GenerateTransformationTool._run
# ---------------------------------------------------------------------------


def test_generate_transformation_tool_validates_decision_and_invokes_llm() -> None:
    captured: dict = {}

    class _StubLLM:
        def generate_transformation(self, mapping_decision, context):  # noqa: ARG002
            captured["decision"] = mapping_decision
            captured["context"] = context
            return "df['id'] = df['user_id']"

    tool = GenerateTransformationTool(llm=_StubLLM())  # type: ignore[arg-type]
    decision = MappingDecision(source="id", target="user_id")
    result = tool._run(mapping_decision=decision.model_dump(), context={})

    assert "decision" in captured
    assert captured["decision"].source == "id"
    assert captured["context"] == {}
    assert result == "df['id'] = df['user_id']"


def test_generate_transformation_tool_uses_empty_context_when_omitted() -> None:
    captured: dict = {}

    class _StubLLM:
        def generate_transformation(self, mapping_decision, context):  # noqa: ARG002
            captured["context"] = context
            return ""

    tool = GenerateTransformationTool(llm=_StubLLM())  # type: ignore[arg-type]
    decision = MappingDecision(source="a", target="b")
    tool._run(mapping_decision=decision.model_dump())  # no context kwarg

    assert captured["context"] == {}
