import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class JobKind(StrEnum):
    BUILD = "build"
    EXTRACT = "extract"
    CATALOG_SYNC = "catalog_sync"
    CATALOG_EXTRACT = "catalog_extract"
    CATALOG_CANONICAL_SYNC = "catalog_canonical_sync"
    CATALOG_CANONICAL_EXTRACT = "catalog_canonical_extract"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobRecord:
    id: str
    kind: JobKind
    status: JobStatus = JobStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    progress: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    artifact_dir: str | None = None


class JobRegistry:
    def __init__(self, max_concurrent: int = 1) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)

    def create(self, kind: JobKind) -> JobRecord:
        job_id = uuid.uuid4().hex
        record = JobRecord(id=job_id, kind=kind)
        self._jobs[job_id] = record
        return record

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def run(
        self,
        job_id: str,
        coro_factory: Callable[[JobRecord], Awaitable[None]],
    ) -> None:
        record = self._jobs[job_id]
        async with self._semaphore:
            record.status = JobStatus.RUNNING
            record.updated_at = datetime.now(tz=UTC)
            try:
                await coro_factory(record)
                record.status = JobStatus.COMPLETED
            except Exception as exc:  # noqa: BLE001 — job boundary
                record.status = JobStatus.FAILED
                record.error = str(exc)
            finally:
                record.updated_at = datetime.now(tz=UTC)

    def start_background(
        self,
        job_id: str,
        coro_factory: Callable[[JobRecord], Awaitable[None]],
    ) -> None:
        asyncio.create_task(self.run(job_id, coro_factory))
