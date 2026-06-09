"""Unit tests for the three new pipeline services added by the audit
follow-up: ``ReviewService``, ``DecisionStore``, and ``ReportService``.

Each is tested both for its core contract (does the right thing for
typical inputs?) and for Protocol conformance (does it satisfy the
runtime-checkable ``@runtime_checkable`` Protocol?). A short
end-to-end test wires the three services together so regressions in
how they inter-operate get caught by a single test.
"""

from __future__ import annotations

from typing import Literal

import pytest

from semantra_core.models.schema import (
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)
from semantra_core.models.mapping import (
    DecisionLogEntry,
    DecisionStatus,
    MappingDecision,
)
from semantra_core.services import (
    DecisionStore,
    InMemoryDecisionStore,
    InMemoryReportService,
    InMemoryReviewService,
    ReportService,
    ReviewService,
)


def _decision(
    source: str, target: str, status: DecisionStatus = "accepted"
) -> MappingDecision:
    return MappingDecision(source=source, target=target, status=status)


def _log_entry(
    source: str, target: str, status: DecisionStatus = "accepted"
) -> DecisionLogEntry:
    return DecisionLogEntry(source=source, final_target=target, final_status=status)


def _source_handle(*column_names: str) -> DatasetHandle:
    cols = [
        ColumnProfile(
            name=n,
            normalized_name=n,
            dtype="str",
            null_ratio=0.0,
            unique_ratio=1.0,
            non_null_count=10,
        )
        for n in column_names
    ]
    schema = SchemaProfile(
        dataset_id="s",
        dataset_name="s",
        row_count=10,
        columns=cols,
    )
    return DatasetHandle(
        dataset_id="s",
        dataset_name="s",
        schema_profile=schema,
    )


def _target_schema(*column_names: str) -> SchemaProfile:
    return SchemaProfile(
        dataset_id="t",
        dataset_name="t",
        row_count=10,
        columns=[
            ColumnProfile(
                name=n,
                normalized_name=n,
                dtype="str",
                null_ratio=0.0,
                unique_ratio=1.0,
                non_null_count=10,
            )
            for n in column_names
        ],
    )


# ---------------------------------------------------------------------------
# InMemoryReviewService
# ---------------------------------------------------------------------------


def test_review_service_isinstance_protocol() -> None:
    """An InMemory instance must satisfy the runtime-checkable Protocol."""
    assert isinstance(InMemoryReviewService(), ReviewService)


def test_review_service_empty_input_returns_empty_plan() -> None:
    plan = InMemoryReviewService().build_plan_from_decisions([])
    assert plan.clusters == []
    assert plan.risks == []
    assert plan.next_actions == []
    assert "No decisions" in plan.queue_summary


def test_review_service_groups_decisions_by_status() -> None:
    """A mixed-status batch must produce one cluster per status, with
    high/medium/low priority assigned by status severity."""
    decisions = [
        _decision("a", "A", "accepted"),
        _decision("b", "B", "accepted"),
        _decision("c", "C", "rejected"),
        _decision("d", "D", "needs_review"),
    ]
    plan = InMemoryReviewService().build_plan_from_decisions(decisions)

    by_status = {c.issue_type: c for c in plan.clusters}
    assert "status_accepted" in by_status
    assert "status_rejected" in by_status
    assert "status_needs_review" in by_status

    assert by_status["status_accepted"].count == 2
    assert by_status["status_rejected"].count == 1
    assert by_status["status_rejected"].priority == "high"
    assert by_status["status_needs_review"].priority == "medium"
    assert by_status["status_accepted"].priority == "low"

    # Clusters should be sorted by priority (high → medium → low).
    priorities = [c.priority for c in plan.clusters]
    assert priorities == sorted(priorities, key=lambda p: ["high", "medium", "low"].index(p))

    # Risks should mention the non-accepted clusters.
    assert any("rejected" in r for r in plan.risks)
    # Focus string uses "status='needs_review'" — match on the focus, not
    # the natural-language risk text.
    assert any("needs_review" in c.focus for c in plan.clusters)


# ---------------------------------------------------------------------------
# InMemoryDecisionStore
# ---------------------------------------------------------------------------


def test_decision_store_isinstance_protocol() -> None:
    assert isinstance(InMemoryDecisionStore(), DecisionStore)


def test_decision_store_append_list_clear_cycle() -> None:
    store = InMemoryDecisionStore()
    assert store.list() == []

    e1 = _log_entry("a", "A")
    e2 = _log_entry("b", "B")
    store.append(e1)
    store.append(e2)

    listed = store.list()
    assert len(listed) == 2
    assert listed[0] is e1
    assert listed[1] is e2

    store.clear()
    assert store.list() == []


