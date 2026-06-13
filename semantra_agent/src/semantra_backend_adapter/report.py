"""Backend adapter for the `ReportService` protocol.

Wraps `backend.app.services.mapping_analysis_service.build_mapping_analysis_summary`
and adapts it to the SDK's `ReportService.build_summary` / `build_summary_for_decisions`
/ `build_coverage`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from semantra_core.models.mapping import (
    AutoMappingResponse,
    MappingAnalysisOptions,
    MappingAnalysisRequest,
    MappingAnalysisSummaryResponse,
    MappingAnalysisWorkspaceContext,
    MappingCandidate,
    MappingDecision,
    ScoringSignals,
)
from semantra_core.models.schema import DatasetHandle, SchemaProfile
from semantra_core.services.implementations import InMemoryReportService

from .context import BackendContext


class BackendReportService:
    """Concrete `ReportService` backed by the Semantra FastAPI backend.

    If the backend package is not importable, falls back to the in-memory
    stub so the adapter is still usable for tests and demos.
    """

    def __init__(self, context: BackendContext | None = None) -> None:
        self.context = context
        self._backend_build = None
        self._fallback = InMemoryReportService()
        self._backend_available = False
        try:
            from backend.app.services import mapping_analysis_service  # type: ignore

            self._backend_build = mapping_analysis_service.build_mapping_analysis_summary
            self._backend_available = True
        except Exception:  # noqa: BLE001
            self._backend_available = False

    def build_summary(
        self, request: MappingAnalysisRequest
    ) -> MappingAnalysisSummaryResponse:
        if not self._backend_available or self._backend_build is None:
            return self._fallback.build_summary(request)
        return self._backend_build(request)

    def build_summary_for_decisions(
        self, decisions: List[MappingDecision]
    ) -> MappingAnalysisSummaryResponse:
        # Try backend first.
        if self._backend_available and self._backend_build is not None:
            mappings: List[MappingCandidate] = []
            for d in decisions:
                if d.status == "accepted":
                    conf, label = 0.95, "high_confidence"
                elif d.status == "rejected":
                    conf, label = 0.05, "low_confidence"
                else:
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
                    )
                )
            response = AutoMappingResponse(ranked_mappings=[], mappings=mappings)
            request = MappingAnalysisRequest(
                mapping_response=response,
                workspace=MappingAnalysisWorkspaceContext(),
                options=MappingAnalysisOptions(),
            )
            return self._backend_build(request)

        return self._fallback.build_summary_for_decisions(decisions)

    def build_coverage(
        self,
        source: DatasetHandle,
        target: SchemaProfile,
        decisions: List[MappingDecision],
    ) -> Dict[str, Any]:
        # Coverage is deterministic — always use the in-memory implementation.
        return self._fallback.build_coverage(source, target, decisions)
