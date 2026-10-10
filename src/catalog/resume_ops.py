"""Database helpers for catalog resume / retry."""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.db.models import WordlistExtractStatus, WordlistTitleModel
from src.repository.db.models.canonical import CanonicalExtractStatus, CanonicalLemmaModel


async def requeue_failed_canonical(session: AsyncSession) -> int:
    stmt = (
        update(CanonicalLemmaModel)
        .where(CanonicalLemmaModel.extract_status == CanonicalExtractStatus.FAILED.value)
        .values(extract_status=CanonicalExtractStatus.PENDING.value, last_error=None)
    )
    result = await session.execute(stmt)
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


async def requeue_failed_wordlist(session: AsyncSession, zim_uuid: str | None = None) -> int:
    stmt = update(WordlistTitleModel).where(
        WordlistTitleModel.extract_status == WordlistExtractStatus.FAILED.value
    )
    if zim_uuid is not None:
        stmt = stmt.where(WordlistTitleModel.zim_uuid == zim_uuid)
    stmt = stmt.values(
        extract_status=WordlistExtractStatus.PENDING.value,
        last_error=None,
    )
    result = await session.execute(stmt)
    await session.commit()
    return int(getattr(result, "rowcount", 0) or 0)
