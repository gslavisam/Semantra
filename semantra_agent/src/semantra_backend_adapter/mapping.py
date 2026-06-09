"""Backend adapter for the `MappingEngine` protocol.

Wraps `backend.app.services.mapping_service.generate_mapping_candidates` and
adapts its return value (`AutoMappingResponse`) to the SDK's
`list[CandidateOption]`.
"""

from __future__ import annotations

import asyncio
from typing import List

from semantra_core.models.schema import DatasetHandle, SchemaProfile
from semantra_core.models.mapping import CandidateOption, ScoringSignals
from semantra_core.services.implementations import InMemoryMappingEngine

from .context import BackendContext


class BackendMappingEngine:
    """Concrete `MappingEngine` backed by the Semantra FastAPI backend.

    If the backend package is not importable, falls back to the in-memory
    stub so the adapter is still usable for tests and demos.
    """

    def __init__(self, context: BackendContext | None = None) -> None:
        self.context = context
        self._backend_generate = None
        self._fallback = InMemoryMappingEngine()
        self._backend_available = False
        try:
            from backend.app.services import mapping_service  # type: ignore

            self._backend_generate = mapping_service.generate_mapping_candidates
            self._backend_available = True
        except Exception:  # noqa: BLE001
            # Backend not importable; we will use the fallback.
            self._backend_available = False

    def map_source_to_target(
        self, source: DatasetHandle, target: SchemaProfile
    ) -> List[CandidateOption]:
        if not self._backend_available or self._backend_generate is None:
            return self._fallback.map_source_to_target(source, target)

        # The backend function takes SchemaProfile for both source and target.
        source_schema = source.schema_profile
        # The SDK is called from agents / notebooks, NOT from the user-facing
        # review UI. We never want to silently persist a decision log entry
        # from a programmatic SDK call — that is the review UI's job.
        response = self._backend_generate(
            source_schema=source_schema,
            target_schema=target,
            write_decision_log=False,
        )
        return self._convert_candidates(response)

    def get_scoring_signals(self) -> ScoringSignals:
        if not self._backend_available:
            return self._fallback.get_scoring_signals()
        try:
            from backend.app.services import mapping_service  # type: ignore
            from backend.app.services import mapping_policy  # type: ignore

            # `DEFAULT_SCORING_PROFILE` is a string key (e.g. "balanced");
            # the actual weight dict lives in `SCORING_PROFILES`.
            profile_name = mapping_service.DEFAULT_SCORING_PROFILE
            profile = mapping_policy.SCORING_PROFILES.get(profile_name, {})
            return ScoringSignals(
                name=profile.get("name", 0.0),
                semantic=profile.get("semantic", 0.0),
                knowledge=profile.get("knowledge", 0.0),
                canonical=profile.get("canonical", 0.0),
                pattern=profile.get("pattern", 0.0),
                statistical=profile.get("statistical", 0.0),
                overlap=profile.get("overlap", 0.0),
                embedding=profile.get("embedding", 0.0),
                correction=profile.get("correction", 0.0),
                llm=profile.get("llm", 0.0),
            )
        except Exception:  # noqa: BLE001
            return ScoringSignals()

    @staticmethod
    def _convert_candidates(response) -> List[CandidateOption]:
        """Convert backend ``AutoMappingResponse`` to ``list[CandidateOption]``.

        The backend's ``AutoMappingResponse`` exposes two relevant fields:

        - ``mappings`` — one ``MappingCandidate`` per source field, each with
          the selected target and a confidence/method/methodology summary.
        - ``ranked_mappings`` — one ``SourceMappingResult`` per source field,
          each with a ``candidates`` list of inner ``CandidateOption`` items
          ranked from best to worst.

        We flatten the inner ``candidates`` lists (the ranked options) so the
        SDK caller can iterate them in score order. We also tag each emitted
        ``CandidateOption`` with the source field name via ``setattr`` so
        callers can group results by source — the SDK model does not yet
        carry a ``source`` field on ``CandidateOption``.

        All backend-to-SDK coercion is delegated to ``_compat.to_candidate_option``
        so the conversion logic lives in one place. If a candidate cannot
        be coerced (e.g. a malformed payload from a misbehaving backend),
        it is skipped silently rather than aborting the whole response.
        """
        from ._compat import to_candidate_option  # late import to keep this module cheap

        result: List[CandidateOption] = []
        ranked = getattr(response, "ranked_mappings", None)
        if ranked is None:
            # Fallback for very old backend versions that only expose ``mappings``.
            ranked = []
            for mc in getattr(response, "mappings", []) or []:
                class _R:  # noqa: D401 - tiny adapter shim
                    source = getattr(mc, "source", "")
                    candidates = getattr(mc, "candidates", []) or []
                ranked.append(_R())

        for rm in ranked:
            source_name = getattr(rm, "source", "")
            for c in getattr(rm, "candidates", []) or []:
                try:
                    converted = to_candidate_option(c)
                except Exception:  # noqa: BLE001
                    # Skip malformed candidates — the rest of the response
                    # is still useful to the SDK caller.
                    continue
                # Attach source field name for downstream grouping.
                # ``object.__setattr__`` is used because Pydantic models
                # are frozen (or otherwise refuse attribute writes).
                try:
                    object.__setattr__(converted, "source", source_name)
                except Exception:  # noqa: BLE001
                    pass
                result.append(converted)
        return result


class BackendAsyncMappingEngine:
    """Concrete ``AsyncMappingEngine`` backed by the Semantra backend.

    The async engine is used by agent pipelines that want to execute
    mapping candidate generation without blocking the event loop. When the
    backend package is not importable, this adapter falls back to the
    in-memory mapping engine and runs it in a worker thread.
    """

    def __init__(self, context: BackendContext | None = None) -> None:
        self.context = context
        self._fallback = InMemoryMappingEngine()
        self._backend_available = False
        self._backend_generate = None
        try:
            from backend.app.services import mapping_service  # type: ignore

            self._backend_generate = mapping_service.generate_mapping_candidates
            self._backend_available = True
        except Exception:  # noqa: BLE001
            self._backend_available = False

    async def map_source_to_target(
        self, source: DatasetHandle, target: SchemaProfile
    ) -> List[CandidateOption]:
        return await asyncio.to_thread(self._map_source_to_target_sync, source, target)

    def _map_source_to_target_sync(
        self, source: DatasetHandle, target: SchemaProfile
    ) -> List[CandidateOption]:
        if not self._backend_available or self._backend_generate is None:
            return self._fallback.map_source_to_target(source, target)

        source_schema = source.schema_profile
        response = self._backend_generate(
            source_schema=source_schema,
            target_schema=target,
            write_decision_log=False,
        )
        return self._convert_candidates(response)
