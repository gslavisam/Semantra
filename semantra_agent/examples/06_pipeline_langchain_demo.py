"""Pipeline demo: end-to-end agent mapping pipeline with LangChain tools.

This example runs the full Semantra agent pipeline:

  1. **Map** — propose candidates for source → target
  2. **Review** — build a review plan from mapping decisions
  3. **Decide** — auto-accept/reject based on confidence thresholds
  4. **Store** — persist the decisions to a decision store
  5. **Report** — generate a mapping summary + coverage report

All steps use the in-memory reference implementations; no backend,
no LLM, no I/O. The full pipeline is also exposed as LangChain tools
via ``build_semantra_tools()`` so an LLM agent could orchestrate the
same steps if desired.

Usage:
    python examples/06_pipeline_langchain_demo.py
"""

from __future__ import annotations

from semantra_core.models.schema import DatasetHandle, SchemaProfile, ColumnProfile
from semantra_core.models.mapping import MappingDecision, DecisionLogEntry
from semantra_core.services.implementations import (
    InMemoryMappingEngine,
    InMemoryKnowledgeBase,
    InMemoryReviewService,
    InMemoryDecisionStore,
    InMemoryReportService,
)
from semantra_agent.langchain_tools import build_semantra_tools


def build_sample_data():
    """Build a realistic source/target pair with overlapping and unique columns."""
    source = DatasetHandle(
        dataset_id="src_erp",
        dataset_name="erp_customer_export",
        schema_profile=SchemaProfile(
            dataset_id="src_erp",
            dataset_name="erp_customer_export",
            row_count=5000,
            columns=[
                ColumnProfile(
                    name="cust_id", normalized_name="cust_id", dtype="str",
                    null_ratio=0.0, unique_ratio=1.0, non_null_count=5000,
                ),
                ColumnProfile(
                    name="cust_name", normalized_name="cust_name", dtype="str",
                    null_ratio=0.01, unique_ratio=0.98, non_null_count=4950,
                ),
                ColumnProfile(
                    name="email_addr", normalized_name="email_addr", dtype="str",
                    null_ratio=0.05, unique_ratio=0.96, non_null_count=4750,
                ),
                ColumnProfile(
                    name="country_code", normalized_name="country_code", dtype="str",
                    null_ratio=0.02, unique_ratio=0.15, non_null_count=4900,
                ),
                ColumnProfile(
                    name="internal_ref", normalized_name="internal_ref", dtype="str",
                    null_ratio=0.10, unique_ratio=0.85, non_null_count=4500,
                ),
            ],
        ),
    )
    target = SchemaProfile(
        dataset_id="tgt_crm",
        dataset_name="crm_contacts",
        row_count=8000,
        columns=[
            ColumnProfile(
                name="customer_key", normalized_name="customer_key", dtype="str",
                null_ratio=0.0, unique_ratio=1.0, non_null_count=8000,
            ),
            ColumnProfile(
                name="customer_name", normalized_name="customer_name", dtype="str",
                null_ratio=0.01, unique_ratio=0.95, non_null_count=7920,
            ),
            ColumnProfile(
                name="email_address", normalized_name="email_address", dtype="str",
                null_ratio=0.03, unique_ratio=0.94, non_null_count=7760,
            ),
            ColumnProfile(
                name="region", normalized_name="region", dtype="str",
                null_ratio=0.05, unique_ratio=0.4, non_null_count=7600,
            ),
            ColumnProfile(
                name="phone", normalized_name="phone", dtype="str",
                null_ratio=0.20, unique_ratio=0.7, non_null_count=6400,
            ),
        ],
    )
    return source, target


# ---------------------------------------------------------------------------
# Step 1: Build services
# ---------------------------------------------------------------------------
print("=" * 70)
print("SEMANTRA AGENT — FULL PIPELINE DEMO")
print("=" * 70)

engine = InMemoryMappingEngine()
knowledge = InMemoryKnowledgeBase()
review = InMemoryReviewService()
store = InMemoryDecisionStore()
report = InMemoryReportService()

source, target = build_sample_data()

# Build LangChain tools for all services
tools = build_semantra_tools(
    engine=engine,
    knowledge=knowledge,
    review_service=review,
    decision_store=store,
    report_service=report,
)

print(f"\n{len(tools)} LangChain tools loaded:")
for t in tools:
    print(f"  • {t.name}")

# ---------------------------------------------------------------------------
# Step 2: MAP — propose candidates
# ---------------------------------------------------------------------------
print(f"\n{'─' * 70}")
print("STEP 1: MAP — propose candidate targets for each source column")
print(f"{'─' * 70}")

candidates = engine.map_source_to_target(source, target)
print(f"Source: {source.dataset_name} ({len(source.schema_profile.columns)} columns)")
print(f"Target: {target.dataset_name} ({len(target.columns)} columns)")
print(f"\nCandidates found: {len(candidates)}")

