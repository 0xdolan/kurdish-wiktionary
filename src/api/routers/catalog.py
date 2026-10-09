from dataclasses import asdict
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from src.api.deps import DbSessionDep, SettingsDep
from src.api.schemas_catalog import (
    CatalogExtractRequest,
    CatalogExtractResponse,
    CatalogStatsResponse,
    CatalogSyncResponse,
    WordlistItemResponse,
    WordlistPageResponse,
)
from src.catalog.extract import extract_pending_wordlist
from src.catalog.stats import fetch_catalog_stats
from src.catalog.sync import sync_wordlist_to_sql
from src.repository.db.models import WordlistTitleModel

router = APIRouter(prefix="/catalog", tags=["catalog"])


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


@router.post("/wordlist/sync", response_model=CatalogSyncResponse)
async def catalog_sync_wordlist(
    settings: SettingsDep,
    session: DbSessionDep,
) -> CatalogSyncResponse:
    if not settings.zim_path.is_file():
        raise HTTPException(status_code=503, detail="ZIM file not readable.")
    result = await sync_wordlist_to_sql(session, settings.zim_path)
    return CatalogSyncResponse(scanned=result.scanned, inserted=result.inserted)


@router.post("/extract", response_model=CatalogExtractResponse)
async def catalog_extract_batch(
    body: CatalogExtractRequest,
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
