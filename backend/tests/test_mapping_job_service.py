from __future__ import annotations

import threading
import time

import pytest

from app.models.mapping import AutoMappingResponse
from app.services.mapping_job_service import (
    FINISHED_JOB_TTL_SECONDS,
    MAX_ACTIVE_JOBS,
    MAX_FINISHED_JOBS,
    MappingJob,
    MappingJobCapacityError,
    MappingJobStore,
)


def test_mapping_job_store_rejects_new_job_when_active_limit_is_reached() -> None:
    store = MappingJobStore()
    for index in range(MAX_ACTIVE_JOBS):
        store._jobs[f"active-{index}"] = MappingJob(job_id=f"active-{index}", status="running")

    with pytest.raises(MappingJobCapacityError):
        store.start(lambda progress_callback: None)


def test_mapping_job_store_prunes_expired_finished_job_before_status_lookup() -> None:
    store = MappingJobStore()
    expired_job = MappingJob(job_id="expired", status="completed")
    expired_job.updated_at_monotonic = time.monotonic() - FINISHED_JOB_TTL_SECONDS - 1
    store._jobs[expired_job.job_id] = expired_job

    with pytest.raises(KeyError):
        store.get_status("expired")

    assert "expired" not in store._jobs


def test_mapping_job_store_keeps_recent_finished_jobs_within_limit() -> None:
    store = MappingJobStore()
    base_time = time.monotonic()
    total_jobs = MAX_FINISHED_JOBS + 2
    for index in range(total_jobs):
        job = MappingJob(job_id=f"finished-{index}", status="completed")
        job.updated_at_monotonic = base_time - (total_jobs - index)
        store._jobs[job.job_id] = job

    status = store.get_status(f"finished-{total_jobs - 1}")

    assert status.job_id == f"finished-{total_jobs - 1}"
    assert len(store._jobs) == MAX_FINISHED_JOBS
    assert "finished-0" not in store._jobs
    assert "finished-1" not in store._jobs


def test_mapping_job_store_marks_job_cancel_requested() -> None:
    store = MappingJobStore()
    store._jobs["job-1"] = MappingJob(job_id="job-1", status="running")

    status = store.cancel("job-1")

    assert status.status == "cancel_requested"
    assert any("Cancellation requested" in line for line in status.activity)


def test_mapping_job_store_cancels_running_worker_at_next_progress_checkpoint() -> None:
    store = MappingJobStore()
    allow_second_checkpoint = threading.Event()

    def worker(progress_callback):
        progress_callback("checkpoint 1")
        allow_second_checkpoint.wait(timeout=1)
        progress_callback("checkpoint 2")
        return AutoMappingResponse()

    job = store.start(worker)

    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        status = store.get_status(job.job_id)
        if any("checkpoint 1" in line for line in status.activity):
            break
        time.sleep(0.01)

    requested = store.cancel(job.job_id)
    assert requested.status == "cancel_requested"

    allow_second_checkpoint.set()

    deadline = time.monotonic() + 1
    final_status = None
    while time.monotonic() < deadline:
        final_status = store.get_status(job.job_id)
        if final_status.status == "canceled":
            break
        time.sleep(0.01)

    assert final_status is not None
    assert final_status.status == "canceled"
    assert any("Mapping job canceled." in line for line in final_status.activity)
    assert final_status.response is None


def test_mapping_job_store_runtime_status_reports_in_memory_defaults() -> None:
    store = MappingJobStore()

    status = store.runtime_status()

    assert status.storage_mode == "in_memory"
    assert status.active_jobs == 0
    assert status.finished_jobs == 0
    assert status.durable_backend_recommended is False
    assert status.durable_backend_triggers == []


def test_mapping_job_store_runtime_status_surfaces_durable_backend_triggers() -> None:
    store = MappingJobStore()
    base_time = time.monotonic()
    for index in range(MAX_ACTIVE_JOBS):
        job = MappingJob(job_id=f"active-{index}", status="running")
        job.created_at_monotonic = base_time - FINISHED_JOB_TTL_SECONDS - 5
        store._jobs[job.job_id] = job
    for index in range(MAX_FINISHED_JOBS):
        job = MappingJob(job_id=f"finished-{index}", status="completed")
        job.updated_at_monotonic = base_time - index
        store._jobs[job.job_id] = job

    status = store.runtime_status()

    assert status.active_jobs == MAX_ACTIVE_JOBS
    assert status.finished_jobs == MAX_FINISHED_JOBS
    assert status.durable_backend_recommended is True
    assert set(status.durable_backend_triggers) == {
        "active_capacity_reached",
        "finished_retention_saturated",
        "long_running_job_exceeds_retention_window",
    }