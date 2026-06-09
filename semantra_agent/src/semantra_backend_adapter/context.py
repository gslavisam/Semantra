"""Shared runtime context for backend adapters.

The adapter classes need access to a few things from the FastAPI backend:
- A way to obtain a database session.
- The application settings (for LLM provider, model, etc.).
- Optional pre-built service instances.

This module provides a lightweight dataclass that can be constructed
either manually (for tests) or via `create_default_context()` (for the
real backend).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class BackendContext:
    """Runtime context required by backend adapters.

    Mirrors a subset of the FastAPI dependencies without requiring a
    request object. All fields are optional; adapters are expected to
    raise a clear error if a needed dependency is missing.
    """

    db_session_factory: Optional[Callable[..., Any]] = None
    settings: Any = None
    extras: dict[str, Any] = field(default_factory=dict)

    def require_session_factory(self) -> Callable[..., Any]:
        if self.db_session_factory is None:
            raise RuntimeError(
                "BackendContext.db_session_factory is not configured. "
                "Use create_default_context() or pass one explicitly."
            )
        return self.db_session_factory

    def require_settings(self) -> Any:
        if self.settings is None:
            raise RuntimeError(
                "BackendContext.settings is not configured. "
                "Use create_default_context() or pass one explicitly."
            )
        return self.settings


def create_default_context() -> BackendContext:
    """Build a BackendContext by importing from the real backend.

    This function performs lazy imports so that the adapter package can
    be installed even if the full backend is not yet on sys.path.
    """
    try:
        from backend.app.core.config import settings  # type: ignore
    except Exception as exc:  # noqa: BLE001
        settings = None  # type: ignore
        _settings_error = exc
    else:
        _settings_error = None

    try:
        from backend.app.core.db import SessionLocal  # type: ignore
    except Exception as exc:  # noqa: BLE001
        SessionLocal = None  # type: ignore
        _db_error = exc
    else:
        _db_error = None

    if settings is None and SessionLocal is None:
        # Both imports failed; the backend is not importable.
        raise RuntimeError(
            "Cannot create default BackendContext: the Semantra backend "
            "package is not importable. Install it with "
            "`pip install -e ./backend` (or add it to PYTHONPATH) and try again."
        )

    return BackendContext(
        db_session_factory=SessionLocal,
        settings=settings,
        extras={"_settings_error": _settings_error, "_db_error": _db_error},
    )
