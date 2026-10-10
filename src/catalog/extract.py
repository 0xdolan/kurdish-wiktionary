import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.cli_progress import ProgressTick
from src.catalog.outcomes import LemmaOutcome, lemma_outcome_from_row
from src.core.models import WiktionaryEntry
from src.extraction.html_parser import parse_wiktionary_html
from src.extraction.zim_reader import get_zim_reader
from src.repository.db.models import WordlistExtractStatus, WordlistTitleModel
from src.repository.db.upsert import upsert_entry


@dataclass(frozen=True, slots=True)
class ExtractBatchResult:
    attempted: int
    extracted: int
    skipped: int
    failed: int
    outcomes: list[LemmaOutcome]


def _parse_article_sync(
    zim_path: Path,
    title: str,
) -> tuple[WiktionaryEntry | None, str | None]:
    reader = get_zim_reader(zim_path)
    meta = reader.metadata()
    metadata_base = {
        "zim_uuid": meta.uuid,
        "zim_date": meta.date,
        "zim_source": meta.source,
        "zim_path": str(meta.path),
        "content_format": "raw_text",
    }
    article = reader.get_article_by_title(title)
    if article is None:
        return None, "Article not found in ZIM"
    try:
        parsed = parse_wiktionary_html(
            article.title,
            article.html,
            metadata_base=dict(metadata_base),
        )
    except Exception as exc:  # noqa: BLE001 — per-row boundary
        return None, str(exc)
    if not parsed.definitions and not parsed.phonetic_transcriptions:
        return None, "No definitions or phonetics"
    return parsed, None


async def extract_pending_wordlist(
    session: AsyncSession,
    zim_path: Path,
    *,
    limit: int = 100,
    include_failed: bool = False,
    progress: Callable[[ProgressTick], None] | None = None,
) -> ExtractBatchResult:
    statuses = [WordlistExtractStatus.PENDING.value]
    if include_failed:
        statuses.append(WordlistExtractStatus.FAILED.value)
    stmt = (
        select(WordlistTitleModel)
        .where(WordlistTitleModel.extract_status.in_(statuses))
        .order_by(WordlistTitleModel.id.asc())
        .limit(max(1, limit))
    )
    rows = (await session.execute(stmt)).scalars().all()
    total = len(rows)
    extracted = skipped = failed = 0
    outcomes: list[LemmaOutcome] = []

    for index, row in enumerate(rows, start=1):
        entry, error = await asyncio.to_thread(_parse_article_sync, zim_path, row.title)
        now = datetime.now(tz=UTC)
        if entry is None:
            if error and (
                "No definitions" in error or "Article not found in ZIM" in error
            ):
                row.extract_status = WordlistExtractStatus.SKIPPED.value
                row.last_error = error
                skipped += 1
                outcomes.append(
                    lemma_outcome_from_row(
                        title=row.title,
                        title_normalized=row.title_normalized,
                        status=WordlistExtractStatus.SKIPPED.value,
                        last_error=error,
                    )
                )
            else:
                row.extract_status = WordlistExtractStatus.FAILED.value
                row.last_error = error
                failed += 1
                outcomes.append(
                    lemma_outcome_from_row(
                        title=row.title,
                        title_normalized=row.title_normalized,
                        status=WordlistExtractStatus.FAILED.value,
                        last_error=error,
                    )
                )
        else:
            entry_row = await upsert_entry(session, entry)
            row.extract_status = WordlistExtractStatus.EXTRACTED.value
            row.entry_id = entry_row.id
            row.last_error = None
            row.extracted_at = now
            extracted += 1
        await session.commit()
        if progress is not None:
            progress(
                ProgressTick(
                    done=index,
                    total=total,
                    extracted=extracted,
                    skipped=skipped,
                    failed=failed,
                )
            )

    return ExtractBatchResult(
        attempted=total,
        extracted=extracted,
        skipped=skipped,
        failed=failed,
        outcomes=outcomes,
    )
