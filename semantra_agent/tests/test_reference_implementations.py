"""Unit tests for the reference stub implementations in
``semantra_core.services.implementations``.

The stubs are intentionally minimal: they exist so that downstream code and
agent workflows can be exercised without a real backend. These tests pin the
observable contract of each stub.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# InMemoryMappingEngine
# ---------------------------------------------------------------------------


def test_in_memory_mapping_engine_finds_substring_match(
    source_handle, target_schema
) -> None:
    """Source column ``id`` is a substring of target column ``user_id``,
    so the stub must produce one substring match candidate."""
    engine = InMemoryMappingEngine()
    result = engine.map_source_to_target(source_handle, target_schema)

    assert len(result) == 1
    cand = result[0]
    assert cand.target == "user_id"
    assert cand.confidence == pytest.approx(0.7)
    assert cand.method == "in_memory_substring_match"
    # ``source`` is attached dynamically via object.__setattr__ (not a
    # Pydantic field), so access it via getattr to keep static checkers
    # happy.
    assert getattr(cand, "source", None) == "id"
    assert cand.signals.name == pytest.approx(0.7)


def test_in_memory_mapping_engine_default_signals_are_all_zero() -> None:
    """Default scoring signals should be a fresh, all-zero ScoringSignals."""
    engine = InMemoryMappingEngine()
    signals = engine.get_scoring_signals()
    assert isinstance(signals, ScoringSignals)
    assert signals == ScoringSignals()


def test_in_memory_mapping_engine_is_reusable_across_calls(
    source_handle, target_schema
) -> None:
    """Calling the same engine multiple times should remain deterministic."""
    engine = InMemoryMappingEngine()
    first = engine.map_source_to_target(source_handle, target_schema)
    second = engine.map_source_to_target(source_handle, target_schema)
    assert first == second
    assert len(first) == 1  # same match produced both times


def test_in_memory_mapping_engine_finds_exact_case_insensitive_match() -> None:
    """Source ``Email`` and target ``email`` should match exactly (case-insensitive)."""
    from semantra_core.models.schema import ColumnProfile, DatasetHandle, SchemaProfile

    src = DatasetHandle(
        dataset_id="s",
        dataset_name="s",
        schema_profile=SchemaProfile(
            dataset_id="s",
            dataset_name="s",
            row_count=1,
            columns=[ColumnProfile(
                name="Email", normalized_name="Email", dtype="str",
                null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
            )],
        ),
    )
    tgt = SchemaProfile(
        dataset_id="t",
        dataset_name="t",
        row_count=1,
        columns=[ColumnProfile(
            name="email", normalized_name="email", dtype="str",
            null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
        )],
    )
    engine = InMemoryMappingEngine()
    result = engine.map_source_to_target(src, tgt)
    assert len(result) == 1
    assert result[0].target == "email"
    assert result[0].confidence == pytest.approx(1.0)
    assert result[0].method == "in_memory_name_match"
    assert result[0].confidence_label == "high_confidence"


def test_in_memory_mapping_engine_returns_empty_for_no_match() -> None:
    """When no source column matches any target column, the result is []."""
    from semantra_core.models.schema import ColumnProfile, DatasetHandle, SchemaProfile

    src = DatasetHandle(
        dataset_id="s",
        dataset_name="s",
        schema_profile=SchemaProfile(
            dataset_id="s",
            dataset_name="s",
            row_count=1,
            columns=[ColumnProfile(
                name="completely_unrelated", normalized_name="completely_unrelated",
                dtype="str", null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
            )],
        ),
    )
    tgt = SchemaProfile(
        dataset_id="t",
        dataset_name="t",
        row_count=1,
        columns=[ColumnProfile(
            name="phone", normalized_name="phone", dtype="str",
            null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
        )],
    )
    engine = InMemoryMappingEngine()
    result = engine.map_source_to_target(src, tgt)
    assert result == []


def test_in_memory_mapping_engine_finds_reverse_substring() -> None:
    """Source column ``user`` is a substring of target column ``user_id``
    (forward) but also: source ``id_long_name`` contains target ``id``
    (reverse). Both directions should be considered."""
    from semantra_core.models.schema import ColumnProfile, DatasetHandle, SchemaProfile

    src = DatasetHandle(
        dataset_id="s",
        dataset_name="s",
        schema_profile=SchemaProfile(
            dataset_id="s",
            dataset_name="s",
            row_count=1,
            columns=[ColumnProfile(
                name="user", normalized_name="user", dtype="str",
                null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
            )],
        ),
    )
    tgt = SchemaProfile(
        dataset_id="t",
        dataset_name="t",
        row_count=1,
        columns=[ColumnProfile(
            name="user_id", normalized_name="user_id", dtype="str",
            null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
        )],
    )
    engine = InMemoryMappingEngine()
    result = engine.map_source_to_target(src, tgt)
    assert len(result) == 1
    assert result[0].target == "user_id"
    assert result[0].confidence == pytest.approx(0.7)
    # Forward substring: source "user" in target "user_id" → "user_id"
    assert result[0].method == "in_memory_substring_match"


def test_in_memory_mapping_engine_exact_beats_substring() -> None:
    """If both an exact and a substring match exist for the same source
    column, the exact match wins (it breaks the inner loop first)."""
    from semantra_core.models.schema import ColumnProfile, DatasetHandle, SchemaProfile

    src = DatasetHandle(
        dataset_id="s",
        dataset_name="s",
        schema_profile=SchemaProfile(
            dataset_id="s",
            dataset_name="s",
            row_count=1,
            columns=[ColumnProfile(
                name="email", normalized_name="email", dtype="str",
                null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
            )],
        ),
    )
    tgt = SchemaProfile(
        dataset_id="t",
        dataset_name="t",
        row_count=1,
        columns=[
            ColumnProfile(
                name="email_long_address", normalized_name="email_long_address",
                dtype="str", null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
            ),
            ColumnProfile(
                name="email", normalized_name="email", dtype="str",
                null_ratio=0.0, unique_ratio=1.0, non_null_count=1,
            ),
        ],
    )
    engine = InMemoryMappingEngine()
    result = engine.map_source_to_target(src, tgt)
    # The exact "email" match must win, not the substring "email_long_address".
    assert len(result) == 1
    assert result[0].target == "email"
    assert result[0].confidence == pytest.approx(1.0)
    assert result[0].method == "in_memory_name_match"


# ---------------------------------------------------------------------------
# InMemoryKnowledgeBase
# ---------------------------------------------------------------------------


def test_in_memory_knowledge_base_starts_empty() -> None:
    """A fresh knowledge base should expose no concepts and no overlay entries."""
    kb = InMemoryKnowledgeBase()
    assert kb.get_canonical_concept("anything") is None
    assert kb.search_concepts("anything") == []
    assert kb.get_active_overlay_entries() == []


def _make_concept(concept_id: str, display_name: str) -> CanonicalGlossaryEntry:
    return CanonicalGlossaryEntry(
        concept_id=concept_id,
        entity=concept_id.split(".")[0],
        attribute=concept_id.split(".")[-1],
        display_name=display_name,
    )


def test_in_memory_knowledge_base_add_and_lookup() -> None:
    """After ``add``, lookups by concept_id should return the stored entry."""
    kb = InMemoryKnowledgeBase()
    entry = _make_concept("customer.email", "Customer Email")
    kb.add(entry)
    assert kb.get_canonical_concept("customer.email") is entry
    # Unknown id returns None.
    assert kb.get_canonical_concept("unknown") is None


def test_in_memory_knowledge_base_add_overwrites_existing() -> None:
    """Re-adding the same id should overwrite the previous entry."""
    kb = InMemoryKnowledgeBase()
    first = _make_concept("customer.email", "Old Name")
    second = _make_concept("customer.email", "New Name")
    kb.add(first)
    kb.add(second)
    assert kb.get_canonical_concept("customer.email") is second


def test_in_memory_knowledge_base_search_is_case_insensitive() -> None:
    """Search should match on display_name (case-insensitive substring)."""
    kb = InMemoryKnowledgeBase()
    kb.add(_make_concept("customer.email", "Customer Email"))
    kb.add(_make_concept("customer.phone", "Customer Phone"))
    kb.add(_make_concept("order.id", "Order Id"))

    results = kb.search_concepts("CUSTOMER")
    assert len(results) == 2
    assert {r.concept_id for r in results} == {
        "customer.email",
        "customer.phone",
    }


def test_in_memory_knowledge_base_search_respects_limit() -> None:
    """Search should cap results at the requested limit."""
    kb = InMemoryKnowledgeBase()
    for i in range(5):
        kb.add(_make_concept(f"c.{i}", f"Customer {i}"))
    results = kb.search_concepts("Customer", limit=3)
    assert len(results) == 3


def test_in_memory_knowledge_base_get_active_overlay_entries_empty() -> None:
    """The stub does not model an active overlay."""
    kb = InMemoryKnowledgeBase()
    assert kb.get_active_overlay_entries() == []


# ---------------------------------------------------------------------------
# BoundedLLMService
# ---------------------------------------------------------------------------


def test_bounded_llm_service_validate_mapping_returns_first_candidate() -> None:
    """The stub should echo the first candidate with zero confidence."""
    llm = BoundedLLMService()
    result = llm.validate_mapping(
        source_field="email",
        candidate_targets=["email_address", "phone"],
        context={},
    )
    assert result["selected_target"] == "email_address"
    assert result["confidence"] == 0.0
    assert isinstance(result["reasoning"], list)
    assert result["reasoning"]  # non-empty list with a stub message


def test_bounded_llm_service_validate_mapping_handles_empty_candidates() -> None:
    """An empty candidate list should result in an empty selection."""
    llm = BoundedLLMService()
    result = llm.validate_mapping(
        source_field="email", candidate_targets=[], context={}
    )
    assert result["selected_target"] == ""
    assert result["confidence"] == 0.0
    assert isinstance(result["reasoning"], list)


def test_bounded_llm_service_generate_transformation_returns_comment() -> None:
    """The stub should return a clear disabled message, not raise."""
    llm = BoundedLLMService()
    decision = MappingDecision(source="email", target="email_address")
    code = llm.generate_transformation(decision, context={})
    assert isinstance(code, str)
    assert code.startswith("#")
    # Should not depend on the decision payload.
    assert "transformation" in code.lower()


# ---------------------------------------------------------------------------
# StaticConnector
# ---------------------------------------------------------------------------


def test_static_connector_fetch_schema_returns_injected_schema(target_schema) -> None:
    """The static connector should return the schema it was constructed with."""
    connector = StaticConnector(schema=target_schema)
    assert connector.fetch_schema() is target_schema


def test_static_connector_fetch_preview_returns_handle_with_empty_rows(
    target_schema,
) -> None:
    """fetch_preview should return a DatasetHandle with no preview rows."""
    connector = StaticConnector(schema=target_schema)
    handle = connector.fetch_preview(limit=100)
    assert handle.dataset_id == target_schema.dataset_id
    assert handle.dataset_name == target_schema.dataset_name
    assert handle.schema_profile is target_schema
    assert handle.preview_rows == []


def test_static_connector_fetch_preview_ignores_limit(target_schema) -> None:
    """The stub currently ignores the limit argument; pin that behavior."""
    connector = StaticConnector(schema=target_schema)
    small = connector.fetch_preview(limit=1)
    large = connector.fetch_preview(limit=1000)
    assert small.preview_rows == large.preview_rows == []
