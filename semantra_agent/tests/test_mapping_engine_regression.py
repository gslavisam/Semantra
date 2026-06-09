"""Regression test for the BackendMappingEngine candidate conversion.

This test guards the fix for the bug where the adapter iterated
``response.candidates`` (which does not exist on ``AutoMappingResponse``)
instead of ``response.ranked_mappings[*].candidates``. The bug silently
returned zero candidates even though the real backend had produced results.

Run this test from the semantra-core venv with the backend importable.
The test is skipped automatically when the backend is not importable, so
it does not break the offline test suite.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure both repo-root and backend/ are importable.
_REPO = Path(__file__).resolve().parents[2]  # /home/smili/Semantra
for p in (str(_REPO / "backend"), str(_REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from backend.app.services import mapping_service  # noqa: F401
    BACKEND_AVAILABLE = True
except Exception:  # noqa: BLE001
    BACKEND_AVAILABLE = False

from semantra_core.models.schema import (
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)
from semantra_backend_adapter import BackendMappingEngine


pytestmark = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="Semantra FastAPI backend not importable; skipping live regression test.",
)


def _two_column_pair() -> tuple[DatasetHandle, SchemaProfile]:
    """Minimal but realistic source/target pair."""
    source = DatasetHandle(
        dataset_id="src", dataset_name="src",
        schema_profile=SchemaProfile(
            dataset_id="src", dataset_name="src", row_count=5,
            columns=[
                ColumnProfile(
                    name="cust_id", normalized_name="cust_id", dtype="str",
                    null_ratio=0.0, unique_ratio=1.0, non_null_count=5,
                    detected_patterns=["uuid"],
                ),
                ColumnProfile(
                    name="email", normalized_name="email", dtype="str",
                    null_ratio=0.0, unique_ratio=1.0, non_null_count=5,
                    detected_patterns=["email"],
                ),
            ],
        ),
    )
    target = SchemaProfile(
        dataset_id="tgt", dataset_name="tgt", row_count=0,
        columns=[
            ColumnProfile(
                name="customer_id", normalized_name="customer_id", dtype="str",
                null_ratio=0.0, unique_ratio=0.0, non_null_count=0,
                detected_patterns=["uuid"],
            ),
            ColumnProfile(
                name="email_address", normalized_name="email_address", dtype="str",
                null_ratio=0.0, unique_ratio=0.0, non_null_count=0,
                detected_patterns=["email"],
            ),
        ],
    )
    return source, target


def test_backend_mapping_engine_returns_non_empty_candidates() -> None:
    """The real engine must surface the inner candidates from ranked_mappings.

    Before the fix, this returned [] because the adapter looked for
    ``response.candidates`` which does not exist on AutoMappingResponse.
    """
    engine = BackendMappingEngine()
    assert engine._backend_available, "backend failed to import; test cannot run"
    source, target = _two_column_pair()
    candidates = engine.map_source_to_target(source, target)
    assert candidates, "BackendMappingEngine returned no candidates (regression)"


def test_backend_mapping_engine_candidates_have_attached_source() -> None:
    """Each emitted CandidateOption should carry its source field name.

    The SDK CandidateOption does not (yet) declare a ``source`` field, so
    the adapter attaches it via ``object.__setattr__``. This test pins that
    behaviour so callers can group results by source.
    """
    engine = BackendMappingEngine()
    assert engine._backend_available
    source, target = _two_column_pair()
    candidates = engine.map_source_to_target(source, target)
    assert candidates
    sources = {getattr(c, "source", None) for c in candidates}
    # We provided two source columns, so at least one of them must appear.
    assert sources & {"cust_id", "email"}, f"no source field attached: {sources}"


def test_backend_mapping_engine_signals_match_default_profile() -> None:
    """get_scoring_signals should reflect the backend's DEFAULT_SCORING_PROFILE."""
    engine = BackendMappingEngine()
    if not engine._backend_available:
        pytest.skip("backend not available")
    signals = engine.get_scoring_signals()
    # We do not pin specific values, only that the engine returned a
    # ScoringSignals instance with at least one non-zero weight when the
    # backend is reachable.
    from semantra_core.models.mapping import ScoringSignals
    assert isinstance(signals, ScoringSignals)
    assert any(
        getattr(signals, name) > 0.0
        for name in (
            "name", "semantic", "knowledge", "canonical",
            "pattern", "statistical", "overlap", "embedding",
        )
    )
