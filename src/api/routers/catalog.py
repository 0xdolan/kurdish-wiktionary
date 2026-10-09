from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from src.api.deps import AppStateDep, DbSessionDep, SettingsDep
from src.api.schemas_catalog import (
    CatalogExtractResponse,
    CatalogExtractSyncRequest,
    CatalogJobCreatedResponse,
    CatalogJobStatusResponse,
    CatalogStatsResponse,
    CatalogSyncResponse,
    WordlistItemResponse,
    WordlistPageResponse,
)
from src.api.schemas_mdx import JobCreatedResponse
from src.catalog.extract import extract_pending_wordlist
from src.catalog.stats import fetch_catalog_stats
from src.catalog.sync import sync_wordlist_to_sql
from src.mdict.jobs import JobKind, JobRecord, JobRegistry
from src.repository.db.base import get_session_factory, init_engine
from src.repository.db.models import WordlistTitleModel

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _jobs(state: AppStateDep) -> JobRegistry:
    return state.mdict_jobs


def _job_response(record: JobRecord) -> CatalogJobStatusResponse:
    return CatalogJobStatusResponse(
        job_id=record.id,
        kind=record.kind.value,
        status=record.status.value,
        progress=record.progress,
        error=record.error,
        artifact_dir=record.artifact_dir,
    )


@router.get("/stats", response_model=CatalogStatsResponse)
async def catalog_stats(settings: SettingsDep, session: DbSessionDep) -> CatalogStatsResponse:
    stats = await fetch_catalog_stats(session, settings.zim_path)
    return CatalogStatsResponse(**asdict(stats))


@router.get("/wordlist", response_model=WordlistPageResponse)
async def catalog_wordlist(
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[
        Literal["pending", "extracted", "skipped", "failed"] | None,
        Query(),
    ] = None,
) -> WordlistPageResponse:
    base = select(WordlistTitleModel)
    count_stmt = select(func.count()).select_from(WordlistTitleModel)
    if status is not None:
        base = base.where(WordlistTitleModel.extract_status == status)
        count_stmt = count_stmt.where(WordlistTitleModel.extract_status == status)

    total = int((await session.execute(count_stmt)).scalar_one())
    stmt = base.order_by(WordlistTitleModel.id.asc()).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    items = [
        WordlistItemResponse(
            id=row.id,
            title=row.title,
            extract_status=row.extract_status,  # type: ignore[arg-type]
            entry_id=row.entry_id,
            discovered_at=row.discovered_at,
            extracted_at=row.extracted_at,
        )
        for row in rows
    ]
    return WordlistPageResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/wordlist/sync", response_model=CatalogJobCreatedResponse, status_code=202)
async def catalog_sync_wordlist_async(
    settings: SettingsDep,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobCreatedResponse:
    if not settings.zim_path.is_file():
        raise HTTPException(status_code=503, detail="ZIM file not readable.")
    record = jobs.create(JobKind.CATALOG_SYNC)

    async def _run(job_record: JobRecord) -> None:
        init_engine(settings.database_url)
        job_record.progress = {"phase": "scanning_zim"}

        def on_progress(done: int, total: int) -> None:
            job_record.progress = {"phase": "syncing", "done": done, "total": total}

        async with get_session_factory()() as session:
            result = await sync_wordlist_to_sql(
                session,
                settings.zim_path,
                progress=on_progress,
            )
        job_record.progress = {
            "phase": "completed",
            "scanned": result.scanned,
            "inserted": result.inserted,
        }

    jobs.start_background(record.id, _run)
    return JobCreatedResponse(job_id=record.id)


@router.post("/wordlist/sync/wait", response_model=CatalogSyncResponse)
async def catalog_sync_wordlist_wait(
    settings: SettingsDep,
    session: DbSessionDep,
) -> CatalogSyncResponse:
    """Synchronous sync for small/dev use (may timeout on ~1M titles)."""
    if not settings.zim_path.is_file():
        raise HTTPException(status_code=503, detail="ZIM file not readable.")
    result = await sync_wordlist_to_sql(session, settings.zim_path)
    return CatalogSyncResponse(scanned=result.scanned, inserted=result.inserted)


@router.post("/extract", response_model=CatalogJobCreatedResponse, status_code=202)
async def catalog_extract_async(
    body: CatalogExtractSyncRequest,
    settings: SettingsDep,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobCreatedResponse:
    if not settings.zim_path.is_file():
        raise HTTPException(status_code=503, detail="ZIM file not readable.")
    record = jobs.create(JobKind.CATALOG_EXTRACT)

    async def _run(job_record: JobRecord) -> None:
        init_engine(settings.database_url)
        job_record.progress = {"phase": "extracting", "limit": body.limit}

        def on_progress(done: int, total: int) -> None:
            job_record.progress = {"phase": "extracting", "done": done, "total": total}

        async with get_session_factory()() as session:
            result = await extract_pending_wordlist(
                session,
                settings.zim_path,
                limit=body.limit,
                progress=on_progress,
            )
        job_record.progress = {
            "phase": "completed",
            "attempted": result.attempted,
            "extracted": result.extracted,
            "skipped": result.skipped,
            "failed": result.failed,
        }

    jobs.start_background(record.id, _run)
    return JobCreatedResponse(job_id=record.id)


@router.post("/extract/wait", response_model=CatalogExtractResponse)
async def catalog_extract_wait(
    body: CatalogExtractSyncRequest,
    settings: SettingsDep,
    session: DbSessionDep,
) -> CatalogExtractResponse:
    if not settings.zim_path.is_file():
        raise HTTPException(status_code=503, detail="ZIM file not readable.")
    result = await extract_pending_wordlist(
        session,
        settings.zim_path,
        limit=body.limit,
    )
    return CatalogExtractResponse(
        attempted=result.attempted,
        extracted=result.extracted,
        skipped=result.skipped,
        failed=result.failed,
    )


@router.get("/jobs/{job_id}", response_model=CatalogJobStatusResponse)
async def catalog_job_status(
    job_id: str,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> CatalogJobStatusResponse:
    record = jobs.get(job_id)
    if record is None or record.kind not in {
        JobKind.CATALOG_SYNC,
        JobKind.CATALOG_EXTRACT,
    }:
        raise HTTPException(status_code=404, detail="Catalog job not found.")
    return _job_response(record)
