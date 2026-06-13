"""Backend adapter for the `ReviewService` protocol.

Wraps `backend.app.services.review_plan_service.build_review_plan` and
adapts it to the SDK's `ReviewService.build_plan` / `build_plan_from_decisions`.
"""

from __future__ import annotations

from typing import List

from semantra_core.models.mapping import (
    MappingDecision,
    ReviewPlanRequest,
    ReviewPlanResponse,
)
from semantra_core.services.implementations import InMemoryReviewService

from .context import BackendContext


class BackendReviewService:
    """Concrete `ReviewService` backed by the Semantra FastAPI backend.

    If the backend package is not importable, falls back to the in-memory
    stub so the adapter is still usable for tests and demos.
    """

    def __init__(self, context: BackendContext | None = None) -> None:
        self.context = context
        self._backend_build = None
        self._fallback = InMemoryReviewService()
        self._backend_available = False
        try:
            from backend.app.services import review_plan_service  # type: ignore

            self._backend_build = review_plan_service.build_review_plan
            self._backend_available = True
        except Exception:  # noqa: BLE001
            self._backend_available = False

    def build_plan(
        self, request: ReviewPlanRequest
    ) -> ReviewPlanResponse:
        if not self._backend_available or self._backend_build is None:
            return self._fallback.build_plan(request)
        return self._backend_build(request)

    def build_plan_from_decisions(
        self, decisions: List[MappingDecision]
    ) -> ReviewPlanResponse:
        """Agent-friendly entry point: build the plan directly from decisions."""
        if not decisions:
            return self._fallback.build_plan_from_decisions(decisions)

        # Try backend first — it may have LLM-assisted clustering.
        if self._backend_available and self._backend_build is not None:
            rows: list[dict] = [
                {
                    "source": d.source,
                    "target": d.target,
                    "status": d.status,
                }
                for d in decisions
            ]
            request = ReviewPlanRequest(filtered_rows=rows)
            return self._backend_build(request)

        return self._fallback.build_plan_from_decisions(decisions)
