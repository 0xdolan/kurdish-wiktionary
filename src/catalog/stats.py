from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.extraction.zim_reader import ZimReader
from src.repository.db.models import EntryModel, WordlistExtractStatus, WordlistTitleModel
from src.repository.db.models.canonical import CanonicalExtractStatus, CanonicalLemmaModel


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


@dataclass(frozen=True, slots=True)
class ZimFileStats:
    path: str
    uuid: str | None
    title_count: int


@dataclass(frozen=True, slots=True)
class CanonicalStats:
    total: int
    pending: int
    extracted: int
    skipped: int
    failed: int
    in_all_configured_zims: int
    in_one_zim_only: int
    entries_total: int


def scan_all_zim_stats(zim_paths: list[Path]) -> list[ZimFileStats]:
    result: list[ZimFileStats] = []
    for path in zim_paths:
        count, uuid = count_zim_titles_sync(path)
        result.append(ZimFileStats(path=str(path.resolve()), uuid=uuid, title_count=count))
    return result


async def fetch_canonical_stats(
    session: AsyncSession,
    *,
    configured_zim_count: int,
) -> CanonicalStats:
    async def _status(status: CanonicalExtractStatus) -> int:
        stmt = (
            select(func.count())
            .select_from(CanonicalLemmaModel)
            .where(CanonicalLemmaModel.extract_status == status.value)
        )
        return int((await session.execute(stmt)).scalar_one())

    total = int(
        (await session.execute(select(func.count()).select_from(CanonicalLemmaModel))).scalar_one()
    )
    in_all = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CanonicalLemmaModel)
                .where(CanonicalLemmaModel.source_count >= configured_zim_count)
            )
        ).scalar_one()
    )
    in_one = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CanonicalLemmaModel)
                .where(CanonicalLemmaModel.source_count == 1)
            )
        ).scalar_one()
    )
    entries_total = int(
        (await session.execute(select(func.count()).select_from(EntryModel))).scalar_one()
    )
    return CanonicalStats(
        total=total,
        pending=await _status(CanonicalExtractStatus.PENDING),
        extracted=await _status(CanonicalExtractStatus.EXTRACTED),
        skipped=await _status(CanonicalExtractStatus.SKIPPED),
        failed=await _status(CanonicalExtractStatus.FAILED),
        in_all_configured_zims=in_all,
        in_one_zim_only=in_one,
        entries_total=entries_total,
    )
