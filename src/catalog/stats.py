from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.extraction.zim_reader import ZimReader
from src.repository.db.models import EntryModel, WordlistExtractStatus, WordlistTitleModel


@dataclass(frozen=True, slots=True)
class CatalogStats:
    zim_path: str
    zim_uuid: str | None
    zim_title_count: int
    wordlist_total: int
    wordlist_pending: int
    wordlist_extracted: int
    wordlist_skipped: int
    wordlist_failed: int
    entries_total: int


def count_zim_titles_sync(zim_path: Path) -> tuple[int, str | None]:
    if not zim_path.is_file():
        return 0, None
    reader = ZimReader(zim_path)
    return reader.count_article_titles(), str(reader.metadata().uuid)


async def fetch_catalog_stats(session: AsyncSession, zim_path: Path) -> CatalogStats:
    zim_title_count, zim_uuid = count_zim_titles_sync(zim_path)

    async def _count_status(status: WordlistExtractStatus) -> int:
        stmt = (
            select(func.count())
            .select_from(WordlistTitleModel)
            .where(WordlistTitleModel.extract_status == status.value)
        )
        return int((await session.execute(stmt)).scalar_one())

    wordlist_total = int(
        (await session.execute(select(func.count()).select_from(WordlistTitleModel))).scalar_one()
    )
    entries_total = int(
        (await session.execute(select(func.count()).select_from(EntryModel))).scalar_one()
    )

    return CatalogStats(
        zim_path=str(zim_path.resolve()),
        zim_uuid=zim_uuid,
        zim_title_count=zim_title_count,
        wordlist_total=wordlist_total,
        wordlist_pending=await _count_status(WordlistExtractStatus.PENDING),
        wordlist_extracted=await _count_status(WordlistExtractStatus.EXTRACTED),
        wordlist_skipped=await _count_status(WordlistExtractStatus.SKIPPED),
        wordlist_failed=await _count_status(WordlistExtractStatus.FAILED),
        entries_total=entries_total,
    )
