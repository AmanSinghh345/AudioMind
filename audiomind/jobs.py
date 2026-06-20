from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from .repository import Repository


class JobManager:
    """Small local worker pool with persistent job status.

    The interface is intentionally compatible with replacing this implementation
    with Redis/RQ or Celery when multiple application instances are deployed.
    """

    def __init__(self, repository: Repository, max_workers: int = 2):
        self.repository = repository
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="audiomind")

    def submit(
        self, kind: str, payload: dict[str, Any], task: Callable[[], dict[str, Any]],
    ) -> str:
        job_id = self.repository.create_job(kind, payload)
        self.executor.submit(self._run, job_id, task)
        return job_id

    def _run(self, job_id: str, task: Callable[[], dict[str, Any]]) -> None:
        self.repository.update_job(job_id, "running", 10)
        try:
            result = task()
            self.repository.update_job(job_id, "completed", 100, result=result)
        except Exception as exc:
            self.repository.update_job(job_id, "failed", 100, error=str(exc)[:2000])
