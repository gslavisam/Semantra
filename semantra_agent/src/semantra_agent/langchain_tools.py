"""LangChain tools that wrap the semantra_core service protocols.

This module exposes the SDK's three core services — ``MappingEngine``,
``KnowledgeBase``, ``LLMService`` — as LangChain ``BaseTool`` instances
so they can be plugged into a LangChain agent (or any LangChain-style
tool-calling loop).

Why this matters
----------------
The semantra_core services are designed as runtime-checkable protocols,
so the same code works against:

  * the in-memory reference implementations (offline, no backend),
  * the Semantra FastAPI backend via ``semantra-backend-adapter``,
  * a custom remote engine the user has written.

The LangChain tools in this module honour that polymorphism: pass any
object that satisfies the protocol, get a working tool.

Install
-------
The LangChain integration is an **optional** extra:

    pip install -e "semantra_agent[langchain]"

Usage
-----

    from semantra_core.services import InMemoryMappingEngine, BoundedLLMService
    from semantra_core.services.implementations import InMemoryKnowledgeBase
    from semantra_agent.langchain_tools import build_semantra_tools

    engine    = InMemoryMappingEngine()
    knowledge = InMemoryKnowledgeBase()
    llm       = BoundedLLMService()

    tools = build_semantra_tools(engine=engine, knowledge=knowledge, llm=llm)
    # `tools` is a list[BaseTool]; pass to a LangChain agent, or call .invoke(...).

The tool inputs are small Pydantic-style dicts so they are JSON-friendly
and easy to serialize for an LLM prompt.
"""

from __future__ import annotations

from typing import Any, Optional, Type

try:
    from langchain_core.tools import BaseTool
    from pydantic import BaseModel as _BaseModel
    from pydantic import Field as _Field
    _LANGCHAIN_AVAILABLE = True
except ImportError as e:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False
    _IMPORT_ERROR = e

    # Provide a minimal stand-in so this module can be imported even
    # without langchain_core (it will raise on tool construction).
    class BaseTool:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "LangChain is not installed. "
                "Run: pip install -e 'semantra_agent[langchain]'"
            ) from _IMPORT_ERROR

    class _BaseModel:  # type: ignore[no-redef]
        pass

    def _Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        return None


from semantra_core.models.knowledge import CanonicalGlossaryEntry
from semantra_core.models.mapping import (
    CandidateOption,
    MappingDecision,
    ScoringSignals,
)
from semantra_core.services.protocols import AsyncLLMService, AsyncMappingEngine
from semantra_core.models.schema import DatasetHandle, SchemaProfile
from semantra_core.services.protocols import (
    Connector,
    KnowledgeBase,
    LLMService,
    MappingEngine,
)


# ---------------------------------------------------------------------------
# Tool input schemas (LangChain needs Pydantic input schemas for typed tools)
# ---------------------------------------------------------------------------


if _LANGCHAIN_AVAILABLE:

    class _MapSourceToTargetInput(_BaseModel):
        """Input for the ``map_source_to_target`` tool."""

        source: dict[str, Any] = _Field(
            description=(
                "Source DatasetHandle serialised as a dict. Must include "
                "'dataset_id', 'dataset_name', and 'schema_profile'."
            )
        )
        target: dict[str, Any] = _Field(
            description=(
                "Target SchemaProfile serialised as a dict. Must include "
                "'dataset_id', 'dataset_name', and 'row_count'."
            )
        )

    class _GetCanonicalConceptInput(_BaseModel):
        """Input for the ``get_canonical_concept`` tool."""

        concept_id: str = _Field(
            description="The stable canonical concept identifier to look up."
        )

    class _SearchConceptsInput(_BaseModel):
        """Input for the ``search_concepts`` tool."""

        query: str = _Field(description="Free-text search query.")
        limit: int = _Field(
            default=10,
            description="Maximum number of results to return (default 10).",
        )

    class _ValidateMappingInput(_BaseModel):
        """Input for the ``validate_mapping`` tool (closed-set LLM)."""

        source_field: str = _Field(
            description="The source field name being mapped."
        )
        candidate_targets: list[str] = _Field(
            description="The closed candidate set to choose from."
        )
        context: dict[str, Any] = _Field(
            default_factory=dict,
            description="Optional context dict (e.g. {'description': 'primary key'}).",
        )

    class _GenerateTransformationInput(_BaseModel):
        """Input for the ``generate_transformation`` tool (advisory)."""

        mapping_decision: dict[str, Any] = _Field(
            description=(
                "MappingDecision serialised as a dict. Must include "
                "'source', 'target', and (optionally) 'resolution_type'."
            )
        )
        context: dict[str, Any] = _Field(
            default_factory=dict,
            description="Optional context for the generator.",
        )

    class _FetchSchemaInput(_BaseModel):
        """Input for the ``fetch_schema`` tool (no arguments)."""

    class _FetchPreviewInput(_BaseModel):
        """Input for the ``fetch_preview`` tool."""

        limit: int = _Field(
            default=100,
            description="Maximum number of preview rows to fetch (default 100).",
        )


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------


