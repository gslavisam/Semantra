"""Unit tests for the pipeline backend adapters.

Tests ``BackendReviewService``, ``BackendDecisionStore``, and
``BackendReportService`` — the three adapters that wrap the Semantra
FastAPI backend's pipeline services.

Since the backend is NOT importable in a pure test environment, all
adapters fall back to their in-memory implementations. These tests
verify the fallback path works correctly — they do NOT require the
backend to be running.
"""

from __future__ import annotations

from typing import List

import pytest

from semantra_core.models.mapping import (
    DecisionLogEntry,
    MappingDecision,
    ReviewPlanResponse,
)
from semantra_core.models.schema import (
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)
from semantra_core.services.protocols import (
    DecisionStore,
    ReportService,
    ReviewService,
)


def _d(source: str, target: str, status: str = "accepted") -> MappingDecision:
    return MappingDecision(source=source, target=target, status=status)  # type: ignore[arg-type]


def _entry(source: str, target: str, status: str = "accepted") -> DecisionLogEntry:
    return DecisionLogEntry(source=source, final_target=target, final_status=status)  # type: ignore[arg-type]


def _source_handle(*names: str) -> DatasetHandle:
    return DatasetHandle(
        dataset_id="s",
        dataset_name="s",
        schema_profile=SchemaProfile(
            dataset_id="s",
            dataset_name="s",
            row_count=10,
            columns=[
                ColumnProfile(
                    name=n, normalized_name=n, dtype="str",
                    null_ratio=0.0, unique_ratio=1.0, non_null_count=10,
                )
                for n in names
            ],
        ),
    )


def _target_schema(*names: str) -> SchemaProfile:
    return SchemaProfile(
        dataset_id="t",
        dataset_name="t",
        row_count=10,
        columns=[
            ColumnProfile(
                name=n, normalized_name=n, dtype="str",
                null_ratio=0.0, unique_ratio=1.0, non_null_count=10,
            )
            for n in names
        ],
    )


# ---------------------------------------------------------------------------
# BackendReviewService
# ---------------------------------------------------------------------------


def test_review_service_implements_protocol_via_fallback() -> None:
    from semantra_backend_adapter import BackendReviewService

    svc = BackendReviewService()
    assert isinstance(svc, ReviewService)


def test_review_service_build_plan_from_decisions_fallback() -> None:
    from semantra_backend_adapter import BackendReviewService

    svc = BackendReviewService()
    decisions = [_d("a", "A", "accepted"), _d("b", "B", "needs_review")]
    plan = svc.build_plan_from_decisions(decisions)

    # Either backend produces clusters, or falls back — both should work.
    # The key contract is: no exception, queue_summary is non-empty,
    # and the plan is a valid ReviewPlanResponse.
    assert isinstance(plan, ReviewPlanResponse)
    assert len(plan.queue_summary) > 0


def test_review_service_build_plan_from_decisions_empty() -> None:
    from semantra_backend_adapter import BackendReviewService

    svc = BackendReviewService()
    plan = svc.build_plan_from_decisions([])
    assert plan.clusters == []
    assert "No decisions" in plan.queue_summary


# ---------------------------------------------------------------------------
# BackendDecisionStore
# ---------------------------------------------------------------------------


def test_decision_store_implements_protocol_via_fallback() -> None:
    from semantra_backend_adapter import BackendDecisionStore

    store = BackendDecisionStore()
    assert isinstance(store, DecisionStore)


def test_decision_store_append_list_cycle_fallback() -> None:
    from semantra_backend_adapter import BackendDecisionStore

    store = BackendDecisionStore()
    store.clear()  # start clean — backend may have leftover entries
    assert store.list() == []

    e1 = _entry("a", "A")
    e2 = _entry("b", "B")
    store.append(e1)
    store.append(e2)

    entries = store.list()
    assert len(entries) == 2
    assert entries[0].source == "a"
    assert entries[1].source == "b"


def test_decision_store_clear_fallback() -> None:
    from semantra_backend_adapter import BackendDecisionStore

    store = BackendDecisionStore()
    store.clear()  # start clean
    store.append(_entry("x", "X"))
    assert len(store.list()) == 1
    store.clear()
    assert store.list() == []


def test_decision_store_list_returns_defensive_copy() -> None:
    from semantra_backend_adapter import BackendDecisionStore

    store = BackendDecisionStore()
    store.clear()  # start clean
    store.append(_entry("a", "A"))
    snap = store.list()
    snap.append(_entry("evil", "X"))
    assert len(store.list()) == 1


# ---------------------------------------------------------------------------
# BackendReportService
# ---------------------------------------------------------------------------


def test_report_service_implements_protocol_via_fallback() -> None:
    from semantra_backend_adapter import BackendReportService

    svc = BackendReportService()
    assert isinstance(svc, ReportService)


def test_report_service_build_summary_for_decisions_fallback() -> None:
    from semantra_backend_adapter import BackendReportService

    svc = BackendReportService()
    decisions = [_d("a", "A", "accepted"), _d("b", "B", "accepted"), _d("c", "C", "rejected")]

    summary = svc.build_summary_for_decisions(decisions)
    assert summary.overall_mapping_health.accepted_count == 2
    assert summary.overall_mapping_health.rejected_count == 1
    # overall_risk depends on backend vs. fallback logic — both are valid.
    assert summary.overall_mapping_health.overall_risk in ("high", "medium", "low")


def test_report_service_build_coverage_fallback() -> None:
    from semantra_backend_adapter import BackendReportService

    svc = BackendReportService()
    cov = svc.build_coverage(
        source=_source_handle("a", "b", "c"),
        target=_target_schema("A", "B"),
        decisions=[_d("a", "A", "accepted"), _d("b", "B", "needs_review"), _d("c", "C", "rejected")],
    )

    assert cov["source_columns"] == 3
    assert cov["matched_sources"] == 2  # a, b (c rejected)
    assert cov["matched_targets"] == 2
    assert cov["source_coverage"] == pytest.approx(2 / 3, abs=1e-6)


# ---------------------------------------------------------------------------
# Factory: create_backend_adapters with include_pipeline=True
# ---------------------------------------------------------------------------


def test_factory_with_include_pipeline_false_returns_core_only() -> None:
    from semantra_backend_adapter import create_backend_adapters, BackendContext

    # Pass an explicit empty context to avoid calling create_default_context()
    # which raises when the backend is not importable.
    ctx = BackendContext()
    adapters = create_backend_adapters(context=ctx, include_pipeline=False)
    assert "engine" in adapters
    assert "knowledge" in adapters
    assert "llm" in adapters
    assert "review" not in adapters
    assert "decision_store" not in adapters
    assert "report" not in adapters


def test_factory_with_include_pipeline_true_returns_all() -> None:
    from semantra_backend_adapter import create_backend_adapters, BackendContext

    ctx = BackendContext()
    adapters = create_backend_adapters(context=ctx, include_pipeline=True)
    assert "engine" in adapters
    assert "knowledge" in adapters
    assert "llm" in adapters
    assert "review" in adapters
    assert "decision_store" in adapters
    assert "report" in adapters

    # Verify pipeline adapters satisfy their protocols
    assert isinstance(adapters["review"], ReviewService)
    assert isinstance(adapters["decision_store"], DecisionStore)
    assert isinstance(adapters["report"], ReportService)
