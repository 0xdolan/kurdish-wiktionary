from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from src.api.deps import AppStateDep, DbSessionDep, SettingsDep
from src.api.schemas_catalog import (
    CanonicalExtractResponse,
    CanonicalStatsResponse,
    CanonicalSyncResponse,
    CatalogAuditResponse,
    CatalogExtractResponse,
    CatalogExtractSyncRequest,
    CatalogJobCreatedResponse,
    CatalogJobStatusResponse,
    CatalogStatsResponse,
    CatalogSyncResponse,
    OutcomeCategoryResponse,
    OutcomeReportResponse,
    OutcomeRowResponse,
    WordlistItemResponse,
    WordlistPageResponse,
    ZimFileStatsResponse,
)
from src.api.schemas_mdx import JobCreatedResponse
from src.catalog.audit import audit_canonical_extraction
from src.catalog.canonical_extract import extract_pending_canonical
from src.catalog.canonical_sync import sync_canonical_wordlist
from src.catalog.cli_progress import ProgressTick
from src.catalog.extract import extract_pending_wordlist
from src.catalog.outcomes import build_outcome_report
from src.catalog.stats import fetch_canonical_stats, fetch_catalog_stats, scan_all_zim_stats
from src.catalog.sync import sync_wordlist_to_sql
from src.catalog.zim_paths import resolve_zim_paths
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

        def on_progress(tick: ProgressTick) -> None:
            job_record.progress = {
                "phase": "syncing",
                "done": tick.done,
                "total": tick.total,
            }

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

        def on_progress(tick: ProgressTick) -> None:
            job_record.progress = {
                "phase": "extracting",
                "done": tick.done,
                "total": tick.total,
                "extracted": tick.extracted,
                "skipped": tick.skipped,
                "failed": tick.failed,
            }

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
        JobKind.CATALOG_CANONICAL_SYNC,
        JobKind.CATALOG_CANONICAL_EXTRACT,
    }:
        raise HTTPException(status_code=404, detail="Catalog job not found.")
    return _job_response(record)


@router.get("/canonical/stats", response_model=CanonicalStatsResponse)
async def catalog_canonical_stats(
    settings: SettingsDep,
    session: DbSessionDep,
) -> CanonicalStatsResponse:
    zim_paths = resolve_zim_paths(settings)
    zim_files = [
        ZimFileStatsResponse(path=r.path, uuid=r.uuid, title_count=r.title_count)
        for r in scan_all_zim_stats(zim_paths)
    ]
    stats = await fetch_canonical_stats(session, configured_zim_count=len(zim_paths))
    return CanonicalStatsResponse(
        zim_files=zim_files,
        total=stats.total,
        pending=stats.pending,
        extracted=stats.extracted,
        skipped=stats.skipped,
        failed=stats.failed,
        in_all_configured_zims=stats.in_all_configured_zims,
        in_one_zim_only=stats.in_one_zim_only,
        entries_total=stats.entries_total,
    )


