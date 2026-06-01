"""Runtime backpressure guards for long synchronous mapping and bounded LLM routes."""

from __future__ import annotations

from contextlib import contextmanager
from threading import BoundedSemaphore, Lock

from app.core.config import settings


class RuntimeCapacityError(RuntimeError):
    """Raised when a bounded runtime surface has reached its concurrency limit."""

    def __init__(self, detail: str, *, retry_after_seconds: int) -> None:
        super().__init__(detail)
        self.retry_after_seconds = retry_after_seconds


def _positive_limit(value: int, *, minimum: int = 1) -> int:
    return max(minimum, int(value))


class RuntimeCapacityGuard:
    """Guard a small number of synchronous runtime surfaces against overload in local pilot mode."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._reset_unlocked()

    @property
    def sync_mapping_capacity(self) -> int:
        return self._sync_mapping_capacity

    @property
    def bounded_llm_capacity(self) -> int:
        return self._bounded_llm_capacity

    def reset(self) -> None:
        with self._lock:
            self._reset_unlocked()

    @contextmanager
    def acquire_sync_mapping_slot(self, *, route_path: str, retry_path: str | None = None):
        detail = f"Synchronous mapping capacity is full for '{route_path}'."
        if retry_path:
            detail = f"{detail} Retry shortly or use '{retry_path}'."
        with self._acquire(self._sync_mapping_semaphore, detail=detail):
            yield

    @contextmanager
    def acquire_bounded_llm_slot(self, *, route_path: str):
        detail = f"Bounded LLM capacity is full for '{route_path}'. Retry shortly."
        with self._acquire(self._bounded_llm_semaphore, detail=detail):
            yield

    @contextmanager
    def _acquire(self, semaphore: BoundedSemaphore, *, detail: str):
        if not semaphore.acquire(blocking=False):
            raise RuntimeCapacityError(
                detail,
                retry_after_seconds=_positive_limit(settings.runtime_capacity_retry_after_seconds),
            )
        try:
            yield
        finally:
            semaphore.release()

    def _reset_unlocked(self) -> None:
        self._sync_mapping_capacity = _positive_limit(settings.sync_mapping_max_concurrent_requests)
        self._bounded_llm_capacity = _positive_limit(settings.bounded_llm_max_concurrent_requests)
        self._sync_mapping_semaphore = BoundedSemaphore(self._sync_mapping_capacity)
        self._bounded_llm_semaphore = BoundedSemaphore(self._bounded_llm_capacity)


runtime_capacity_guard = RuntimeCapacityGuard()