def _candidate_to_dict(c: CandidateOption) -> dict[str, Any]:
    return {
        "target": c.target,
        "confidence": c.confidence,
        "confidence_label": c.confidence_label,
        "method": c.method,
        "explanation": list(c.explanation or []),
        "canonical_concepts": [
            {"concept_id": cd.concept_id, "display_name": cd.display_name}
            for cd in (c.canonical_details.source_concepts or [])
        ],
    }


def _concept_to_dict(c: CanonicalGlossaryEntry) -> dict[str, Any]:
    return {
        "concept_id": c.concept_id,
        "entity": c.entity,
        "attribute": c.attribute,
        "display_name": c.display_name,
        "description": c.description,
        "data_type": c.data_type,
        "aliases": list(c.aliases or []),
    }


class MapSourceToTargetTool(BaseTool):  # type: ignore[misc, valid-type]
    """LangChain tool that calls ``MappingEngine.map_source_to_target``."""

    name: str = "semantra_map_source_to_target"
    description: str = (
        "Score and rank candidate target fields for a given source dataset. "
        "Use this when you need to know 'which target field best matches "
        "this source field?'. Input is two serialised schema dicts."
    )
    args_schema: Type[_BaseModel] = _MapSourceToTargetInput  # type: ignore[assignment]

    engine: Any = None  # MappingEngine instance, set at construction.

    def _run(  # type: ignore[override]
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        **_: Any,
    ) -> list[dict[str, Any]]:
        source_handle = DatasetHandle.model_validate(source)
        target_profile = SchemaProfile.model_validate(target)
        candidates = self.engine.map_source_to_target(source_handle, target_profile)
        return [_candidate_to_dict(c) for c in candidates]

    async def _arun(
        self,
        source: dict[str, Any],
        target: dict[str, Any],
        **_: Any,
    ) -> Any:  # type: ignore[override]
        if isinstance(self.engine, AsyncMappingEngine):
            source_handle = DatasetHandle.model_validate(source)
            target_profile = SchemaProfile.model_validate(target)
            candidates = await self.engine.map_source_to_target(source_handle, target_profile)
            return [_candidate_to_dict(c) for c in candidates]
        return self._run(source=source, target=target)


class GetCanonicalConceptTool(BaseTool):  # type: ignore[misc, valid-type]
    """LangChain tool that calls ``KnowledgeBase.get_canonical_concept``."""

    name: str = "semantra_get_canonical_concept"
    description: str = (
        "Look up a canonical concept by its stable identifier. "
        "Use this when you need the definition / aliases of a known concept."
    )
    args_schema: Type[_BaseModel] = _GetCanonicalConceptInput  # type: ignore[assignment]

    knowledge: Any = None  # KnowledgeBase instance.

    def _run(  # type: ignore[override]
        self, concept_id: str, **_: Any
    ) -> Optional[dict[str, Any]]:
        entry = self.knowledge.get_canonical_concept(concept_id)
        return _concept_to_dict(entry) if entry is not None else None

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        return self._run(*args, **kwargs)


class SearchConceptsTool(BaseTool):  # type: ignore[misc, valid-type]
    """LangChain tool that calls ``KnowledgeBase.search_concepts``."""

    name: str = "semantra_search_concepts"
    description: str = (
        "Search the canonical glossary by free-text query. "
        "Use this when you don't know the concept id but have a keyword."
    )
    args_schema: Type[_BaseModel] = _SearchConceptsInput  # type: ignore[assignment]

    knowledge: Any = None

    def _run(  # type: ignore[override]
        self, query: str, limit: int = 10, **_: Any
    ) -> list[dict[str, Any]]:
        results = self.knowledge.search_concepts(query, limit=limit)
        return [_concept_to_dict(c) for c in results]

    async def _arun(self, *args: Any, **kwargs: Any) -> Any:  # type: ignore[override]
        return self._run(*args, **kwargs)


