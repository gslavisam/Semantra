"""Tests that both the reference implementations AND the backend adapters
implement the semantra-core protocols.

These tests are intentionally lightweight: they only verify that the
implementations can be instantiated and that they structurally satisfy the
runtime-checkable protocols. They do not require the full backend to be
importable; the adapters fall back to in-memory implementations.
"""

from __future__ import annotations

import pytest

from semantra_core.services import (
    InMemoryMappingEngine,
    InMemoryKnowledgeBase,
    BoundedLLMService,
)
from semantra_core.services.implementations import StaticConnector
from semantra_core.services.protocols import (
    MappingEngine,
    KnowledgeBase,
    LLMService,
    AsyncLLMService,
    AsyncMappingEngine,
    Connector,
    AsyncConnector,
)
from semantra_backend_adapter import (
    BackendMappingEngine,
    BackendAsyncMappingEngine,
    BackendKnowledgeBase,
    BackendLLMService,
    BackendConnector,
    create_backend_adapters,
    BackendContext,
)
from semantra_core.models.schema import SchemaProfile


# ---------------------------------------------------------------------------
# Reference implementations (semantra-core)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "stub,protocol",
    [
        (InMemoryMappingEngine(), MappingEngine),
        (InMemoryKnowledgeBase(), KnowledgeBase),
        (BoundedLLMService(), LLMService),
        (
            StaticConnector(
                schema=SchemaProfile(
                    dataset_id="x", dataset_name="x", row_count=0
                )
            ),
            Connector,
        ),
    ],
    ids=["mapping", "knowledge", "llm", "connector"],
)
def test_reference_implementation_satisfies_protocol(stub, protocol) -> None:
    """Each reference implementation should be a structural instance of its Protocol."""
    assert isinstance(stub, protocol)


def test_in_memory_mapping_engine_has_required_methods() -> None:
    """InMemoryMappingEngine should expose the exact Protocol method surface."""
    engine = InMemoryMappingEngine()
    assert hasattr(engine, "map_source_to_target")
    assert hasattr(engine, "get_scoring_signals")
    assert callable(engine.map_source_to_target)
    assert callable(engine.get_scoring_signals)


def test_in_memory_knowledge_base_has_required_methods() -> None:
    """InMemoryKnowledgeBase should expose the exact Protocol method surface."""
    kb = InMemoryKnowledgeBase()
    assert hasattr(kb, "get_canonical_concept")
    assert hasattr(kb, "search_concepts")
    assert hasattr(kb, "get_active_overlay_entries")
    assert callable(kb.get_canonical_concept)
    assert callable(kb.search_concepts)
    assert callable(kb.get_active_overlay_entries)


def test_bounded_llm_service_has_required_methods() -> None:
    """BoundedLLMService should expose the exact Protocol method surface."""
    llm = BoundedLLMService()
    assert hasattr(llm, "validate_mapping")
    assert hasattr(llm, "generate_transformation")
    assert callable(llm.validate_mapping)
    assert callable(llm.generate_transformation)


def test_static_connector_has_required_methods() -> None:
    """StaticConnector should expose the exact Protocol method surface."""
    connector = StaticConnector(
        schema=SchemaProfile(dataset_id="x", dataset_name="x", row_count=0)
    )
    assert hasattr(connector, "fetch_schema")
    assert hasattr(connector, "fetch_preview")
    assert callable(connector.fetch_schema)
    assert callable(connector.fetch_preview)


def test_protocols_are_runtime_checkable() -> None:
    """All async and sync Protocols should be runtime_checkable (i.e. usable with isinstance)."""
    for proto in (
        MappingEngine,
        AsyncMappingEngine,
        KnowledgeBase,
        LLMService,
        AsyncLLMService,
        Connector,
        AsyncConnector,
    ):
        # The `_is_runtime_protocol` attribute is set by @runtime_checkable.
        assert getattr(proto, "_is_runtime_protocol", False) is True


# ---------------------------------------------------------------------------
# Backend adapters (semantra-backend-adapter)
# ---------------------------------------------------------------------------


def test_mapping_engine_implements_protocol():
    engine = BackendMappingEngine(context=BackendContext())
    assert isinstance(engine, MappingEngine)


def test_knowledge_base_implements_protocol():
    kb = BackendKnowledgeBase(context=BackendContext())
    assert isinstance(kb, KnowledgeBase)


def test_llm_service_implements_protocol():
    llm = BackendLLMService(context=BackendContext())
    assert isinstance(llm, LLMService)


def test_async_mapping_engine_implements_protocol():
    async_engine = BackendAsyncMappingEngine(context=BackendContext())
    assert isinstance(async_engine, AsyncMappingEngine)


def test_connector_implements_protocol():
    connector = BackendConnector(dataset_id="test", context=BackendContext())
    assert isinstance(connector, Connector)


def test_factory_returns_all_adapters():
    adapters = create_backend_adapters(context=BackendContext())
    assert "engine" in adapters
    assert "knowledge" in adapters
    assert "llm" in adapters
    assert "connector" not in adapters  # no dataset_id provided
    assert "async_engine" not in adapters

    adapters_with_async = create_backend_adapters(
        context=BackendContext(), include_async_engine=True
    )
    assert "async_engine" in adapters_with_async

    adapters_with_connector = create_backend_adapters(
        context=BackendContext(), dataset_id="ds1"
    )
    assert "connector" in adapters_with_connector


def test_adapters_work_without_backend():
    """The adapters should not raise even when the backend is unavailable."""
    from semantra_core.models.schema import (
        DatasetHandle,
        SchemaProfile,
        ColumnProfile,
    )

    source = DatasetHandle(
        dataset_id="src",
        dataset_name="src",
        schema_profile=SchemaProfile(
            dataset_id="src",
            dataset_name="src",
            row_count=0,
            columns=[
                ColumnProfile(
                    name="id",
                    normalized_name="id",
                    dtype="str",
                    null_ratio=0.0,
                    unique_ratio=1.0,
                    non_null_count=0,
                )
            ],
        ),
    )
    target = SchemaProfile(
        dataset_id="tgt",
        dataset_name="tgt",
        row_count=0,
        columns=[],
    )

    adapters = create_backend_adapters(context=BackendContext())
    candidates = adapters["engine"].map_source_to_target(source, target)
    assert isinstance(candidates, list)

    concepts = adapters["knowledge"].search_concepts("anything")
    assert isinstance(concepts, list)

    result = adapters["llm"].validate_mapping("id", ["a", "b"], context={})
    assert "selected_target" in result
