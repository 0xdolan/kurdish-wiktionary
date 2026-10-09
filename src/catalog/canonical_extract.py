import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.zim_paths import sort_zim_paths_for_extract
from src.core.models import WiktionaryEntry
from src.extraction.parse_page import ParsedPage, parse_wiktionary_page
from src.extraction.zim_reader import ZimReader
from src.repository.db.models.canonical import CanonicalExtractStatus, CanonicalLemmaModel
from src.repository.db.upsert import upsert_entry
from src.repository.db.upsert_assets import replace_entry_media, upsert_entry_html


@dataclass(frozen=True, slots=True)
class CanonicalExtractBatchResult:
    attempted: int
    extracted: int
    skipped: int
    failed: int


def _parse_from_zim(
    zim_path: Path,
    title: str,
) -> tuple[WiktionaryEntry | None, str | None, ParsedPage | None, list[ParsedPage]]:
    reader = ZimReader(zim_path)
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
        return None, "Article not found in ZIM", None, []
    try:
        page = parse_wiktionary_page(
            article.title,
            article.html,
            metadata_base=dict(metadata_base),
        )
    except Exception as exc:  # noqa: BLE001
        return None, str(exc), None, []
    if not page.entry.definitions and not page.entry.phonetic_transcriptions:
        return None, "No definitions or phonetics", page, [page]
    return page.entry, None, page, [page]


def _merge_entries(primary: WiktionaryEntry, others: list[WiktionaryEntry]) -> WiktionaryEntry:
    def union(field: str) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for ent in (primary, *others):
            for item in getattr(ent, field):
                if item and item not in seen:
                    seen.add(item)
                    out.append(item)
        return out

    zim_variants: list[dict[str, Any]] = []
    for ent in (primary, *others):
        zim_variants.append(
            {
                "zim_uuid": ent.metadata.get("zim_uuid"),
                "zim_path": ent.metadata.get("zim_path"),
                "definition_count": len(ent.definitions),
            }
        )

    metadata = dict(primary.metadata)
    metadata["zim_variants"] = zim_variants
    metadata["merged_from_zims"] = len(zim_variants)

    etymology = primary.etymology
    for ent in others:
        if not etymology and ent.etymology:
            etymology = ent.etymology

    return WiktionaryEntry(
        entry=primary.entry,
        part_of_speech=union("part_of_speech"),
        definitions=union("definitions"),
        phonetic_transcriptions=union("phonetic_transcriptions"),
        pronunciations=union("pronunciations"),
        examples=union("examples"),
        synonyms=union("synonyms"),
        antonyms=union("antonyms"),
        etymology=etymology,
        derived_terms=union("derived_terms"),
        metadata=metadata,
    )


def _extract_lemma_sync(
    row: CanonicalLemmaModel,
    zim_paths: list[Path],
) -> tuple[WiktionaryEntry | None, str | None, ParsedPage | None, list[ParsedPage]]:
    sources: dict[str, dict[str, str]] = dict(row.zim_sources or {})

    parsed_entries: list[WiktionaryEntry] = []
    parsed_pages: list[ParsedPage] = []
    errors: list[str] = []
    ordered_paths = sort_zim_paths_for_extract(zim_paths)

    for zim_path in ordered_paths:
        source = None
        for item in sources.values():
            if item.get("zim_path") == str(zim_path.resolve()):
                source = item
                break
        if source is None:
            continue
        entry, err, page, pages = _parse_from_zim(zim_path, source["title"])
        if pages:
            parsed_pages.extend(pages)
        if entry is not None:
            parsed_entries.append(entry)
        elif err:
            errors.append(f"{zim_path.name}: {err}")

    if not parsed_entries:
        if errors and all("No definitions" in e for e in errors):
            return None, "No definitions or phonetics", None, parsed_pages
        err = errors[0] if errors else "No ZIM source matched configured paths"
        return None, err, None, parsed_pages

    primary = parsed_entries[0]
    primary_page = parsed_pages[0] if parsed_pages else None
    if len(parsed_entries) == 1:
        primary.metadata["merged_from_zims"] = 1
        return primary, None, primary_page, parsed_pages
    merged = _merge_entries(primary, parsed_entries[1:])
    return merged, None, primary_page, parsed_pages


async def extract_pending_canonical(
    session: AsyncSession,
    zim_paths: list[Path],
    *,
    limit: int = 100,
    progress: Callable[[int, int], None] | None = None,
) -> CanonicalExtractBatchResult:
    stmt = (
        select(CanonicalLemmaModel)
        .where(CanonicalLemmaModel.extract_status == CanonicalExtractStatus.PENDING.value)
        .order_by(CanonicalLemmaModel.title_normalized.asc())
        .limit(max(1, limit))
    )
    rows = (await session.execute(stmt)).scalars().all()
    total = len(rows)
    extracted = skipped = failed = 0

    for index, row in enumerate(rows, start=1):
        entry, error, page, parsed_pages = await asyncio.to_thread(
            _extract_lemma_sync,
            row,
            zim_paths,
        )
        now = datetime.now(tz=UTC)
        if entry is None:
            if error and "No definitions" in error:
                row.extract_status = CanonicalExtractStatus.SKIPPED.value
                row.last_error = error
                skipped += 1
            else:
                row.extract_status = CanonicalExtractStatus.FAILED.value
                row.last_error = error
                failed += 1
        else:
            entry_row = await upsert_entry(session, entry)
            if page is not None:
                await upsert_entry_html(
                    session,
                    entry_row.id,
                    html_full=page.html_full,
                    section_html=page.section_html,
                )
                merged_media: list[dict[str, Any]] = []
                seen_urls: set[str] = set()
                for p in parsed_pages:
                    for item in p.media:
                        url = str(item.get("url", ""))
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            merged_media.append(item)
                await replace_entry_media(session, entry_row.id, merged_media)
            row.extract_status = CanonicalExtractStatus.EXTRACTED.value
            row.entry_id = entry_row.id
            row.last_error = None
            row.extracted_at = now
            extracted += 1
        await session.commit()
        if progress is not None:
            progress(index, total)

    return CanonicalExtractBatchResult(
        attempted=total,
        extracted=extracted,
        skipped=skipped,
        failed=failed,
    )
