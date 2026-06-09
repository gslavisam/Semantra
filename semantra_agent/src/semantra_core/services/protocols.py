"""Abstract service protocols for the Semantra core SDK.

These protocols define the minimal contract that any implementation of the
Semantra core services must satisfy. They enable external systems (e.g. agents
built with LangGraph, CrewAI, or custom orchestrators) to interact with
Semantra without coupling to the concrete FastAPI/Streamlit backend.
"""

from __future__ import annotations

from typing import Any, Protocol, List, Optional, runtime_checkable

# Import the public data models from the core package.
from ..models.schema import DatasetHandle, SchemaProfile
from ..models.mapping import (
    CandidateOption,
    DecisionLogEntry,
    MappingAnalysisRequest,
    MappingAnalysisSummaryResponse,
    MappingDecision,
    ReviewPlanRequest,
    ReviewPlanResponse,
    ScoringSignals,
)
from ..models.knowledge import CanonicalGlossaryEntry, KnowledgeOverlayEntry


@runtime_checkable
class MappingEngine(Protocol):
    """Contract for any component that can score and propose source-to-target mappings."""

    def map_source_to_target(
        self, source: DatasetHandle, target: SchemaProfile
    ) -> List[CandidateOption]:
        """Return ranked candidate target options for the given source dataset."""
        ...

    def get_scoring_signals(self) -> ScoringSignals:
        """Return the default or currently active scoring signal profile."""
        ...


@runtime_checkable
class KnowledgeBase(Protocol):
    """Contract for the canonical concept and knowledge overlay runtime."""

    def get_canonical_concept(self, concept_id: str) -> Optional[CanonicalGlossaryEntry]:
        """Look up a canonical concept by its stable identifier."""
        ...

    def search_concepts(self, query: str, limit: int = 10) -> List[CanonicalGlossaryEntry]:
        """Search canonical concepts by free-text query."""
        ...

    def get_active_overlay_entries(self) -> List[KnowledgeOverlayEntry]:
        """Return all entries from the currently active knowledge overlay, if any."""
        ...


