"""InMemory-only mapping demo — no backend, no LangChain, no extras.

Purpose
-------
Demonstrate that the SDK's in-memory ``MappingEngine`` now produces a
non-trivial mapping output (case-insensitive exact match + substring
match) without any backend, LangChain, or LangGraph installed. This is
useful for:

  * Demos at meetups / in slides where spinning up FastAPI is overkill
  * CI smoke tests for downstream consumers
  * Local development before a real engine is wired up
  * Unit-test fixtures

Run from the ``semantra_agent/`` directory:

    .venv/bin/python examples/04c_in_memory_demo.py

Expected output
---------------
A table showing each source column, the best target column, the
confidence, and the match method (``in_memory_name_match`` or
``in_memory_substring_match``). For the demo dataset below:

  email_address → email          (exact, conf=1.0)
  main_phone   → phone           (substring, conf=0.7)
  customer_id  → user_id         (substring, conf=0.7)
  full_name    → (no match)
  go_live_date → (no match)
  ...

The original InMemory engine returned ``[]`` for every input; the new
implementation does a deterministic, two-tier name match.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make ``src/`` importable without an editable install.
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
sys.path.insert(0, str(_ROOT / "src"))

from semantra_core.models.schema import (  # noqa: E402
    ColumnProfile,
    DatasetHandle,
    SchemaProfile,
)
from semantra_core.models.mapping import (  # noqa: E402
    DecisionLogEntry,
    MappingDecision,
)
from semantra_core.services.implementations import (  # noqa: E402
    InMemoryDecisionStore,
    InMemoryMappingEngine,
    InMemoryReportService,
    InMemoryReviewService,
)


def _make_handle(
    dataset_id: str, name: str, columns: list[ColumnProfile]
) -> DatasetHandle:
    schema = SchemaProfile(
        dataset_id=dataset_id,
        dataset_name=name,
        row_count=100,
        columns=columns,
    )
    return DatasetHandle(
        dataset_id=dataset_id,
        dataset_name=name,
        schema_profile=schema,
        preview_rows=[],
    )


def _make_schema(
    dataset_id: str, name: str, columns: list[ColumnProfile]
) -> SchemaProfile:
    return SchemaProfile(
        dataset_id=dataset_id,
        dataset_name=name,
        row_count=100,
        columns=columns,
    )


def _col(name: str) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        normalized_name=name.lower(),
        dtype="str",
        null_ratio=0.0,
        unique_ratio=1.0,
        non_null_count=100,
    )


def main() -> int:
    # Realistic-ish customer schema (the same kind of columns the
    # 04_real_file_mapping_demo.py reads from CSV).
    source = _make_handle(
        "src_customers",
        "Customer Master (source)",
        columns=[
            _col("customer_id"),
            _col("email_address"),
            _col("main_phone"),
            _col("full_name"),
            _col("go_live_date"),
            _col("annual_spend_usd"),
        ],
    )

    # The canonical target schema (the one Semantra ships as the
    # "canonical customer" model). Note: the engine takes a raw
    # ``SchemaProfile`` for the target, not a ``DatasetHandle``.
    target = _make_schema(
        "tgt_canonical",
        "Canonical Customer (target)",
        columns=[
            _col("user_id"),
            _col("email"),
            _col("phone"),
            _col("customer_name"),
            _col("created_date"),
            _col("annual_revenue_usd"),
        ],
    )

    # ----- 1. MAP ------------------------------------------------------------
    engine = InMemoryMappingEngine()
    candidates = engine.map_source_to_target(source, target)

    # Group candidates by source field for a tidy table.
    by_source: dict[str, list] = {}
    for c in candidates:
        src_name = getattr(c, "source", "?")
        by_source.setdefault(src_name, []).append(c)

    print("=" * 100)
    print("InMemory mapping demo — no backend, no LangChain")
    print("=" * 100)
    print()
    print(f"Source columns: {len(source.schema_profile.columns)}")
    print(f"Target columns: {len(target.columns)}")
    print(f"Candidates produced: {len(candidates)}")
    print()
    print(f"{'Source':<20} -> {'Target':<25} {'conf':>5}  method")
    print("-" * 100)
    matched_sources = set()
    for c in candidates:
        src_name = getattr(c, "source", "?")
        matched_sources.add(src_name)
        print(
            f"{src_name:<20} -> {c.target:<25} "
            f"{c.confidence:>5.2f}  {c.method}"
        )
    print()

    # ----- 2. DECIDE (auto policy) ------------------------------------------
    # Deterministic policy:
    #   confidence >= 0.75  → accepted
    #   confidence >= 0.50  → needs_review
    #   otherwise           → rejected
    decisions: list[MappingDecision] = []
    for c in candidates:
        if c.confidence >= 0.75:
            status = "accepted"
        elif c.confidence >= 0.50:
            status = "needs_review"
        else:
            status = "rejected"
        decisions.append(
            MappingDecision(
                source=getattr(c, "source", "?"),
                target=c.target,
                status=status,  # type: ignore[arg-type]
            )
        )

    print(f"Auto-decisions: {len(decisions)}")
    by_status: dict[str, list[MappingDecision]] = {}
    for d in decisions:
        by_status.setdefault(d.status, []).append(d)
    for status, group in by_status.items():
        print(f"  {status:<14} {len(group)}")

    # ----- 3. REVIEW (cluster by status) ------------------------------------
    review = InMemoryReviewService()
    plan = review.build_plan_from_decisions(decisions)
    print()
    print("Review plan:")
    print(f"  {plan.queue_summary}")
    for c in plan.clusters:
        print(
            f"  - [{c.priority:<6}] {c.issue_type}: "
            f"{c.count} decision(s) — {c.focus}"
        )

    # ----- 4. PERSIST --------------------------------------------------------
    store = InMemoryDecisionStore()
    for d in decisions:
        store.append(DecisionLogEntry(
            source=d.source,
            final_target=d.target,
            final_status=d.status,
        ))
    print()
    print(f"Decision store: {len(store.list())} entries persisted")

    # ----- 5. REPORT (summary + coverage) -----------------------------------
    report = InMemoryReportService()
    summary = report.build_summary_for_decisions(decisions)
    cov = report.build_coverage(source, target, decisions)

    print()
    print("Analysis summary:")
    h = summary.overall_mapping_health
    print(
        f"  accepted={h.accepted_count}, needs_review={h.needs_review_count}, "
        f"rejected={h.rejected_count}, unmatched={h.unmatched_count}"
    )
    print(
        f"  high={h.high_confidence_count}, medium={h.medium_confidence_count}, "
        f"low={h.low_confidence_count}, risk={h.overall_risk}"
    )
    print()
    print("Coverage:")
    print(
        f"  source: {cov['matched_sources']}/{cov['source_columns']} "
        f"({cov['source_coverage']:.0%})"
    )
    print(
        f"  target: {cov['matched_targets']}/{cov['target_columns']} "
        f"({cov['target_coverage']:.0%})"
    )
    print(f"  overall: {cov['overall_coverage']:.0%}")
    if cov["unmatched_sources"]:
        print(f"  unmatched sources: {', '.join(cov['unmatched_sources'])}")
    if cov["unmatched_targets"]:
        print(f"  unmatched targets: {', '.join(cov['unmatched_targets'])}")

    print()
    print("=" * 100)
    print("Full pipeline ran end-to-end with no LLM, no backend, no I/O.")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