def test_decision_store_list_returns_a_copy() -> None:
    """Mutating the returned list must not affect the store."""
    store = InMemoryDecisionStore()
    store.append(_log_entry("a", "A"))

    snap = store.list()
    snap.append(_log_entry("evil", "X"))  # try to inject
    assert len(store.list()) == 1, "list() must return a defensive copy"


# ---------------------------------------------------------------------------
# InMemoryReportService
# ---------------------------------------------------------------------------


def test_report_service_isinstance_protocol() -> None:
    assert isinstance(InMemoryReportService(), ReportService)


def test_report_service_summary_for_decisions_has_health() -> None:
    """build_summary_for_decisions should populate the overall health
    block with the right counts and the confidence distribution."""
    decisions = [
        _decision("a", "A", "accepted"),
        _decision("b", "B", "accepted"),
        _decision("c", "C", "rejected"),
    ]
    summary = InMemoryReportService().build_summary_for_decisions(decisions)

    health = summary.overall_mapping_health
    assert health.accepted_count == 2
    assert health.rejected_count == 1
    assert health.unmatched_count == 0
    assert health.high_confidence_count == 2
    assert health.low_confidence_count == 1
    # Any rejected mappings make the overall risk "high".
    assert health.overall_risk == "high"

    dist = summary.confidence_distribution
    assert dist.high_confidence_count == 2
    assert dist.low_confidence_count == 1
    assert dist.high_confidence_ratio == pytest.approx(2 / 3, abs=1e-6)


def test_report_service_coverage_calculates_ratios() -> None:
    """build_coverage must report matched/unmatched counts and ratios.

    Coverage counts BOTH accepted and needs_review items as "mapped"
    (they both have a target); only rejected is excluded.
    """
    decisions = [
        _decision("a", "A", "accepted"),
        _decision("b", "B", "accepted"),
        _decision("c", "C", "needs_review"),
        _decision("d", "D", "rejected"),
    ]
    cov = InMemoryReportService().build_coverage(
        source=_source_handle("a", "b", "c", "d"),
        target=_target_schema("A", "B", "C", "E"),
        decisions=decisions,
    )

    assert cov["source_columns"] == 4
    assert cov["target_columns"] == 4
    assert cov["matched_sources"] == 3  # a, b, c — not d (rejected)
    assert cov["matched_targets"] == 3
    assert cov["matched_pairs"] == 3
    assert cov["source_coverage"] == pytest.approx(3 / 4, abs=1e-6)
    assert cov["target_coverage"] == pytest.approx(3 / 4, abs=1e-6)
    assert cov["overall_coverage"] == pytest.approx(3 / 4, abs=1e-6)
    assert cov["unmatched_sources"] == ["d"]
    assert cov["unmatched_targets"] == ["E"]


# ---------------------------------------------------------------------------
# End-to-end: the three services in concert (the agent pipeline)
# ---------------------------------------------------------------------------


def test_agent_pipeline_runs_end_to_end_without_an_llm() -> None:
    """Build decisions from a candidate set, run them through review +
    store + report. No LLM, no I/O, no pauses. This is the contract
    that lets the agent run the whole pipeline in-process."""
    # Setup: a candidate → decision policy (high conf accepted, low rejected).
    candidates = [
        ("a", "A", 0.95, "accepted"),
        ("b", "B", 0.50, "needs_review"),
        ("c", "C", 0.05, "rejected"),
    ]
    decisions = [
        MappingDecision(source=s, target=t, status=st)  # type: ignore[arg-type]
        for s, t, _, st in candidates
    ]

    review = InMemoryReviewService()
    store = InMemoryDecisionStore()
    report = InMemoryReportService()

    # 1. Persist all decisions (the audit-followup contract is append-only).
    for d in decisions:
        store.append(DecisionLogEntry(
            source=d.source,
            final_target=d.target,
            final_status=d.status,
        ))
    assert len(store.list()) == 3

    # 2. Review the set.
    plan = review.build_plan_from_decisions(decisions)
    assert len(plan.clusters) == 3
    assert "1 accepted" in plan.queue_summary

    # 3. Build the report.
    summary = report.build_summary_for_decisions(decisions)
    assert summary.overall_mapping_health.accepted_count == 1
    assert summary.overall_mapping_health.needs_review_count == 1
    assert summary.overall_mapping_health.rejected_count == 1

    # 4. Compute coverage.
    cov = report.build_coverage(
        source=_source_handle("a", "b", "c"),
        target=_target_schema("A", "B", "C"),
        decisions=decisions,
    )
    # All three source/target columns are matched (we accepted/need-review/rejected
    # all three, and our coverage considers non-rejected as matched).
    assert cov["matched_sources"] == 2  # accepted + needs_review
    assert cov["matched_targets"] == 2