class ValidateMappingTool(BaseTool):  # type: ignore[misc, valid-type]
    """LangChain tool that calls ``LLMService.validate_mapping`` (closed-set)."""

    name: str = "semantra_validate_mapping"
    description: str = (
        "Ask the bounded LLM to pick the best target from a closed "
        "candidate set. The LLM cannot invent new targets — it can "
        "only pick one of the provided candidates or refuse."
    )
    args_schema: Type[_BaseModel] = _ValidateMappingInput  # type: ignore[assignment]

    llm: Any = None

    def _run(  # type: ignore[override]
        self,
        source_field: str,
        candidate_targets: list[str],
        context: Optional[dict[str, Any]] = None,
        **_: Any,
    ) -> dict[str, Any]:
        return self.llm.validate_mapping(
            source_field=source_field,
            candidate_targets=candidate_targets,
            context=context or {},
        )

    async def _arun(  # type: ignore[override]
        self,
        source_field: str,
        candidate_targets: list[str],
        context: Optional[dict[str, Any]] = None,
        **_: Any,
    ) -> dict[str, Any]:
        # If the bound LLM service implements the async protocol,
        # dispatch the I/O to it without blocking the event loop.
        if isinstance(self.llm, AsyncLLMService):
            return await self.llm.avalidate_mapping(
                source_field=source_field,
                candidate_targets=candidate_targets,
                context=context or {},
            )
        return self._run(
            source_field=source_field,
            candidate_targets=candidate_targets,
            context=context,
        )


class GenerateTransformationTool(BaseTool):  # type: ignore[misc, valid-type]
    """LangChain tool that calls ``LLMService.generate_transformation`` (advisory)."""

    name: str = "semantra_generate_transformation"
    description: str = (
        "Generate starter transformation code (Pandas / PySpark / dbt) "
        "for an accepted mapping decision. Output is **advisory** — must "
        "be reviewed before use."
    )
    args_schema: Type[_BaseModel] = _GenerateTransformationInput  # type: ignore[assignment]

    llm: Any = None

    def _run(  # type: ignore[override]
        self,
        mapping_decision: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        **_: Any,
    ) -> str:
        decision = MappingDecision.model_validate(mapping_decision)
        return self.llm.generate_transformation(decision, context=context or {})

    async def _arun(  # type: ignore[override]
        self,
        mapping_decision: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
        **_: Any,
    ) -> str:
        # If the bound LLM service implements the async protocol,
        # dispatch the I/O to it without blocking the event loop.
        if isinstance(self.llm, AsyncLLMService):
            decision = MappingDecision.model_validate(mapping_decision)
            return await self.llm.agenerate_transformation(
                decision, context=context or {}
            )
        return self._run(mapping_decision=mapping_decision, context=context)


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------


def build_semantra_tools(
    engine: Optional[MappingEngine | AsyncMappingEngine] = None,
    async_engine: Optional[AsyncMappingEngine] = None,
    knowledge: Optional[KnowledgeBase] = None,
    llm: Optional[LLMService] = None,
    connector: Optional[Connector] = None,
) -> list[BaseTool]:
    """Build a list of LangChain tools over the provided semantra_core services.

    Pass only the services you have. Tools are returned only for the
    services that are provided, so the resulting agent only sees the
    capabilities it actually has.

    Example::

        from semantra_core.services import InMemoryMappingEngine, BoundedLLMService
        from semantra_agent.langchain_tools import build_semantra_tools

        tools = build_semantra_tools(
            engine=InMemoryMappingEngine(),
            llm=BoundedLLMService(),
        )

    Raises:
        RuntimeError: if LangChain is not installed in the current
            environment. Install with ``pip install -e
            'semantra_agent[langchain]'``.
    """
    if not _LANGCHAIN_AVAILABLE:
        raise RuntimeError(
            "LangChain is not installed. "
            "Run: pip install -e 'semantra_agent[langchain]'"
        )

    tools: list[BaseTool] = []
    selected_engine = async_engine if async_engine is not None else engine
    if selected_engine is not None:
        tools.append(MapSourceToTargetTool(engine=selected_engine))  # type: ignore[arg-type]
    if knowledge is not None:
        tools.append(GetCanonicalConceptTool(knowledge=knowledge))  # type: ignore[arg-type]
        tools.append(SearchConceptsTool(knowledge=knowledge))  # type: ignore[arg-type]
    if llm is not None:
        tools.append(ValidateMappingTool(llm=llm))  # type: ignore[arg-type]
        tools.append(GenerateTransformationTool(llm=llm))  # type: ignore[arg-type]
    # Connector tools (SchemaProfile / DatasetHandle fetchers) — placeholder
    # for when the connector becomes a first-class service in the SDK.
    return tools


__all__ = [
    "MapSourceToTargetTool",
    "GetCanonicalConceptTool",
    "SearchConceptsTool",
    "ValidateMappingTool",
    "GenerateTransformationTool",
    "build_semantra_tools",
]