@runtime_checkable
class LLMService(Protocol):
    """Contract for bounded LLM interactions used for validation and refinement."""

    def validate_mapping(
        self,
        source_field: str,
        candidate_targets: List[str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Ask the LLM to choose the best target from a closed candidate set."""
        ...

    def generate_transformation(
        self,
        mapping_decision: MappingDecision,
        context: dict[str, Any],
    ) -> str:
        """Produce starter transformation code (Pandas/PySpark/dbt) for an accepted mapping."""
        ...


@runtime_checkable
class AsyncLLMService(Protocol):
    """Async counterpart to :class:`LLMService`.

    The two LLM-bound calls (``validate_mapping`` and
    ``generate_transformation``) are I/O-heavy (network round-trip to
    OpenAI / Anthropic). When a backend is available, exposing them
    asynchronously lets the agent pipeline run batch operations in
    parallel and lets FastAPI keep its event loop responsive while
    a request is in flight.

    The ``LLMService`` Protocol is unchanged — in-memory
    implementations (``BoundedLLMService``) have no I/O and stay
    synchronous. Implementations that talk to a real LLM backend
    should implement BOTH protocols (sync and async); the agent
    runtime can then choose based on the context.
    """

    async def avalidate_mapping(
        self,
        source_field: str,
        candidate_targets: List[str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Async version of :meth:`LLMService.validate_mapping`."""
        ...

    async def agenerate_transformation(
        self,
        mapping_decision: MappingDecision,
        context: dict[str, Any],
    ) -> str:
        """Async version of :meth:`LLMService.generate_transformation`."""
        ...


@runtime_checkable
class Connector(Protocol):
    """Contract for data source connectors (CSV, SQL, SAP, QAD, generic HTTP, etc.)."""

    def fetch_schema(self) -> SchemaProfile:
        """Return the schema profile of the underlying data source."""
        ...

    def fetch_preview(self, limit: int = 100) -> DatasetHandle:
        """Return a dataset handle with up to `limit` preview rows."""
        ...


@runtime_checkable
class AsyncMappingEngine(Protocol):
    """Async contract for a component that can score and propose source-to-target mappings."""

    async def map_source_to_target(
        self, source: DatasetHandle, target: SchemaProfile
    ) -> list[CandidateOption]:
        """Return ranked candidate target options for the given source dataset asynchronously."""
        ...


@runtime_checkable
class AsyncConnector(Protocol):
    """Async contract for data source connectors that support non-blocking schema and preview fetch."""

    async def fetch_schema(self) -> SchemaProfile:
        """Return the schema profile of the underlying data source."""
        ...

    async def fetch_preview(self, limit: int = 100) -> DatasetHandle:
        """Return a dataset handle with up to `limit` preview rows."""
        ...


# ---------------------------------------------------------------------------
# Pipeline services — these are the three "downstream" protocols that turn a
# set of ``MappingDecision`` objects into review, persistence, and reporting.
# They are all DETERMINISTIC (no LLM) so the agent pipeline can run
# end-to-end without pausing for human review.
#
# The only LLM-bound calls live in ``LLMService`` (closed-set ``validate_mapping``
# and advisory ``generate_transformation``) — bounded by design.
# ---------------------------------------------------------------------------


@runtime_checkable
class ReviewService(Protocol):
    """Automated review of a batch of ``MappingDecision`` objects.

    Returns a ``ReviewPlanResponse`` that groups decisions by suggested
    follow-up theme, priority, and risk. Deterministic — does NOT call an
    LLM. The agent uses this to decide what still needs attention
    (medium / low confidence) versus what can be auto-accepted.
    """

    def build_plan(
        self, request: ReviewPlanRequest
    ) -> ReviewPlanResponse:
        """Cluster the given decisions into a review plan.

        The returned plan carries:
        - ``queue_summary``: one-line natural-language overview
        - ``clusters``: groups of related decisions
        - ``risks``: list of risk notes
        - ``next_actions``: suggested follow-ups
        - ``generation_metadata``: how the plan was produced (always
          ``fallback`` / deterministic here; the backend adapter can
          override with ``llm`` when an LLM actually planned it)
        """
        ...


@runtime_checkable
class DecisionStore(Protocol):
    """Append-only store for accepted/rejected mapping decisions.

    The store is intentionally simple — ``append`` / ``list`` / ``clear``
    — so it can be backed by anything: in-memory list, SQLite table,
    a remote log, or a test double. No query language; the agent
    iterates ``list()`` and filters in Python.
    """

    def append(self, entry: DecisionLogEntry) -> None:
        """Persist a single decision log entry."""
        ...

    def list(self) -> List[DecisionLogEntry]:
        """Return all entries currently in the store, in insertion order."""
        ...

    def clear(self) -> None:
        """Remove all entries. Used by the agent to start a fresh run."""
        ...


@runtime_checkable
class ReportService(Protocol):
    """Deterministic mapping-analysis summary for an accepted decision set.

    Produces a ``MappingAnalysisSummaryResponse`` (health, confidence
    distribution, unmatched sources, strongest match, transformation
    hotspots, canonical coverage) and an LLM-free coverage report.
    Audio / spoken narration is *not* part of this contract — that
    flows through ``LLMService`` if/when desired.
    """

    def build_summary(
        self, request: MappingAnalysisRequest
    ) -> MappingAnalysisSummaryResponse:
        """Compute the deterministic analysis summary for a set of decisions.

        ``request.decisions`` is the input; the returned response carries
        the full set of derived metrics.
        """
        ...

    def build_summary_for_decisions(
        self, decisions: List[MappingDecision]
    ) -> MappingAnalysisSummaryResponse:
        """Convenience: derive a summary directly from a list of decisions.

        The agent pipeline produces ``MappingDecision`` objects as it
        goes; rather than forcing the agent to construct an
        ``AutoMappingResponse`` + ``MappingAnalysisRequest`` by hand,
        this method wraps the decisions with status-derived confidence
        values and calls :meth:`build_summary` internally.

        Status mapping (deterministic):

        - ``accepted`` → confidence 0.95, ``high_confidence``
        - ``rejected`` → confidence 0.05, ``low_confidence``
        - ``needs_review`` → confidence 0.5,  ``medium_confidence``
        """
        ...

    def build_coverage(
        self,
        source: DatasetHandle,
        target: SchemaProfile,
        decisions: List[MappingDecision],
    ) -> dict[str, Any]:
        """Return a flat coverage dict::

            {
                "source_columns": int,
                "target_columns": int,
                "matched_sources": int,
                "matched_targets": int,
                "matched_pairs": int,
                "source_coverage": float,   # 0.0–1.0
                "target_coverage": float,   # 0.0–1.0
                "overall_coverage": float,  # 0.0–1.0
                "unmatched_sources": list[str],
                "unmatched_targets": list[str],
            }

        Useful for the agent's final "what got mapped / what didn't" report.
        """
        ...
