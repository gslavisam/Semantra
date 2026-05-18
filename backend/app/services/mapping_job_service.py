from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.models.mapping import AutoMappingResponse, MappingJobRuntimeStatusResponse, MappingJobStatusResponse
from app.services.mapping_service import ProgressCallbackCancelled

MAX_ACTIVITY_LINES = 500
MAX_ACTIVE_JOBS = 4
MAX_FINISHED_JOBS = 32
FINISHED_JOB_TTL_SECONDS = 15 * 60
ACTIVE_JOB_STATUSES = {"queued", "running", "cancel_requested"}
FINISHED_JOB_STATUSES = {"completed", "failed", "canceled"}


class MappingJobCapacityError(RuntimeError):
    pass


@dataclass
class MappingJob:
    job_id: str
    status: str = "queued"
    activity: list[str] = field(default_factory=list)
    response: AutoMappingResponse | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    created_at_monotonic: float = field(default_factory=time.monotonic, repr=False)
    updated_at_monotonic: float = field(default_factory=time.monotonic, repr=False)


class MappingJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, MappingJob] = {}
        self._lock = threading.Lock()

    def start(self, worker) -> MappingJob:
        job = MappingJob(job_id=uuid4().hex)
        self._save(job)
        thread = threading.Thread(target=self._run_worker, args=(job.job_id, worker), daemon=True)
        thread.start()
        return job

    def get_status(self, job_id: str) -> MappingJobStatusResponse:
        with self._lock:
            self._prune_jobs_locked()
            job = self._jobs[job_id]
            return MappingJobStatusResponse(
                job_id=job.job_id,
                status=job.status,
                activity=list(job.activity),
                response=job.response,
                error=job.error,
            )

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()

    def runtime_status(self) -> MappingJobRuntimeStatusResponse:
        with self._lock:
            self._prune_jobs_locked()
            active_jobs = [job for job in self._jobs.values() if job.status in ACTIVE_JOB_STATUSES]
            finished_jobs = [job for job in self._jobs.values() if job.status in FINISHED_JOB_STATUSES]
            oldest_active_job_age_seconds = 0
            if active_jobs:
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
            job = self._jobs[job_id]
            if job.status in FINISHED_JOB_STATUSES:
                return self._build_status_response(job)
            if job.status != "cancel_requested":
                job.status = "cancel_requested"
                self._append_activity_locked(job, "Cancellation requested; the current step will stop at the next progress checkpoint.")
            return self._build_status_response(job)

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
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        with self._lock:
            job = self._jobs[job_id]
            self._append_activity_locked(job, message, timestamp=timestamp)

    def _save(self, job: MappingJob) -> None:
        with self._lock:
            self._prune_jobs_locked()
            active_jobs = sum(1 for item in self._jobs.values() if item.status in ACTIVE_JOB_STATUSES)
            if active_jobs >= MAX_ACTIVE_JOBS:
                raise MappingJobCapacityError(
                    f"Too many active mapping jobs ({active_jobs}/{MAX_ACTIVE_JOBS}). Try again after current jobs finish."
                )
            self._jobs[job.job_id] = job
            self._prune_jobs_locked()

    def _set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = status
            self._touch_locked(job)
            if status in FINISHED_JOB_STATUSES:
                self._prune_jobs_locked()

    def _set_response(self, job_id: str, response: AutoMappingResponse) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.response = response
            self._touch_locked(job)

    def _set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.error = error
            self._touch_locked(job)

    def _touch_locked(self, job: MappingJob) -> None:
        job.updated_at = datetime.now(UTC).isoformat()
        job.updated_at_monotonic = time.monotonic()

    def _append_activity_locked(self, job: MappingJob, message: str, *, timestamp: str | None = None) -> None:
        job.activity.append(f"{timestamp or datetime.now(UTC).strftime('%H:%M:%S')} | {message}")
        if len(job.activity) > MAX_ACTIVITY_LINES:
            job.activity = job.activity[-MAX_ACTIVITY_LINES:]
        self._touch_locked(job)

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
            job = self._jobs[job_id]
            return job.status == "cancel_requested"

    def _prune_jobs_locked(self) -> None:
        expiration_cutoff = time.monotonic() - FINISHED_JOB_TTL_SECONDS
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
        overflow = len(finished_jobs) - MAX_FINISHED_JOBS
        if overflow <= 0:
            return
        for _, job_id in sorted(finished_jobs)[:overflow]:
            self._jobs.pop(job_id, None)


mapping_job_store = MappingJobStore()
