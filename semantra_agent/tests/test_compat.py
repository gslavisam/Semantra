"""Unit tests for ``semantra_backend_adapter._compat.to_candidate_option``.

The conversion function is the single point where backend model instances
become SDK model instances, so its behaviour must be pinned in isolation
even when no real backend is available. Each test below covers one input
shape (core instance, Pydantic-from-another-module, dict, duck-typed) and
the fail-loud guarantee.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict
from pydantic import ValidationError as PydanticValidationError

from semantra_core.models.mapping import (
    CandidateOption,
    CanonicalConceptMatchDetail,
    CanonicalMappingDetails,
    ScoringSignals,
)


def _full_candidate_dict() -> dict:
    """A dict with EVERY field populated — used to assert that
    model_validate preserves all the rich payload, not just the basics."""
    return {
        "target": "user_id",
        "confidence": 0.92,
        "confidence_label": "high_confidence",
        "method": "name_match",
        "signals": {"name": 1.0, "semantic": 0.8, "knowledge": 0.5},
        "explanation": ["names match", "types match"],
        "canonical_details": {
            "source_concepts": [
                {"concept_id": "user.id", "display_name": "User ID", "strength": 0.9}
            ],
            "target_concepts": [
                {"concept_id": "user.identifier", "display_name": "User Identifier", "strength": 0.9}
            ],
            "shared_concepts": [
                {"concept_id": "user.identity", "display_name": "User Identity", "strength": 0.85}
            ],
        },
    }


# ---------------------------------------------------------------------------
# Path 1: core instance → no-op
# ---------------------------------------------------------------------------


def test_to_candidate_option_returns_same_instance_for_core() -> None:
    """An input that is already a core CandidateOption must be returned as-is."""
    from semantra_backend_adapter._compat import to_candidate_option

    original = CandidateOption(
        target="x",
        confidence=0.5,
        confidence_label="medium_confidence",
        method="stub",
        signals=ScoringSignals(),
        explanation=["e1"],
        canonical_details=CanonicalMappingDetails(),
    )
    result = to_candidate_option(original)
    assert result is original, "core instance must be returned as-is (identity preserved)"


# ---------------------------------------------------------------------------
# Path 2: dict → validated
# ---------------------------------------------------------------------------


def test_to_candidate_option_converts_dict() -> None:
    """A plain dict with the right keys is validated into a core CandidateOption."""
    from semantra_backend_adapter._compat import to_candidate_option

    result = to_candidate_option(_full_candidate_dict())
    assert isinstance(result, CandidateOption)
    assert result.target == "user_id"
    assert result.confidence == pytest.approx(0.92)
    assert result.method == "name_match"


def test_to_candidate_option_preserves_rich_payload_from_dict() -> None:
    """The whole point of the refactor: every field the backend provides
    must reach the SDK, not just the obvious ones."""
    from semantra_backend_adapter._compat import to_candidate_option

    result = to_candidate_option(_full_candidate_dict())

    # The signals (a nested Pydantic model) must round-trip with values intact.
    assert isinstance(result.signals, ScoringSignals)
    assert result.signals.name == pytest.approx(1.0)
    assert result.signals.semantic == pytest.approx(0.8)
    assert result.signals.knowledge == pytest.approx(0.5)

    # The canonical_details (also nested) must round-trip.
    assert isinstance(result.canonical_details, CanonicalMappingDetails)
    assert len(result.canonical_details.source_concepts) == 1
    assert result.canonical_details.source_concepts[0].concept_id == "user.id"
    assert len(result.canonical_details.target_concepts) == 1
    assert len(result.canonical_details.shared_concepts) == 1
    assert result.canonical_details.shared_concepts[0].strength == pytest.approx(0.85)

    # Explanations preserved verbatim.
    assert result.explanation == ["names match", "types match"]


# ---------------------------------------------------------------------------
# Path 3: another Pydantic model with the same shape → model_dump round-trip
# ---------------------------------------------------------------------------


def test_to_candidate_option_round_trips_foreign_pydantic_model() -> None:
    """A Pydantic model from a *different* class (simulating the backend's
    CandidateOption) must be converted via model_dump + model_validate."""
    from semantra_backend_adapter._compat import to_candidate_option

    class ForeignCandidate(BaseModel):
        """A Pydantic model with the same fields as core CandidateOption
        but a different class identity (this is exactly the situation
        we have with backend.app.models.mapping.CandidateOption)."""

        model_config = ConfigDict(extra="ignore")  # match default behaviour

        target: str
        confidence: float
        confidence_label: str
        method: str
        signals: ScoringSignals
        explanation: list[str] = []
        canonical_details: CanonicalMappingDetails = CanonicalMappingDetails()

    foreign = ForeignCandidate(
        target="email",
        confidence=0.7,
        confidence_label="medium_confidence",
        method="foreign",
        signals=ScoringSignals(name=0.5),
        explanation=["foreign match"],
        canonical_details=CanonicalMappingDetails(),
    )

    result = to_candidate_option(foreign)
    assert isinstance(result, CandidateOption)
    assert result.target == "email"
    assert result.confidence == pytest.approx(0.7)
    assert result.method == "foreign"
    # Signals are preserved (not lost like with getattr reconstruction).
    assert result.signals.name == pytest.approx(0.5)


def test_to_candidate_option_drops_extra_fields_from_foreign_model() -> None:
    """If the foreign Pydantic model has extra fields, they are dropped
    (default Pydantic behaviour) — we only want known SDK fields."""
    from semantra_backend_adapter._compat import to_candidate_option

    class ForeignWithExtra(BaseModel):
        target: str
        confidence: float
        confidence_label: str
        method: str
        signals: ScoringSignals
        explanation: list[str] = []
        canonical_details: CanonicalMappingDetails = CanonicalMappingDetails()
        # Extra field that doesn't exist in core CandidateOption.
        backend_internal_id: int = 42

    foreign = ForeignWithExtra(
        target="x",
        confidence=0.1,
        confidence_label="low_confidence",
        method="test",
        signals=ScoringSignals(),
    )
    result = to_candidate_option(foreign)
    # The extra field is dropped (no error, no leakage).
    assert not hasattr(result, "backend_internal_id")
    assert result.target == "x"


# ---------------------------------------------------------------------------
# Path 4: duck-typed fallback
# ---------------------------------------------------------------------------


def test_to_candidate_option_duck_typed_uses_getattr_with_defaults() -> None:
    """Non-Pydantic objects (e.g. old backend shapes, test stubs) must be
    reconstructed via getattr with sensible defaults."""
    from semantra_backend_adapter._compat import to_candidate_option

    class _OldShape:
        """Pretends to be a backend response from a very old version that
        returned duck-typed objects, not Pydantic models."""

        target = "phone"
        confidence = 0.6
        confidence_label = "medium_confidence"
        method = "legacy"
        signals = ScoringSignals(name=0.5)
        explanation = ["legacy match"]
        canonical_details = CanonicalMappingDetails()

    result = to_candidate_option(_OldShape())
    assert isinstance(result, CandidateOption)
    assert result.target == "phone"
    assert result.method == "legacy"
    assert result.signals.name == pytest.approx(0.5)


def test_to_candidate_option_duck_typed_missing_fields_get_defaults() -> None:
    """A duck-typed object missing optional fields must not crash — it
    picks up the default values from the core CandidateOption model."""
    from semantra_backend_adapter._compat import to_candidate_option

    class _Minimal:
        target = "y"
        confidence = 0.4
        confidence_label = "low_confidence"
        method = "min"

    result = to_candidate_option(_Minimal())
    assert result.target == "y"
    # Default signals (all zero).
    assert result.signals == ScoringSignals()
    # Default empty explanations.
    assert result.explanation == []
    # Default empty canonical_details.
    assert result.canonical_details == CanonicalMappingDetails()


# ---------------------------------------------------------------------------
# Fail-loud guarantee
# ---------------------------------------------------------------------------


def test_to_candidate_option_raises_on_missing_required_field() -> None:
    """A dict that lacks a required field must raise ValidationError
    — silently producing a half-built CandidateOption is the bug we
    are replacing with getattr."""
    from semantra_backend_adapter._compat import to_candidate_option

    bad = {
        "target": "x",
        # missing confidence (required, no default)
        "confidence_label": "low_confidence",
        "method": "test",
        "signals": {},
    }
    with pytest.raises(PydanticValidationError):
        to_candidate_option(bad)


def test_to_candidate_option_raises_on_invalid_confidence_label() -> None:
    """A ``confidence_label`` that is not in the Literal set must fail-loud."""
    from semantra_backend_adapter._compat import to_candidate_option

    bad = {
        "target": "x",
        "confidence": 0.5,
        "confidence_label": "VERY_HIGH",  # not in Literal
        "method": "test",
        "signals": {},
    }
    with pytest.raises(PydanticValidationError):
        to_candidate_option(bad)


# ---------------------------------------------------------------------------
# Adapter integration: the full path through _convert_candidates
# ---------------------------------------------------------------------------


def test_adapter_preserves_signals_from_backend_payload(
    monkeypatch, source_handle, target_schema
) -> None:
    """End-to-end: a backend-shaped Pydantic ``SourceMappingResult`` with
    rich ``signals`` and ``canonical_details`` must survive the round trip
    through ``BackendMappingEngine.map_source_to_target`` — the original
    bug was that the adapter's ``getattr`` re-construction dropped these."""
    import sys
    import types
    from unittest.mock import MagicMock

    from semantra_core.models.mapping import CanonicalMappingDetails

    fake_mapping = types.ModuleType("backend.app.services.mapping_service")
    fake_policy = types.ModuleType("backend.app.services.mapping_policy")

    rich_candidate = CandidateOption(
        target="user_id",
        confidence=0.88,
        confidence_label="high_confidence",
        method="name+knowledge",
        signals=ScoringSignals(name=1.0, knowledge=0.7),
        explanation=["names match", "shared concept: user.identity"],
        canonical_details=CanonicalMappingDetails(
            shared_concepts=[
                CanonicalConceptMatchDetail(
                    concept_id="user.identity",
                    display_name="User Identity",
                    strength=0.85,
                )
            ]
        ),
    )

    ranked = MagicMock()
    ranked.source = "id"
    ranked.candidates = [rich_candidate]
    ranked.selected = None

    mock_response = MagicMock()
    mock_response.ranked_mappings = [ranked]

    fake_mapping.generate_mapping_candidates = MagicMock(return_value=mock_response)
    fake_mapping.DEFAULT_SCORING_PROFILE = "balanced"
    fake_policy.SCORING_PROFILES = {"balanced": {}}

    for name, module in [
        ("backend", types.ModuleType("backend")),
        ("backend.app", types.ModuleType("backend.app")),
        ("backend.app.services", types.ModuleType("backend.app.services")),
        ("backend.app.services.mapping_service", fake_mapping),
        ("backend.app.services.mapping_policy", fake_policy),
    ]:
        monkeypatch.setitem(sys.modules, name, module)

    from semantra_backend_adapter.mapping import BackendMappingEngine

    engine = BackendMappingEngine()
    result = engine.map_source_to_target(source_handle, target_schema)

    assert len(result) == 1
    assert result[0].target == "user_id"
    # Rich signals survived.
    assert result[0].signals.name == pytest.approx(1.0)
    assert result[0].signals.knowledge == pytest.approx(0.7)
    # Rich canonical_details survived.
    assert len(result[0].canonical_details.shared_concepts) == 1
    assert result[0].canonical_details.shared_concepts[0].concept_id == "user.identity"
    # Explanations preserved.
    assert result[0].explanation == [
        "names match",
        "shared concept: user.identity",
    ]
