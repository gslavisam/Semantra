"""Reference stub implementations of the Semantra core service protocols.

These implementations are intentionally minimal. They serve as:
- A starting point for unit tests of agent workflows.
- A working example of how to satisfy the `protocols` contracts.
- A safe default for development environments where the full backend is not available.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from ..models.schema import DatasetHandle, SchemaProfile
from ..models.mapping import (
    AutoMappingResponse,
    CandidateOption,
    DecisionLogEntry,
    MappingAnalysisCanonicalCoverageSummary,
    MappingAnalysisConfidenceDistribution,
    MappingAnalysisGenerationMetadata,
    MappingAnalysisOptions,
    MappingAnalysisOverallMappingHealth,
    MappingAnalysisRequest,
    MappingAnalysisSummaryResponse,
    MappingAnalysisWorkspaceContext,
    MappingCandidate,
    MappingDecision,
    ReviewPlanCluster,
    ReviewPlanGenerationMetadata,
    ReviewPlanRequest,
    ReviewPlanResponse,
    ScoringSignals,
)
from ..models.knowledge import CanonicalGlossaryEntry, KnowledgeOverlayEntry
from .protocols import (
    Connector,
    DecisionStore,
    KnowledgeBase,
    LLMService,
    MappingEngine,
    ReportService,
    ReviewService,
)


class InMemoryMappingEngine:
    """Reference stub with trivial name-based matching.

    Useful as a working default for:
    - Unit tests of agent workflows
    - Demos that want non-trivial mapping output without a real backend
    - Local development before a real engine is wired up

    Matching strategy (deterministic, in priority order):
    1. Case-insensitive **exact equality** → confidence 1.0
    2. Case-insensitive **substring** (either direction) → confidence 0.7

    Each source column with at least one match produces ONE
    ``CandidateOption`` pointing at the best target column. The source
    field name is attached as a ``source`` attribute (mirroring the
    convention used by the backend adapter) so callers can group
    results by source field.

    NOTE: This is a STUB. It exists so the SDK demo path and unit tests
    can produce visible output without a real backend. Real production
    matching should use ``BackendMappingEngine`` (which delegates to
    the Semantra FastAPI backend) or a custom engine implementation.
    """

    def map_source_to_target(
        self, source: DatasetHandle, target: SchemaProfile
    ) -> List[CandidateOption]:
        candidates: List[CandidateOption] = []
        for source_col in source.schema_profile.columns:
            source_name = source_col.name
            source_lower = source_name.lower()

            # (confidence, target_name, method) — first match wins
            # because exact match breaks the inner loop.
            best: Optional[tuple[float, str, str]] = None

            for target_col in target.columns:
                target_name = target_col.name
                target_lower = target_name.lower()

                if source_lower == target_lower:
                    # Exact match — beats any substring match.
                    best = (1.0, target_name, "in_memory_name_match")
                    break

                if source_lower in target_lower or target_lower in source_lower:
                    conf = 0.7
                    if best is None or conf > best[0]:
                        best = (conf, target_name, "in_memory_substring_match")

            if best is None:
                continue

            conf, target_name, method = best
            cand = CandidateOption(
                target=target_name,
                confidence=conf,
                confidence_label=(
                    "high_confidence" if conf >= 0.8 else "medium_confidence"
                ),
                method=method,
                signals=ScoringSignals(name=conf),
                explanation=[f"name match: {source_name!r} ↔ {target_name!r}"],
            )
            # Attach source field name so callers can group by source.
            # ``object.__setattr__`` bypasses Pydantic's frozen model check.
            try:
                object.__setattr__(cand, "source", source_name)
            except Exception:  # noqa: BLE001
                pass
            candidates.append(cand)

        return candidates

    def get_scoring_signals(self) -> ScoringSignals:
        return ScoringSignals()


class InMemoryKnowledgeBase:
    """Stub knowledge base that holds concepts in memory. No persistence."""

    def __init__(self) -> None:
        self._concepts: dict[str, CanonicalGlossaryEntry] = {}

    def add(self, concept: CanonicalGlossaryEntry) -> None:
        self._concepts[concept.concept_id] = concept

    def get_canonical_concept(self, concept_id: str) -> Optional[CanonicalGlossaryEntry]:
        return self._concepts.get(concept_id)

    def search_concepts(self, query: str, limit: int = 10) -> List[CanonicalGlossaryEntry]:
        q = query.lower()
        return [c for c in self._concepts.values() if q in c.display_name.lower()][:limit]

    def get_active_overlay_entries(self) -> List[KnowledgeOverlayEntry]:
        return []


class BoundedLLMService:
    """LLM service stub that echoes the input. Replace with a real provider in production."""

    def validate_mapping(
        self,
        source_field: str,
        candidate_targets: List[str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "selected_target": candidate_targets[0] if candidate_targets else "",
            "confidence": 0.0,
            "reasoning": ["LLM service not configured; using stub."],
        }

    def generate_transformation(
        self,
        mapping_decision: MappingDecision,
        context: dict[str, Any],
    ) -> str:
        return "# transformation generation disabled in stub LLM service"


class StaticConnector:
    """Connector stub that returns a fixed schema. Useful for examples and tests."""

    def __init__(self, schema: SchemaProfile) -> None:
        self._schema = schema

    def fetch_schema(self) -> SchemaProfile:
        return self._schema

    def fetch_preview(self, limit: int = 100) -> DatasetHandle:
        return DatasetHandle(
            dataset_id=self._schema.dataset_id,
            dataset_name=self._schema.dataset_name,
            schema_profile=self._schema,
            preview_rows=[],
        )


# Note: These classes structurally satisfy the Protocol definitions in
# `protocols.py`. The `@runtime_checkable` decorator on each Protocol allows
# `isinstance()` checks, and structural duck-typing handles the rest.


# ---------------------------------------------------------------------------
# Pipeline services: ReviewService, DecisionStore, ReportService
#
# These three services turn a list of ``MappingDecision`` objects into
# (a) a review plan, (b) persistent decisions, and (c) a coverage /
# analysis summary. They are all deterministic — no LLM, no I/O — so the
# agent pipeline runs end-to-end without pausing.
# ---------------------------------------------------------------------------


class InMemoryReviewService:
    """Deterministic review plan over a batch of ``MappingDecision`` objects.

    Grouping strategy: clusters are produced by ``status`` (one cluster
    per status), priority is assigned by status severity:

      - ``rejected``      → high priority (something was actively dropped)
      - ``needs_review``  → medium priority (pending human/agent attention)
      - ``accepted``      → low priority (informational — already done)

    This is intentionally simple. The backend adapter can replace it
    with the real ``review_plan_service.build_review_plan`` which uses
    LLM-assisted clustering — but for the agent pipeline we don't want
    a pause.
    """

    def build_plan(
        self, request: ReviewPlanRequest
    ) -> ReviewPlanResponse:
        """Build a review plan from the request's filtered rows (dict shape).

        This is the strict-protocol entry point used by the backend
        adapter; the agent pipeline prefers :meth:`build_plan_from_decisions`
        because it accepts the SDK's Pydantic model directly.
        """
        # The InMemory variant looks at the row dicts the same way the
        # real backend does: by issue type / status / count.
        # For the in-memory stub we just emit a single "auto-clustered"
        # cluster from the row count so callers still get a useful plan.
        n = len(request.filtered_rows)
        if n == 0:
            return ReviewPlanResponse(
                title="Review plan",
                queue_summary="No items to review.",
                clusters=[],
                risks=[],
                next_actions=[],
                generation_metadata=ReviewPlanGenerationMetadata(
                    used_llm=False, fallback_used=True
                ),
            )
        cluster = ReviewPlanCluster(
            issue_type="auto_review",
            focus="filtered_rows",
            canonical_status="",
            priority="medium",
            count=n,
            source_examples=[
                str(row.get("source", ""))
                for row in request.filtered_rows[:3]
            ],
            summary=f"{n} items selected by the current filter set.",
            recommended_follow_up=(
                "Inspect the auto-clustered items; promote high-confidence "
                "matches and reject the rest."
            ),
        )
        return ReviewPlanResponse(
            title="Review plan (in-memory)",
            queue_summary=f"{n} items require automated review.",
            clusters=[cluster],
            risks=[],
            next_actions=[
                "Run the agent pipeline to auto-accept / auto-reject."
            ],
            generation_metadata=ReviewPlanGenerationMetadata(
                used_llm=False, fallback_used=True
            ),
        )

    def build_plan_from_decisions(
        self, decisions: List[MappingDecision]
    ) -> ReviewPlanResponse:
        """Agent-friendly entry point: build the plan directly from
        ``MappingDecision`` objects (no dict wrapping required)."""
        if not decisions:
            return ReviewPlanResponse(
                title="Review plan",
                queue_summary="No decisions to review.",
                clusters=[],
                risks=[],
                next_actions=[],
                generation_metadata=ReviewPlanGenerationMetadata(
                    used_llm=False, fallback_used=True
                ),
            )

        # Group by status; assign priority by severity.
        priority_by_status: Dict[str, str] = {
            "rejected": "high",
            "needs_review": "medium",
            "accepted": "low",
        }
        by_status: Dict[str, List[MappingDecision]] = {}
        for d in decisions:
            by_status.setdefault(d.status, []).append(d)

        clusters: List[ReviewPlanCluster] = []
        for status, group in by_status.items():
            priority = priority_by_status.get(status, "medium")
            clusters.append(
                ReviewPlanCluster(
                    issue_type=f"status_{status}",
                    focus=f"{len(group)} decision(s) with status={status!r}",
                    canonical_status="",
                    priority=priority,  # type: ignore[arg-type]
                    count=len(group),
                    source_examples=[d.source for d in group[:3]],
                    summary=(
                        f"{len(group)} decision(s) in status {status!r}: "
                        f"{', '.join(d.source for d in group[:3])}"
                        + ("…" if len(group) > 3 else "")
                    ),
                    recommended_follow_up=(
                        "No action required — already auto-decided."
                        if status == "accepted"
                        else f"Review the {len(group)} {status} item(s) "
                        "before promoting them to the next stage."
                    ),
                )
            )

        # Stable order: high → medium → low priority.
        order = {"high": 0, "medium": 1, "low": 2}
        clusters.sort(key=lambda c: order.get(c.priority, 99))

        # Build risks and next_actions.
        risks: List[str] = []
        next_actions: List[str] = []
        for c in clusters:
            if c.priority in {"high", "medium"} and c.count:
                risks.append(
                    f"{c.count} decision(s) in {c.focus} still need attention."
                )
                next_actions.append(c.recommended_follow_up)

        accepted = sum(1 for d in decisions if d.status == "accepted")
        rejected = sum(1 for d in decisions if d.status == "rejected")
        review = sum(1 for d in decisions if d.status == "needs_review")

        return ReviewPlanResponse(
            title="Automated review plan",
            queue_summary=(
                f"{accepted} accepted, {rejected} rejected, "
                f"{review} still need review."
            ),
            clusters=clusters,
            risks=risks,
            next_actions=next_actions,
            generation_metadata=ReviewPlanGenerationMetadata(
                used_llm=False, fallback_used=True
            ),
        )


class InMemoryDecisionStore:
    """In-memory append-only decision store.

    Entries are kept in insertion order in a plain list. No query
    language; iterate ``list()`` and filter in Python. This is the
    canonical reference implementation of the ``DecisionStore`` Protocol
    — the backend adapter replaces it with a SQLite-backed equivalent.
    """

    def __init__(self) -> None:
        self._entries: List[DecisionLogEntry] = []

    def append(self, entry: DecisionLogEntry) -> None:
        self._entries.append(entry)

    def list(self) -> List[DecisionLogEntry]:
        # Return a copy so the caller cannot mutate the store by holding
        # a reference to the internal list.
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()


class InMemoryReportService:
    """Deterministic mapping-analysis summary + coverage report.

    No LLM is invoked. The two key methods are:

      - :meth:`build_summary`            — strict protocol: takes
        ``MappingAnalysisRequest`` (backed by ``AutoMappingResponse``).
      - :meth:`build_summary_for_decisions` — convenience for the
        agent pipeline: takes a plain list of ``MappingDecision``.
      - :meth:`build_coverage`           — flat coverage dict.

    Status → confidence mapping (deterministic, used by the agent):
        accepted      → 0.95, high_confidence
        rejected      → 0.05, low_confidence
        needs_review  → 0.5,  medium_confidence
    """

    def build_summary(
        self, request: MappingAnalysisRequest
    ) -> MappingAnalysisSummaryResponse:
        """Compute the deterministic analysis summary from a request.

        Reads ``request.mapping_response.mappings`` (the resolved
        ``MappingCandidate`` list) and derives every metric. If the
        response is empty, returns a zeroed-out summary.
        """
        mappings = list(request.mapping_response.mappings or [])
        total = len(mappings)

        # Health buckets (status).
        accepted = sum(1 for m in mappings if m.status == "accepted")
        needs_review = sum(1 for m in mappings if m.status == "needs_review")
        rejected = sum(1 for m in mappings if m.status == "rejected")
        unmatched = sum(1 for m in mappings if (m.target is None or m.target == ""))

        # Confidence buckets.
        high = sum(1 for m in mappings if m.confidence_label == "high_confidence")
        medium = sum(1 for m in mappings if m.confidence_label == "medium_confidence")
        low = sum(1 for m in mappings if m.confidence_label == "low_confidence")

        # Risk: heuristic — any rejected or unmatched, or >50% low.
        if rejected or unmatched:
            overall_risk = "high"
        elif low > total / 2:
            overall_risk = "medium"
        else:
            overall_risk = "low"

        health = MappingAnalysisOverallMappingHealth(
            summary=(
                f"{accepted} accepted, {needs_review} need review, "
                f"{rejected} rejected, {unmatched} unmatched out of {total}."
            ),
            accepted_count=accepted,
            needs_review_count=needs_review,
            rejected_count=rejected,
            unmatched_count=unmatched,
            high_confidence_count=high,
            medium_confidence_count=medium,
            low_confidence_count=low,
            overall_risk=overall_risk,  # type: ignore[arg-type]
        )

        denom = total if total else 1
        distribution = MappingAnalysisConfidenceDistribution(
            high_confidence_count=high,
            medium_confidence_count=medium,
            low_confidence_count=low,
            high_confidence_ratio=high / denom,
            medium_confidence_ratio=medium / denom,
            low_confidence_ratio=low / denom,
            interpretation=(
                f"{high}/{total} high-confidence, {medium} medium, {low} low."
            ),
        )

        # Strongest match: highest confidence, with a target.
        strongest = None
        for m in mappings:
            if m.target and (strongest is None or m.confidence > strongest.confidence):
                strongest = m

        return MappingAnalysisSummaryResponse(
            title="Automated mapping analysis",
            overall_mapping_health=health,
            confidence_distribution=distribution,
            strongest_matches=[],  # strongest is a MappingCandidate, not the nested type
            needs_review_items=[],
            unmatched_sources=[],
            canonical_coverage_summary=MappingAnalysisCanonicalCoverageSummary(),
            transformation_hotspots=[],
            implementation_risks=(
                [
                    f"{rejected} rejected mapping(s) detected."
                ] if rejected else []
            ),
            recommended_next_actions=(
                [
                    f"Inspect the {unmatched} unmatched source field(s)."
                ] if unmatched else []
            ),
            narration_script_seed="",
            generation_metadata=MappingAnalysisGenerationMetadata(
                used_llm=False, fallback_used=True
            ),
        )

    def build_summary_for_decisions(
        self, decisions: List[MappingDecision]
    ) -> MappingAnalysisSummaryResponse:
        """Wrap a list of decisions into a request and call :meth:`build_summary`.

        This is the entry point the agent pipeline uses. It maps each
        ``MappingDecision`` into a ``MappingCandidate`` with a
        status-derived confidence value, builds a synthetic
        ``AutoMappingResponse``, and delegates.
        """
        mappings: List[MappingCandidate] = []
        for d in decisions:
            if d.status == "accepted":
                conf, label = 0.95, "high_confidence"
            elif d.status == "rejected":
                conf, label = 0.05, "low_confidence"
            else:  # needs_review
                conf, label = 0.5, "medium_confidence"
            mappings.append(
                MappingCandidate(
                    source=d.source,
                    target=d.target,
                    confidence=conf,
                    confidence_label=label,  # type: ignore[arg-type]
                    status=d.status,  # type: ignore[arg-type]
                    method="auto_decision",
                    signals=ScoringSignals(name=conf),
                    explanation=[
                        f"auto-decision: status={d.status}, "
                        f"resolution_type={d.resolution_type}"
                    ],
                )
            )

        response = AutoMappingResponse(ranked_mappings=[], mappings=mappings)
        request = MappingAnalysisRequest(
            mapping_response=response,
            workspace=MappingAnalysisWorkspaceContext(),
            options=MappingAnalysisOptions(),
        )
        return self.build_summary(request)

    def build_coverage(
        self,
        source: DatasetHandle,
        target: SchemaProfile,
        decisions: List[MappingDecision],
    ) -> Dict[str, Any]:
        """Flat coverage report — useful for the agent's final summary.

        ``decisions`` is treated as the set of mapped decisions
        (both ``accepted`` and ``needs_review``). ``rejected`` items
        are excluded from coverage — they are by definition not mapped.
        """
        source_columns = list(source.schema_profile.columns)
        target_columns = list(target.columns)

        mapped = [d for d in decisions if d.status != "rejected"]
        matched_sources = {d.source for d in mapped if d.source}
        matched_targets = {d.target for d in mapped if d.target}

        unmatched_sources = [c.name for c in source_columns if c.name not in matched_sources]
        unmatched_targets = [c.name for c in target_columns if c.name not in matched_targets]

        n_source = len(source_columns) or 1
        n_target = len(target_columns) or 1
        source_coverage = len(matched_sources) / n_source
        target_coverage = len(matched_targets) / n_target
        overall = (source_coverage + target_coverage) / 2

        return {
            "source_columns": len(source_columns),
            "target_columns": len(target_columns),
            "matched_sources": len(matched_sources),
            "matched_targets": len(matched_targets),
            "matched_pairs": len(mapped),
            "source_coverage": source_coverage,
            "target_coverage": target_coverage,
            "overall_coverage": overall,
            "unmatched_sources": unmatched_sources,
            "unmatched_targets": unmatched_targets,
        }
