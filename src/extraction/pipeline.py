import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.models import WiktionaryEntry
from src.extraction.html_parser import parse_wiktionary_html
from src.extraction.zim_reader import ZimReader

logger = get_logger("uvicorn.error")


@dataclass(slots=True)
class PipelineStats:
    processed: int = 0
    skipped: int = 0
    failed: int = 0


@dataclass(slots=True)
class PipelineResult:
    stats: PipelineStats
    entries: list[WiktionaryEntry]


def _iter_parsed_sync(
    zim_path: Path,
    max_entries: int | None,
) -> tuple[Iterator[WiktionaryEntry], PipelineStats]:
    reader = ZimReader(zim_path)
    meta = reader.metadata()
    metadata_base = {
        "zim_uuid": meta.uuid,
        "zim_date": meta.date,
        "zim_source": meta.source,
        "zim_path": str(meta.path),
    }
    stats = PipelineStats()

    def generator() -> Iterator[WiktionaryEntry]:
        nonlocal stats
        for article in reader.iter_articles():
            if max_entries is not None and stats.processed >= max_entries:
                break
            try:
                parsed = parse_wiktionary_html(
                    article.title,
                    article.html,
                    metadata_base=dict(metadata_base),
                )
                if not parsed.definitions and not parsed.phonetic_transcriptions:
                    stats.skipped += 1
                    continue
                stats.processed += 1
                yield parsed
            except Exception:
                stats.failed += 1
                logger.exception("Failed to parse article %s", article.title)

    return generator(), stats


def _process_zim_sync(
    zim_path: Path,
    max_entries: int | None,
) -> PipelineResult:
    generator, stats = _iter_parsed_sync(zim_path, max_entries)
    entries = list(generator)
    return PipelineResult(stats=stats, entries=entries)


async def run_extraction_pipeline(
    zim_path: Path,
    *,
    max_entries: int | None = None,
) -> PipelineResult:
    return await asyncio.to_thread(_process_zim_sync, zim_path, max_entries)


async def iter_entries(
    zim_path: Path,
    *,
    max_entries: int | None = None,
) -> AsyncIterator[WiktionaryEntry]:
    generator, _stats = await asyncio.to_thread(_iter_parsed_sync, zim_path, max_entries)
    for entry in generator:
        yield entry


async def ingest_zim_to_session(
    zim_path: Path,
    session: AsyncSession,
    *,
    max_entries: int | None = None,
    batch_size: int = 200,
) -> PipelineStats:
    from src.repository.db.upsert import upsert_entry

    generator, stats = await asyncio.to_thread(_iter_parsed_sync, zim_path, max_entries)
    batch: list[WiktionaryEntry] = []
    for entry in generator:
        batch.append(entry)
        if len(batch) >= batch_size:
            for item in batch:
                await upsert_entry(session, item)
            await session.commit()
            batch.clear()
    if batch:
        for item in batch:
            await upsert_entry(session, item)
        await session.commit()
    return stats
