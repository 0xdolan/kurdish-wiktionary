import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.extraction.normalize import normalize_entry_key
from src.extraction.zim_reader import ZimReader
from src.repository.db.models import WordlistExtractStatus, WordlistTitleModel


@dataclass(frozen=True, slots=True)
class WordlistSyncResult:
    scanned: int
    inserted: int


def _iter_title_rows(zim_path: Path) -> list[dict[str, str]]:
    reader = ZimReader(zim_path)
    meta = reader.metadata()
    zim_uuid = str(meta.uuid)
    zim_path_str = str(meta.path)
    rows: list[dict[str, str]] = []
    for title in reader.iter_article_titles():
        rows.append(
            {
                "title": title,
                "title_normalized": normalize_entry_key(title),
                "zim_uuid": zim_uuid,
                "zim_path": zim_path_str,
                "extract_status": WordlistExtractStatus.PENDING.value,
            }
        )
    return rows


async def sync_wordlist_to_sql(
    session: AsyncSession,
    zim_path: Path,
    *,
    batch_size: int = 2000,
    progress: Callable[[int, int], None] | None = None,
) -> WordlistSyncResult:
    from sqlalchemy import func, select

    before = int(
        (await session.execute(select(func.count()).select_from(WordlistTitleModel))).scalar_one()
    )
    rows = await asyncio.to_thread(_iter_title_rows, zim_path)
    scanned = len(rows)
    for offset in range(0, scanned, batch_size):
        chunk = rows[offset : offset + batch_size]
        stmt = pg_insert(WordlistTitleModel).values(chunk)
        stmt = stmt.on_conflict_do_nothing(index_elements=["title_normalized", "zim_uuid"])
        await session.execute(stmt)
        await session.commit()
        if progress is not None:
            progress(min(offset + len(chunk), scanned), scanned)
    after = int(
        (await session.execute(select(func.count()).select_from(WordlistTitleModel))).scalar_one()
    )
    return WordlistSyncResult(scanned=scanned, inserted=max(0, after - before))
