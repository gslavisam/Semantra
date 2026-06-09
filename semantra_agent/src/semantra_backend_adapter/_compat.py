"""Coercion helpers for converting backend model instances to SDK models.

Background
----------
The backend (``backend.app.models.mapping``) and the SDK
(``semantra_core.models.mapping``) define ``CandidateOption`` (and the
other mapping types) with **identical** field shapes, but they live in
different modules. An ``isinstance(c, CandidateOption)`` check across
the module boundary always returns ``False`` for backend instances.

The previous adapter code worked around this by reading each attribute
with ``getattr(c, "field", default)`` and re-constructing a core
``CandidateOption``. That "best-effort" approach silently dropped any
field that was added to the backend later (``canonical_details``,
``signals``, etc.) — exactly the rich payload the SDK is supposed to
expose to its callers.

The functions in this module replace the ``getattr`` re-construction
with a single, validated path: Pydantic's ``model_validate`` does the
duck-typing for us, raises on missing or invalid values (fail-loud),
and preserves every field the backend provides.

Three input shapes are supported, in order of preference:

1. **Already a core ``CandidateOption``** — returned as-is.
2. **Any Pydantic ``BaseModel``** with the same fields (e.g. a backend
   ``CandidateOption``) — round-tripped through ``model_dump()`` and
   validated into a core ``CandidateOption``.
3. **A ``dict``** — validated directly (e.g. JSON payloads).
4. **A duck-typed object** (e.g. an old backend shape, a unit-test
   stub) — explicitly reconstructed with ``getattr`` and sensible
   defaults. This is the only path that can still lose fields, but it
   is now confined to one place and clearly documented.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from semantra_core.models.mapping import (
    CandidateOption,
    CanonicalMappingDetails,
    ScoringSignals,
)


def to_candidate_option(c: Any) -> CandidateOption:
    """Coerce *c* into a core ``CandidateOption`` instance.

    See module docstring for the supported input shapes. This function
    is the single conversion point used by the adapter; do NOT
    duplicate the ``getattr`` reconstruction at call sites.
    """
    # 1. Already a core instance → no-op.
    if isinstance(c, CandidateOption):
        return c

    # 2. Any Pydantic model with the same field shape (e.g. backend
    #    CandidateOption, MappingCandidate, …). ``model_dump()`` drops
    #    extra fields and normalises values, so we get a clean dict
    #    to feed back into ``model_validate``.
    if isinstance(c, BaseModel):
        return CandidateOption.model_validate(c.model_dump())

    # 3. Dict → validate directly.
    if isinstance(c, dict):
        return CandidateOption.model_validate(c)

    # 4. Duck-typed fallback. This path can lose information (e.g. a
    #    custom ``signals`` shape) and is intentionally the last resort.
    #    Centralised here so it is easy to find and to extend.
    return CandidateOption(
        target=getattr(c, "target", ""),
        confidence=float(getattr(c, "confidence", 0.0)),
        confidence_label=getattr(c, "confidence_label", "low_confidence"),
        method=getattr(c, "method", "adapter"),
        signals=getattr(c, "signals", ScoringSignals()),
        explanation=list(getattr(c, "explanation", [])),
        canonical_details=getattr(c, "canonical_details", CanonicalMappingDetails()),
    )


def is_candidate_option_like(c: Any) -> bool:
    """Cheap structural check: does *c* look like a CandidateOption?

    Useful when callers want to filter a list down to the candidates
    only (skipping ``MappingCandidate`` "selected" objects that may
    appear in mixed responses from older backend versions).
    """
    # Core or backend CandidateOption both expose ``target`` and
    # ``confidence``; ``MappingCandidate`` also has those plus ``source``.
    return (
        isinstance(c, CandidateOption)
        or (isinstance(c, BaseModel) and "target" in type(c).model_fields and "confidence" in type(c).model_fields and "source" not in type(c).model_fields)
        or (hasattr(c, "target") and hasattr(c, "confidence") and hasattr(c, "method") and not hasattr(c, "source"))
    )
