"""Async mapping job runtime with pluggable state stores and durable SQLite-backed status persistence."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from app.models.mapping import AutoMappingResponse, MappingJobRuntimeStatusResponse, MappingJobStatusResponse
from app.services.mapping_service import ProgressCallbackCancelled
from app.services.persistence_service import persistence_service

MAX_ACTIVITY_LINES = 500
MAX_ACTIVE_JOBS = 4
MAX_FINISHED_JOBS = 32
FINISHED_JOB_TTL_SECONDS = 15 * 60
ACTIVE_JOB_STATUSES = {"queued", "running", "cancel_requested"}
FINISHED_JOB_STATUSES = {"completed", "failed", "canceled"}


def _parse_job_timestamp(timestamp: str) -> datetime:
    parsed = datetime.fromisoformat(timestamp)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _job_age_seconds(timestamp: str) -> float:
    return max(0.0, (datetime.now(UTC) - _parse_job_timestamp(timestamp)).total_seconds())


class MappingJobCapacityError(RuntimeError):
    """Raised when the mapping job store has reached active-job capacity."""

    pass


@dataclass
class MappingJob:
    """Runtime record for one async mapping job."""

    job_id: str
    status: str = "queued"
    activity: list[str] = field(default_factory=list)
    response: AutoMappingResponse | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    created_at_monotonic: float = field(default_factory=time.monotonic, repr=False)
    updated_at_monotonic: float = field(default_factory=time.monotonic, repr=False)
    retry_count: int = 0
    cancel_requested: bool = False
    canceled_at: str | None = None


class MappingJobStateStore(Protocol):
    """Backing store contract for mapping job lifecycle state."""

    storage_mode: str
    restart_safe: bool
    cross_process_safe: bool

    def save_job(self, job: MappingJob) -> None: ...

    def get_job(self, job_id: str) -> MappingJob: ...

    def list_jobs(self) -> list[MappingJob]: ...

    def append_activity(self, job_id: str, line: str) -> None: ...

    def clear(self) -> None: ...

    def prune_finished_jobs(self, *, finished_job_ttl_seconds: int, max_finished_jobs: int) -> None: ...


class InMemoryMappingJobStateStore:
    """State store used by focused unit tests and local non-durable flows."""

    storage_mode = "in_memory"
    restart_safe = False
    cross_process_safe = False

    def __init__(self) -> None:
        self._jobs: dict[str, MappingJob] = {}

    def save_job(self, job: MappingJob) -> None:
        self._jobs[job.job_id] = job

    def get_job(self, job_id: str) -> MappingJob:
        return self._jobs[job_id]

    def list_jobs(self) -> list[MappingJob]:
        return list(self._jobs.values())

    def append_activity(self, job_id: str, line: str) -> None:
        job = self._jobs[job_id]
        job.activity.append(line)
        if len(job.activity) > MAX_ACTIVITY_LINES:
            job.activity = job.activity[-MAX_ACTIVITY_LINES:]

    def clear(self) -> None:
        self._jobs.clear()

    def prune_finished_jobs(self, *, finished_job_ttl_seconds: int, max_finished_jobs: int) -> None:
        expiration_cutoff = time.monotonic() - finished_job_ttl_seconds
        expired_job_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.status in FINISHED_JOB_STATUSES and job.updated_at_monotonic < expiration_cutoff
        ]
        for job_id in expired_job_ids:
            self._jobs.pop(job_id, None)

        finished_jobs = [
            (job.updated_at_monotonic, job_id)
            for job_id, job in self._jobs.items()
            if job.status in FINISHED_JOB_STATUSES
        ]
        overflow = len(finished_jobs) - max_finished_jobs
        if overflow <= 0:
            return
        for _, job_id in sorted(finished_jobs)[:overflow]:
            self._jobs.pop(job_id, None)


class SQLiteMappingJobStateStore:
    """SQLite-backed status and progress persistence for mapping jobs."""

    storage_mode = "sqlite_status"
    restart_safe = False
    cross_process_safe = False

    def __init__(self) -> None:
        self._recover_interrupted_jobs()

    def save_job(self, job: MappingJob) -> None:
        persistence_service.save_mapping_job(
            job_id=job.job_id,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            created_at_monotonic=job.created_at_monotonic,
            updated_at_monotonic=job.updated_at_monotonic,
            retry_count=job.retry_count,
            cancel_requested=job.cancel_requested,
            canceled_at=job.canceled_at,
            response=job.response,
            error=job.error,
        )

    def get_job(self, job_id: str) -> MappingJob:
        payload = persistence_service.get_mapping_job(job_id)
        if payload is None:
            raise KeyError(job_id)
        return MappingJob(
            job_id=payload["job_id"],
            status=payload["status"],
            activity=persistence_service.list_mapping_job_events(job_id, limit=MAX_ACTIVITY_LINES),
            response=payload["response"],
            error=payload["error"],
            created_at=payload["created_at"],
            updated_at=payload["updated_at"],
            created_at_monotonic=payload["created_at_monotonic"],
            updated_at_monotonic=payload["updated_at_monotonic"],
            retry_count=payload["retry_count"],
            cancel_requested=payload["cancel_requested"],
            canceled_at=payload["canceled_at"],
        )

    def list_jobs(self) -> list[MappingJob]:
        jobs: list[MappingJob] = []
        for payload in persistence_service.list_mapping_jobs():
            jobs.append(
                MappingJob(
                    job_id=payload["job_id"],
                    status=payload["status"],
                    response=payload["response"],
                    error=payload["error"],
                    created_at=payload["created_at"],
                    updated_at=payload["updated_at"],
                    created_at_monotonic=payload["created_at_monotonic"],
                    updated_at_monotonic=payload["updated_at_monotonic"],
                    retry_count=payload["retry_count"],
                    cancel_requested=payload["cancel_requested"],
                    canceled_at=payload["canceled_at"],
                )
            )
        return jobs

    def append_activity(self, job_id: str, line: str) -> None:
        timestamp, _, message = line.partition(" | ")
        del timestamp
        persistence_service.append_mapping_job_event(
            job_id,
            created_at=datetime.now(UTC).isoformat(),
            message=message or line,
        )
        persistence_service.trim_mapping_job_events(job_id, keep_last=MAX_ACTIVITY_LINES)

    def clear(self) -> None:
        persistence_service.clear_mapping_jobs()

    def prune_finished_jobs(self, *, finished_job_ttl_seconds: int, max_finished_jobs: int) -> None:
        jobs = self.list_jobs()
        expired_job_ids = [
            job.job_id
            for job in jobs
            if job.status in FINISHED_JOB_STATUSES and _job_age_seconds(job.updated_at) > finished_job_ttl_seconds
        ]

        finished_jobs = [
            (_parse_job_timestamp(job.updated_at), job.job_id)
            for job in jobs
            if job.status in FINISHED_JOB_STATUSES and job.job_id not in expired_job_ids
        ]
        overflow = len(finished_jobs) - max_finished_jobs
        if overflow > 0:
            expired_job_ids.extend(job_id for _, job_id in sorted(finished_jobs)[:overflow])
        persistence_service.delete_mapping_jobs(sorted(set(expired_job_ids)))

    def _recover_interrupted_jobs(self) -> None:
        now = datetime.now(UTC).isoformat()
        persistence_service.fail_active_mapping_jobs(
            updated_at=now,
            updated_at_monotonic=time.monotonic(),
            message="Mapping job interrupted before completion because the local worker runtime restarted.",
            error="Mapping job interrupted before completion because the local worker runtime restarted.",
        )


class MappingJobStore:
    """Async job runtime that delegates lifecycle persistence to a pluggable state store."""

    def __init__(self, state_store: MappingJobStateStore | None = None) -> None:
        self._state_store = state_store or InMemoryMappingJobStateStore()
        self._lock = threading.Lock()

    @property
    def _jobs(self) -> dict[str, MappingJob]:
        if isinstance(self._state_store, InMemoryMappingJobStateStore):
            return self._state_store._jobs
        raise AttributeError("The configured mapping job store does not expose an in-memory _jobs dictionary.")

    def start(self, worker) -> MappingJob:
        """Create and launch one background mapping job for the supplied worker callback."""

        with self._lock:
            self._prune_jobs_locked()
            active_jobs = sum(1 for item in self._state_store.list_jobs() if item.status in ACTIVE_JOB_STATUSES)
            if active_jobs >= MAX_ACTIVE_JOBS:
                raise MappingJobCapacityError(
                    f"Too many active mapping jobs ({active_jobs}/{MAX_ACTIVE_JOBS}). Try again after current jobs finish."
                )
            job = MappingJob(job_id=uuid4().hex)
            self._state_store.save_job(job)

        thread = threading.Thread(target=self._run_worker, args=(job.job_id, worker), daemon=True)
        thread.start()
        return job

    def get_status(self, job_id: str) -> MappingJobStatusResponse:
        with self._lock:
            self._prune_jobs_locked()
            job = self._state_store.get_job(job_id)
            return self._build_status_response(job)

    def clear(self) -> None:
        with self._lock:
            self._state_store.clear()

    def runtime_status(self) -> MappingJobRuntimeStatusResponse:
        with self._lock:
            self._prune_jobs_locked()
            jobs = self._state_store.list_jobs()
            active_jobs = [job for job in jobs if job.status in ACTIVE_JOB_STATUSES]
            finished_jobs = [job for job in jobs if job.status in FINISHED_JOB_STATUSES]
            oldest_active_job_age_seconds = 0
            if active_jobs:
                if self._state_store.storage_mode == "sqlite_status":
                    oldest_active_job_age_seconds = int(max(_job_age_seconds(job.created_at) for job in active_jobs))
                else:
                    oldest_active_job_age_seconds = int(
                        max(time.monotonic() - job.created_at_monotonic for job in active_jobs)
                    )

            durable_backend_triggers: list[str] = []
            if len(active_jobs) >= MAX_ACTIVE_JOBS:
                durable_backend_triggers.append("active_capacity_reached")
            if len(finished_jobs) >= MAX_FINISHED_JOBS:
                durable_backend_triggers.append("finished_retention_saturated")
            if oldest_active_job_age_seconds >= FINISHED_JOB_TTL_SECONDS:
                durable_backend_triggers.append("long_running_job_exceeds_retention_window")

            return MappingJobRuntimeStatusResponse(
                storage_mode=self._state_store.storage_mode,
                restart_safe=self._state_store.restart_safe,
                cross_process_safe=self._state_store.cross_process_safe,
                active_jobs=len(active_jobs),
                max_active_jobs=MAX_ACTIVE_JOBS,
                finished_jobs=len(finished_jobs),
                max_finished_jobs=MAX_FINISHED_JOBS,
                finished_job_ttl_seconds=FINISHED_JOB_TTL_SECONDS,
                oldest_active_job_age_seconds=oldest_active_job_age_seconds,
                durable_backend_recommended=bool(durable_backend_triggers),
                durable_backend_triggers=durable_backend_triggers,
            )

    def cancel(self, job_id: str) -> MappingJobStatusResponse:
        with self._lock:
            self._prune_jobs_locked()
            job = self._state_store.get_job(job_id)
            if job.status in FINISHED_JOB_STATUSES:
                return self._build_status_response(job)
            if job.status != "cancel_requested":
                job.status = "cancel_requested"
                job.cancel_requested = True
                self._touch_job_locked(job)
                self._state_store.save_job(job)
                self._append_activity_locked(
                    job,
                    "Cancellation requested; the current step will stop at the next progress checkpoint.",
                )
            return self._build_status_response(self._state_store.get_job(job_id))

    def _run_worker(self, job_id: str, worker) -> None:
        if self._is_cancel_requested(job_id):
            self.append_activity(job_id, "Mapping job canceled before execution started.")
            self._set_status(job_id, "canceled")
            return
        self._set_status(job_id, "running")
        self.append_activity(job_id, "Mapping job started.")
        try:
            response = worker(self._make_progress_callback(job_id))
            if self._is_cancel_requested(job_id):
                self.append_activity(job_id, "Mapping job canceled.")
                self._set_status(job_id, "canceled")
                return
            self._set_response(job_id, response)
            self.append_activity(job_id, "Mapping job completed.")
            self._set_status(job_id, "completed")
        except ProgressCallbackCancelled:
            self.append_activity(job_id, "Mapping job canceled.")
            self._set_status(job_id, "canceled")
        except Exception as error:
            self.append_activity(job_id, f"Mapping job failed: {error}")
            self._set_error(job_id, str(error))
            self._set_status(job_id, "failed")

    def append_activity(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._state_store.get_job(job_id)
            self._append_activity_locked(job, message)

    def _set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._state_store.get_job(job_id)
            job.status = status
            job.cancel_requested = status == "cancel_requested"
            if status == "canceled":
                job.canceled_at = datetime.now(UTC).isoformat()
            elif status != "cancel_requested":
                job.canceled_at = None
            if status in FINISHED_JOB_STATUSES:
                job.cancel_requested = False
            self._touch_job_locked(job)
            self._state_store.save_job(job)
            if status in FINISHED_JOB_STATUSES:
                self._prune_jobs_locked()

    def _set_response(self, job_id: str, response: AutoMappingResponse) -> None:
        with self._lock:
            job = self._state_store.get_job(job_id)
            job.response = response
            self._touch_job_locked(job)
            self._state_store.save_job(job)

    def _set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._state_store.get_job(job_id)
            job.error = error
            self._touch_job_locked(job)
            self._state_store.save_job(job)

    def _touch_job_locked(self, job: MappingJob) -> None:
        job.updated_at = datetime.now(UTC).isoformat()
        job.updated_at_monotonic = time.monotonic()

    def _append_activity_locked(self, job: MappingJob, message: str) -> None:
        line = f"{datetime.now(UTC).strftime('%H:%M:%S')} | {message}"
        self._state_store.append_activity(job.job_id, line)
        job.activity = self._state_store.get_job(job.job_id).activity
        self._touch_job_locked(job)
        self._state_store.save_job(job)

    def _build_status_response(self, job: MappingJob) -> MappingJobStatusResponse:
        return MappingJobStatusResponse(
            job_id=job.job_id,
            status=job.status,
            activity=list(job.activity),
            response=job.response,
            error=job.error,
        )

    def _make_progress_callback(self, job_id: str):
        def callback(message: str) -> None:
            self.append_activity(job_id, message)
            if self._is_cancel_requested(job_id):
                raise ProgressCallbackCancelled(job_id)

        return callback

    def _is_cancel_requested(self, job_id: str) -> bool:
        with self._lock:
            try:
                job = self._state_store.get_job(job_id)
            except KeyError:
                return False
            return job.status == "cancel_requested" or job.cancel_requested

    def _prune_jobs_locked(self) -> None:
        self._state_store.prune_finished_jobs(
            finished_job_ttl_seconds=FINISHED_JOB_TTL_SECONDS,
            max_finished_jobs=MAX_FINISHED_JOBS,
        )


mapping_job_store = MappingJobStore(state_store=SQLiteMappingJobStateStore())
