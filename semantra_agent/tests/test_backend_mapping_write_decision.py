"""Regression test for the SDK's decision-log side-effect.

Originally the adapter called
``mapping_service.generate_mapping_candidates(source_schema=..., target_schema=...)``
without forwarding ``write_decision_log``, so the backend's default of
``True`` kicked in and the SDK was silently writing to the database on
every call. This test pins the contract: SDK callers must NOT trigger
persistence, so ``write_decision_log`` must be explicitly forwarded as
``False``.

The test injects a fake ``backend.app.services`` module hierarchy into
``sys.modules`` so it runs regardless of whether the real backend
package is importable in the test environment.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest


def _install_fake_backend_modules(
    monkeypatch, *, generate_return
) -> MagicMock:
    """Create a minimal ``backend.app.services.*`` namespace in sys.modules.

    Returns the mock object representing ``generate_mapping_candidates``
    so the caller can inspect how it was invoked.
    """
    fake_backend = types.ModuleType("backend")
    fake_app = types.ModuleType("backend.app")
    fake_services = types.ModuleType("backend.app.services")
    fake_mapping = types.ModuleType("backend.app.services.mapping_service")
    fake_policy = types.ModuleType("backend.app.services.mapping_policy")

    mock_generate = MagicMock(return_value=generate_return)
    fake_mapping.generate_mapping_candidates = mock_generate
    fake_mapping.DEFAULT_SCORING_PROFILE = "balanced"
    fake_policy.SCORING_PROFILES = {"balanced": {}}

    for name, module in [
        ("backend", fake_backend),
        ("backend.app", fake_app),
        ("backend.app.services", fake_services),
        ("backend.app.services.mapping_service", fake_mapping),
        ("backend.app.services.mapping_policy", fake_policy),
    ]:
        monkeypatch.setitem(sys.modules, name, module)

    return mock_generate


def test_backend_mapping_engine_forwards_write_decision_log_false(
    monkeypatch, source_handle, target_schema
) -> None:
    """``BackendMappingEngine`` must pass ``write_decision_log=False`` so
    the SDK does not silently persist to the backend's decision log."""
    from semantra_backend_adapter.mapping import BackendMappingEngine

    mock_response = MagicMock()
    mock_response.ranked_mappings = []
    mock_generate = _install_fake_backend_modules(
        monkeypatch, generate_return=mock_response
    )

    engine = BackendMappingEngine()
    assert engine._backend_available is True, (
        "fake backend modules did not enable the backend branch — "
        "check that sys.modules injection is correct"
    )

    engine.map_source_to_target(source_handle, target_schema)

    mock_generate.assert_called_once()
    call = mock_generate.call_args
    # call.args / call.kwargs — we use kwargs.
    kwargs = call.kwargs
    assert "write_decision_log" in kwargs, (
        "adapter did not forward write_decision_log — backend default "
        "of True would silently persist decisions from SDK calls"
    )
    assert kwargs["write_decision_log"] is False, (
        f"expected write_decision_log=False, got {kwargs['write_decision_log']!r}"
    )


def test_backend_mapping_engine_passes_source_and_target_schemas(
    monkeypatch, source_handle, target_schema
) -> None:
    """Sanity check: the adapter forwards the right schema objects."""
    from semantra_backend_adapter.mapping import BackendMappingEngine

    mock_response = MagicMock()
    mock_response.ranked_mappings = []
    mock_generate = _install_fake_backend_modules(
        monkeypatch, generate_return=mock_response
    )

    engine = BackendMappingEngine()
    engine.map_source_to_target(source_handle, target_schema)

    kwargs = mock_generate.call_args.kwargs
    # source.schema_profile should be forwarded as source_schema; the
    # target SchemaProfile is forwarded as target_schema.
    assert kwargs["source_schema"] is source_handle.schema_profile
    assert kwargs["target_schema"] is target_schema


def test_backend_mapping_engine_returns_candidates_from_response(
    monkeypatch, source_handle, target_schema
) -> None:
    """When the backend returns ranked candidates, they must be
    converted to the SDK's ``CandidateOption`` list (not flattened
    silently)."""
    from semantra_core.models.mapping import CandidateOption

    from semantra_backend_adapter.mapping import BackendMappingEngine

    # Construct a backend-shaped response with one ranked mapping
    # containing one inner candidate.
    inner_candidate = MagicMock(spec=CandidateOption)
    inner_candidate.target = "user_id"
    inner_candidate.confidence = 0.9
    inner_candidate.confidence_label = "high_confidence"
    inner_candidate.method = "backend"
    inner_candidate.signals = MagicMock()
    inner_candidate.explanation = ["name match"]
    inner_candidate.canonical_details = None

    ranked = MagicMock()
    ranked.source = "id"
    ranked.candidates = [inner_candidate]

    mock_response = MagicMock()
    mock_response.ranked_mappings = [ranked]
    _ = _install_fake_backend_modules(
        monkeypatch, generate_return=mock_response
    )

    engine = BackendMappingEngine()
    result = engine.map_source_to_target(source_handle, target_schema)

    # The inner candidate was already a CandidateOption → adapter must
    # return it directly (not a getattr-rebuilt copy).
    assert len(result) == 1
    assert result[0] is inner_candidate


def test_backend_mapping_engine_falls_back_when_backend_missing(
    monkeypatch, source_handle, target_schema
) -> None:
    """If the backend import fails, the adapter must fall back to the
    in-memory stub and not raise.

    Note: the in-memory stub now performs trivial name-based matching
    (not the empty list it used to return), so the fallback result is
    *one* substring-match candidate for ``id → user_id`` — that is the
    correct, observable behaviour of the adapter when the backend is
    unavailable. The contract being tested here is that the adapter
    does NOT raise and DOES return a usable result.
    """
    from semantra_backend_adapter.mapping import BackendMappingEngine

    # Make every backend import raise.
    for name in list(sys.modules):
        if name == "backend" or name.startswith("backend."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    # Re-import in a way that the lazy import inside __init__ raises.
    import builtins
    real_import = builtins.__import__

    def _failing_import(name, *args, **kwargs):
        if name == "backend.app.services" or name.startswith("backend.app.services"):
            raise ImportError("simulated: backend not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _failing_import)

    engine = BackendMappingEngine()
    assert engine._backend_available is False

    result = engine.map_source_to_target(source_handle, target_schema)
    # InMemory fallback now does trivial name matching: ``id`` is a
    # substring of ``user_id`` → exactly one substring-match candidate.
    assert len(result) == 1
    assert result[0].target == "user_id"
    assert result[0].method == "in_memory_substring_match"
