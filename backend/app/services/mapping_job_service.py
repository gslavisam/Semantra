from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from app.models.mapping import AutoMappingResponse, MappingJobStatusResponse

MAX_ACTIVITY_LINES = 500


@dataclass
class MappingJob:
    job_id: str
    status: str = "queued"
    activity: list[str] = field(default_factory=list)
    response: AutoMappingResponse | None = None
    error: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


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

    def _run_worker(self, job_id: str, worker) -> None:
        self._set_status(job_id, "running")
        self.append_activity(job_id, "Mapping job started.")
        try:
            response = worker(lambda message: self.append_activity(job_id, message))
            self._set_response(job_id, response)
            self.append_activity(job_id, "Mapping job completed.")
            self._set_status(job_id, "completed")
        except Exception as error:
            self.append_activity(job_id, f"Mapping job failed: {error}")
            self._set_error(job_id, str(error))
            self._set_status(job_id, "failed")

    def append_activity(self, job_id: str, message: str) -> None:
        timestamp = datetime.now(UTC).strftime("%H:%M:%S")
        with self._lock:
            job = self._jobs[job_id]
            job.activity.append(f"{timestamp} | {message}")
            if len(job.activity) > MAX_ACTIVITY_LINES:
                job.activity = job.activity[-MAX_ACTIVITY_LINES:]
            job.updated_at = datetime.now(UTC).isoformat()

    def _save(self, job: MappingJob) -> None:
        with self._lock:
            self._jobs[job.job_id] = job

    def _set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = status
            job.updated_at = datetime.now(UTC).isoformat()

    def _set_response(self, job_id: str, response: AutoMappingResponse) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.response = response
            job.updated_at = datetime.now(UTC).isoformat()

    def _set_error(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.error = error
            job.updated_at = datetime.now(UTC).isoformat()


mapping_job_store = MappingJobStore()