@router.post("/canonical/sync", response_model=CatalogJobCreatedResponse, status_code=202)
async def catalog_canonical_sync_async(
    settings: SettingsDep,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobCreatedResponse:
    zim_paths = resolve_zim_paths(settings)
    for path in zim_paths:
        if not path.is_file():
            raise HTTPException(status_code=503, detail=f"ZIM not readable: {path}")
    record = jobs.create(JobKind.CATALOG_CANONICAL_SYNC)

    async def _run(job_record: JobRecord) -> None:
        init_engine(settings.database_url)
        job_record.progress = {"phase": "scanning_zims", "count": len(zim_paths)}

        def on_progress(tick: ProgressTick) -> None:
            job_record.progress = {
                "phase": "upserting",
                "done": tick.done,
                "total": tick.total,
            }

        async with get_session_factory()() as session:
            result = await sync_canonical_wordlist(
                session,
                zim_paths,
                progress=on_progress,
            )
        job_record.progress = {
            "phase": "completed",
            "unique_lemmas": result.unique_lemmas,
            "in_all_zims": result.in_all_zims,
        }

    jobs.start_background(record.id, _run)
    return JobCreatedResponse(job_id=record.id)


@router.post("/canonical/sync/wait", response_model=CanonicalSyncResponse)
async def catalog_canonical_sync_wait(
    settings: SettingsDep,
    session: DbSessionDep,
) -> CanonicalSyncResponse:
    zim_paths = resolve_zim_paths(settings)
    for path in zim_paths:
        if not path.is_file():
            raise HTTPException(status_code=503, detail=f"ZIM not readable: {path}")
    result = await sync_canonical_wordlist(session, zim_paths)
    return CanonicalSyncResponse(
        zim_files=result.zim_files,
        unique_lemmas=result.unique_lemmas,
        upserted=result.upserted,
        in_all_zims=result.in_all_zims,
        in_single_zim=result.in_single_zim,
    )


@router.post("/canonical/extract", response_model=CatalogJobCreatedResponse, status_code=202)
async def catalog_canonical_extract_async(
    body: CatalogExtractSyncRequest,
    settings: SettingsDep,
    jobs: Annotated[JobRegistry, Depends(_jobs)],
) -> JobCreatedResponse:
    zim_paths = resolve_zim_paths(settings)
    for path in zim_paths:
        if not path.is_file():
            raise HTTPException(status_code=503, detail=f"ZIM not readable: {path}")
    record = jobs.create(JobKind.CATALOG_CANONICAL_EXTRACT)

    async def _run(job_record: JobRecord) -> None:
        init_engine(settings.database_url)
        job_record.progress = {"phase": "extracting", "limit": body.limit}

        def on_progress(tick: ProgressTick) -> None:
            job_record.progress = {
                "phase": "extracting",
                "done": tick.done,
                "total": tick.total,
                "extracted": tick.extracted,
                "skipped": tick.skipped,
                "failed": tick.failed,
            }

        async with get_session_factory()() as session:
            result = await extract_pending_canonical(
                session,
                zim_paths,
                limit=body.limit,
                progress=on_progress,
            )
        job_record.progress = {
            "phase": "completed",
            "extracted": result.extracted,
            "skipped": result.skipped,
            "failed": result.failed,
        }

    jobs.start_background(record.id, _run)
    return JobCreatedResponse(job_id=record.id)


@router.post("/canonical/extract/wait", response_model=CanonicalExtractResponse)
async def catalog_canonical_extract_wait(
    body: CatalogExtractSyncRequest,
    settings: SettingsDep,
    session: DbSessionDep,
) -> CanonicalExtractResponse:
    zim_paths = resolve_zim_paths(settings)
    for path in zim_paths:
        if not path.is_file():
            raise HTTPException(status_code=503, detail=f"ZIM not readable: {path}")
    result = await extract_pending_canonical(
        session,
        zim_paths,
        limit=body.limit,
    )
    return CanonicalExtractResponse(
        attempted=result.attempted,
        extracted=result.extracted,
        skipped=result.skipped,
        failed=result.failed,
    )


@router.get("/audit", response_model=CatalogAuditResponse)
async def catalog_audit(session: DbSessionDep) -> CatalogAuditResponse:
    report = await audit_canonical_extraction(session)
    return CatalogAuditResponse(
        canonical_total=report.canonical_total,
        canonical_extracted=report.canonical_extracted,
        canonical_pending=report.canonical_pending,
        canonical_skipped=report.canonical_skipped,
        canonical_failed=report.canonical_failed,
        extracted_missing_entry_id=report.extracted_missing_entry_id,
        entries_with_html_entities=report.entries_with_html_entities,
        sample_entity_lemmas=report.sample_entity_lemmas,
    )


@router.get("/outcomes", response_model=OutcomeReportResponse)
async def catalog_outcome_report(
    session: DbSessionDep,
    scope: Annotated[Literal["canonical", "wordlist"], Query()] = "canonical",
    status: Annotated[Literal["both", "skipped", "failed"], Query()] = "both",
    limit: Annotated[int, Query(ge=1, le=5000)] = 200,
) -> OutcomeReportResponse:
    report = await build_outcome_report(
        session,
        scope=scope,
        status_filter=status,
        row_limit=limit,
    )
    return OutcomeReportResponse(
        scope=report.scope,
        generated_at=report.generated_at,
        skipped_total=report.skipped_total,
        failed_total=report.failed_total,
        categories=[
            OutcomeCategoryResponse(
                status=c.status,
                category=c.category,
                count=c.count,
                sample_titles=c.sample_titles,
            )
            for c in report.categories
        ],
        rows=[OutcomeRowResponse(**row.__dict__) for row in report.rows],
    )
