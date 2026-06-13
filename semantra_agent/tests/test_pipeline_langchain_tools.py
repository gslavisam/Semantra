"""Unit tests for the pipeline LangChain tool wrappers.

Tests ``BuildReviewPlanTool``, ``AppendDecisionLogTool``,
``ListDecisionsTool``, ``BuildMappingSummaryTool``, and
``BuildCoverageReportTool`` — the five LangChain tools that wrap the
pipeline services (ReviewService, DecisionStore, ReportService).

Uses in-memory reference implementations — no LangChain LLM, no
Semantra backend required.
"""

from __future__ import annotations

from typing import Any

import pytest

from semantra_core.models.mapping import (
    DecisionLogEntry,
    MappingDecision,
)
from semantra_core.models.schema import (
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)
from semantra_core.services.implementations import (
    InMemoryDecisionStore,
    InMemoryReportService,
    InMemoryReviewService,
)

# Skip if langchain_core is not available.
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
        AppendDecisionLogTool,
        BuildCoverageReportTool,
        BuildMappingSummaryTool,
        BuildReviewPlanTool,
        ListDecisionsTool,
        build_semantra_tools,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
# Factory: build_semantra_tools with pipeline services
# ---------------------------------------------------------------------------


def test_factory_with_pipeline_services_returns_all_tools() -> None:
    tools = build_semantra_tools(
        review_service=InMemoryReviewService(),
        decision_store=InMemoryDecisionStore(),
        report_service=InMemoryReportService(),
    )
    # review (1) + store (2: append + list) + report (2: summary + coverage) = 5
    assert len(tools) == 5
    names = {t.name for t in tools}
    assert "semantra_build_review_plan" in names
    assert "semantra_append_decision_log" in names
    assert "semantra_list_decisions" in names
    assert "semantra_build_mapping_summary" in names
    assert "semantra_build_coverage_report" in names


def test_factory_with_core_and_pipeline_services_returns_all() -> None:
    from semantra_core.services.implementations import (
        InMemoryMappingEngine,
        BoundedLLMService,
    )

    tools = build_semantra_tools(
        engine=InMemoryMappingEngine(),
        llm=BoundedLLMService(),
        review_service=InMemoryReviewService(),
        decision_store=InMemoryDecisionStore(),
        report_service=InMemoryReportService(),
    )
    # core: 1 (engine) + 2 (llm) = 3; pipeline: 1 + 2 + 2 = 5 → 8 total
    assert len(tools) == 8


# ---------------------------------------------------------------------------
# BuildReviewPlanTool
# ---------------------------------------------------------------------------


def test_build_review_plan_tool_empty_decisions() -> None:
    tool = BuildReviewPlanTool(review_service=InMemoryReviewService())  # type: ignore[arg-type,call-arg]
    result = tool._run(decisions=[])
    assert result["clusters"] == []
    assert result["risks"] == []
    assert "No decisions" in result["queue_summary"]


def test_build_review_plan_tool_with_mixed_statuses() -> None:
    tool = BuildReviewPlanTool(review_service=InMemoryReviewService())  # type: ignore[arg-type,call-arg]
    decisions = [_d("a", "A", "accepted"), _d("b", "B", "needs_review"), _d("c", "C", "rejected")]
    result = tool._run(decisions=[d.model_dump() for d in decisions])

    assert len(result["clusters"]) == 3
    assert "1 accepted" in result["queue_summary"]
    priorities = [c["priority"] for c in result["clusters"]]
    # Clusters must be sorted high → medium → low
    assert priorities == ["high", "medium", "low"] or priorities == sorted(
        priorities, key=lambda p: ["high", "medium", "low"].index(p)
    )


# ---------------------------------------------------------------------------
# AppendDecisionLogTool + ListDecisionsTool
# ---------------------------------------------------------------------------


def test_append_and_list_decision_log_cycle() -> None:
    store = InMemoryDecisionStore()
    append_tool = AppendDecisionLogTool(decision_store=store)  # type: ignore[arg-type,call-arg]
    list_tool = ListDecisionsTool(decision_store=store)  # type: ignore[arg-type,call-arg]

    e1 = _entry("a", "A", "accepted")
    e2 = _entry("b", "B", "needs_review")

    result_msg = append_tool._run(entries=[e1.model_dump(), e2.model_dump()])
    assert "2" in result_msg

    listed = list_tool._run()
    assert len(listed) == 2
    assert listed[0]["source"] == "a"
    assert listed[0]["final_target"] == "A"
    assert listed[1]["source"] == "b"
    assert listed[1]["final_status"] == "needs_review"


def test_list_decisions_tool_empty_store_returns_empty_list() -> None:
    tool = ListDecisionsTool(decision_store=InMemoryDecisionStore())  # type: ignore[arg-type,call-arg]
    assert tool._run() == []


# ---------------------------------------------------------------------------
# BuildMappingSummaryTool
# ---------------------------------------------------------------------------


def test_build_mapping_summary_tool_with_decisions() -> None:
    tool = BuildMappingSummaryTool(report_service=InMemoryReportService())  # type: ignore[arg-type,call-arg]
    decisions = [_d("a", "A", "accepted"), _d("b", "B", "accepted"), _d("c", "C", "rejected")]
    result = tool._run(decisions=[d.model_dump() for d in decisions])

    assert result["overall_risk"] == "high"  # rejected → high risk
    assert result["accepted_count"] == 2
    assert result["rejected_count"] == 1
    assert "implementation_risks" in result


def test_build_mapping_summary_tool_empty_input() -> None:
    tool = BuildMappingSummaryTool(report_service=InMemoryReportService())  # type: ignore[arg-type,call-arg]
    result = tool._run(decisions=[])
    assert result["accepted_count"] == 0
    assert result["overall_risk"] == "low"


# ---------------------------------------------------------------------------
# BuildCoverageReportTool
# ---------------------------------------------------------------------------


def test_build_coverage_report_tool_calculates_ratios() -> None:
    tool = BuildCoverageReportTool(report_service=InMemoryReportService())  # type: ignore[arg-type,call-arg]
    decisions = [_d("a", "A", "accepted"), _d("b", "B", "needs_review"), _d("d", "D", "rejected")]

    result = tool._run(
        source=_source_handle("a", "b", "c", "d").model_dump(),
        target=_target_schema("A", "B", "C", "E").model_dump(),
        decisions=[d.model_dump() for d in decisions],
    )

    assert result["source_columns"] == 4
    assert result["target_columns"] == 4
    assert result["matched_sources"] == 2  # a, b (d is rejected)
    assert result["matched_targets"] == 2
    assert result["source_coverage"] == pytest.approx(2 / 4, abs=1e-6)
    assert result["target_coverage"] == pytest.approx(2 / 4, abs=1e-6)
    assert "d" in result["unmatched_sources"]
    assert "E" in result["unmatched_targets"]
