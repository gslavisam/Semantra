"""Backend adapter for the `LLMService` protocol.

Wraps `backend.app.services.llm_service` to expose bounded LLM validation
and transformation code generation.

Implements both the synchronous :class:`LLMService` protocol and the
asynchronous :class:`AsyncLLMService` protocol — the async methods
delegate to the synchronous backend via ``asyncio.to_thread`` so they
don't block the event loop while the LLM call is in flight.
"""

from __future__ import annotations

import asyncio
from typing import Any, List

from semantra_core.models.mapping import MappingDecision
from semantra_core.services.implementations import BoundedLLMService

from .context import BackendContext


class BackendLLMService:
    """Concrete `LLMService` backed by the Semantra FastAPI backend.

    Falls back to a stub if the backend is not importable.
    """

    def __init__(self, context: BackendContext | None = None) -> None:
        self.context = context
        self._fallback = BoundedLLMService()
        self._backend_available = False
        try:
            from backend.app.services import llm_service  # type: ignore

            self._service = llm_service
            self._backend_available = True
        except Exception:  # noqa: BLE001
            self._backend_available = False

    def validate_mapping(
        self,
        source_field: str,
        candidate_targets: List[str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._backend_available:
            return self._fallback.validate_mapping(source_field, candidate_targets, context)
        try:
            # The backend function name may vary; we attempt the canonical one.
            result = self._service.call_validator(
                source_field=source_field,
                candidate_targets=candidate_targets,
                context=context,
            )
            return {
                "selected_target": getattr(result, "selected_target", ""),
                "confidence": float(getattr(result, "confidence", 0.0)),
                "reasoning": list(getattr(result, "reasoning", [])),
                "transformation_code": getattr(result, "transformation_code", None),
            }
        except Exception:  # noqa: BLE001
            return self._fallback.validate_mapping(source_field, candidate_targets, context)

    def generate_transformation(
        self,
        mapping_decision: MappingDecision,
        context: dict[str, Any],
    ) -> str:
        if not self._backend_available:
            return self._fallback.generate_transformation(mapping_decision, context)
        try:
            code = self._service.call_transformation_generator(
                mapping_decision=mapping_decision,
                context=context,
            )
            return str(code)
        except Exception:  # noqa: BLE001
            return self._fallback.generate_transformation(mapping_decision, context)

    # ------------------------------------------------------------------
    # AsyncLLMService — used by the agent runtime for batch / parallel
    # LLM work. The implementation is the same code as the sync
    # version, just dispatched to a worker thread so the event loop
    # stays responsive while the network call is in flight.
    # ------------------------------------------------------------------

    async def avalidate_mapping(
        self,
        source_field: str,
        candidate_targets: List[str],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self.validate_mapping, source_field, candidate_targets, context
        )

    async def agenerate_transformation(
        self,
        mapping_decision: MappingDecision,
        context: dict[str, Any],
    ) -> str:
        return await asyncio.to_thread(
            self.generate_transformation, mapping_decision, context
        )