# Show raw candidate output
for c in candidates:
    source_name = getattr(c, "source", "unknown")
    print(
        f"  {source_name} → {c.target} "
        f"({c.method}, confidence={c.confidence:.2f}, {c.confidence_label})"
    )

# ---------------------------------------------------------------------------
# Step 3: REVIEW — build review plan from auto-decisions
# ---------------------------------------------------------------------------
print(f"\n{'─' * 70}")
print("STEP 2: DECIDE + REVIEW — auto-accept/reject, then build review plan")
print(f"{'─' * 70}")

# Auto-decision policy: high_confidence → accepted, medium → needs_review,
# low → rejected. For this demo we use name-match confidence.
decisions: list[MappingDecision] = []
for c in candidates:
    source_name = getattr(c, "source", "unknown")
    if c.confidence >= 0.8:
        status = "accepted"
    elif c.confidence >= 0.5:
        status = "needs_review"
    else:
        status = "rejected"
    decisions.append(
        MappingDecision(
            source=source_name,
            target=c.target,
            status=status,  # type: ignore[arg-type]
        )
    )

accepted = sum(1 for d in decisions if d.status == "accepted")
review_needed = sum(1 for d in decisions if d.status == "needs_review")
rejected = sum(1 for d in decisions if d.status == "rejected")
print(
    f"Auto-decisions: {accepted} accepted, {review_needed} needs review, "
    f"{rejected} rejected"
)

# Build review plan
plan = review.build_plan_from_decisions(decisions)
print(f"\nReview Plan: {plan.queue_summary}")
print(f"  Title: {plan.title}")
for cluster in plan.clusters:
    print(f"  Cluster: {cluster.issue_type} ({cluster.priority}, {cluster.count} items)")
    print(f"    Focus: {cluster.focus}")
    print(f"    Action: {cluster.recommended_follow_up}")
if plan.risks:
    print(f"\n  Risks:")
    for r in plan.risks:
        print(f"    ⚠ {r}")
if plan.next_actions:
    print(f"\n  Next actions:")
    for a in plan.next_actions:
        print(f"    → {a}")

# ---------------------------------------------------------------------------
# Step 4: STORE — persist decisions
# ---------------------------------------------------------------------------
print(f"\n{'─' * 70}")
print("STEP 3: STORE — persist mapping decisions")
print(f"{'─' * 70}")

for d in decisions:
    store.append(
        DecisionLogEntry(
            source=d.source,
            final_target=d.target,
            final_status=d.status,  # type: ignore[arg-type]
        )
    )

all_entries = store.list()
print(f"Persisted {len(all_entries)} decision log entries:")
for e in all_entries:
    print(f"  {e.source} → {e.final_target} [{e.final_status}]")

# ---------------------------------------------------------------------------
# Step 5: REPORT — build summary + coverage
# ---------------------------------------------------------------------------
print(f"\n{'─' * 70}")
print("STEP 4: REPORT — mapping summary + coverage")
print(f"{'─' * 70}")

summary = report.build_summary_for_decisions(decisions)
health = summary.overall_mapping_health
dist = summary.confidence_distribution

print(f"Mapping Analysis: {summary.title}")
print(f"  Overall risk: {health.overall_risk}")
print(
    f"  Accepted: {health.accepted_count} | "
    f"Needs review: {health.needs_review_count} | "
    f"Rejected: {health.rejected_count}"
)
print(
    f"  Confidence: {dist.high_confidence_count} high "
    f"({dist.high_confidence_ratio:.0%}), "
    f"{dist.medium_confidence_count} medium, {dist.low_confidence_count} low"
)

if summary.implementation_risks:
    print(f"\n  Risks:")
    for r in summary.implementation_risks:
        print(f"    ⚠ {r}")

# Coverage report
cov = report.build_coverage(source, target, decisions)
print(f"\n  Coverage Report:")
print(f"    Source columns: {cov['source_columns']} (matched: {cov['matched_sources']})")
print(f"    Target columns: {cov['target_columns']} (matched: {cov['matched_targets']})")
print(f"    Source coverage: {cov['source_coverage']:.0%}")
print(f"    Target coverage: {cov['target_coverage']:.0%}")
print(f"    Overall coverage: {cov['overall_coverage']:.0%}")
if cov["unmatched_sources"]:
    print(f"    Unmatched sources: {', '.join(cov['unmatched_sources'])}")
if cov["unmatched_targets"]:
    print(f"    Unmatched targets: {', '.join(cov['unmatched_targets'])}")

# ---------------------------------------------------------------------------
# Verdict
# ---------------------------------------------------------------------------
print(f"\n{'=' * 70}")
print("PIPELINE COMPLETE!")
print(
    f"  {len(candidates)} candidates → "
    f"{accepted} accepted, {review_needed} needs review, {rejected} rejected"
)
print(f"  Coverage: {cov['overall_coverage']:.0%} overall")
print(f"  Risk: {health.overall_risk}")
print("=" * 70)
