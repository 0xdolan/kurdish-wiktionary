import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.catalog.cli_progress import CatalogJobProgress, ProgressTick
from src.catalog.zim_paths import resolve_zim_paths, sort_zim_paths_for_extract
from src.config import Settings
from src.core.models import WiktionaryEntry
from src.extraction.normalize import normalize_entry_key
from src.extraction.parse_page import parse_wiktionary_page
from src.extraction.zim_media import local_media_relative_path, resolve_media_href
from src.extraction.zim_reader import ZimReader
from src.lexicon.media_download import download_media_item
from src.lexicon.media_run_log import MediaDownloadRunLogger
from src.repository.db.mappers import entry_model_to_schema
from src.repository.db.models import EntryModel
from src.repository.db.models.entry import (
    EntryAntonymRow,
    EntryDefinitionRow,
    EntryDerivedTermRow,
    EntryExampleRow,
    EntryPartOfSpeechRow,
    EntryPhoneticRow,
    EntryPronunciationRow,
    EntrySynonymRow,
)
from src.repository.db.models.entry_assets import EntryHtmlModel, EntryMediaModel
from src.repository.db.upsert import upsert_entry
from src.repository.db.upsert_assets import get_entry_html, replace_entry_media, upsert_entry_html

FieldName = Literal[
    "definitions",
    "synonyms",
    "antonyms",
    "examples",
    "pronunciations",
    "phonetic_transcriptions",
    "derived_terms",
    "part_of_speech",
]


@dataclass(frozen=True, slots=True)
class PreviewResult:
    title: str
    entry: WiktionaryEntry
    html_bytes: int
    section_html_keys: list[str]
    media_count: int
    media: list[dict[str, Any]]
    counts: dict[str, int]
    warnings: list[str]


def _field_values(entry: WiktionaryEntry, field: FieldName) -> list[str]:
    return list(getattr(entry, field))


def _count_fields(entry: WiktionaryEntry) -> dict[str, int]:
    return {
        "definitions": len(entry.definitions),
        "synonyms": len(entry.synonyms),
        "antonyms": len(entry.antonyms),
        "examples": len(entry.examples),
        "pronunciations": len(entry.pronunciations),
        "phonetic_transcriptions": len(entry.phonetic_transcriptions),
        "derived_terms": len(entry.derived_terms),
        "part_of_speech": len(entry.part_of_speech),
    }


def _preview_warnings(counts: dict[str, int]) -> list[str]:
    warnings: list[str] = []
    if counts["definitions"] == 0 and counts["phonetic_transcriptions"] == 0:
        warnings.append("no_definitions_or_phonetics")
    if counts["synonyms"] == 0:
        warnings.append("synonyms_empty")
    if counts["antonyms"] == 0:
        warnings.append("antonyms_empty")
    return warnings


async def _load_entry_row(session: AsyncSession, word: str) -> EntryModel | None:
    normalized = normalize_entry_key(word)
    stmt = (
        select(EntryModel)
        .where(EntryModel.entry_normalized == normalized)
        .options(
            selectinload(EntryModel.definitions),
            selectinload(EntryModel.examples),
            selectinload(EntryModel.synonyms),
            selectinload(EntryModel.antonyms),
            selectinload(EntryModel.phonetics),
            selectinload(EntryModel.pronunciations),
            selectinload(EntryModel.derived_terms),
            selectinload(EntryModel.parts_of_speech),
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


@dataclass(frozen=True, slots=True)
class ZimArticlePayload:
    html: str
    zim_path: str
    article_path: str


def _fetch_zim_article(settings: Settings, word: str) -> ZimArticlePayload:
    for zim_path in sort_zim_paths_for_extract(resolve_zim_paths(settings)):
        reader = ZimReader(zim_path)
        article = reader.get_article_by_title(word)
        if article is not None:
            return ZimArticlePayload(
                html=article.html,
                zim_path=str(zim_path),
                article_path=article.path,
            )
    raise LookupError(f"Lemma not found in configured ZIM files: {word}")


def _enrich_media_urls(
    media: list[dict[str, Any]],
    *,
    zim_path: str,
    article_path: str,
    entry_normalized: str,
) -> list[dict[str, Any]]:
    reader = ZimReader(Path(zim_path))
    enriched: list[dict[str, Any]] = []
    for item in media:
        url = str(item.get("url", ""))
        kind = str(item.get("kind", "other"))
        resolved = resolve_media_href(
            article_zim_path=article_path,
            href=url,
            has_zim_path=reader.has_path,
        )
        row = dict(item)
        row["resolve"] = resolved
        row["local_relative_path"] = local_media_relative_path(
            entry_normalized=entry_normalized,
            kind=kind,
            url=url,
        )
        enriched.append(row)
    return enriched


async def preview_entry(settings: Settings, word: str) -> PreviewResult:
    payload = await asyncio.to_thread(_fetch_zim_article, settings, word)
    meta = ZimReader(Path(payload.zim_path)).metadata()
    page = parse_wiktionary_page(
        word,
        payload.html,
        metadata_base={
            "zim_uuid": meta.uuid,
            "zim_path": payload.zim_path,
            "preview": True,
        },
    )
    counts = _count_fields(page.entry)
    normalized = normalize_entry_key(word)
    media = _enrich_media_urls(
        page.media,
        zim_path=payload.zim_path,
        article_path=payload.article_path,
        entry_normalized=normalized,
    )
    return PreviewResult(
        title=word,
        entry=page.entry,
        html_bytes=len(payload.html.encode("utf-8")),
        section_html_keys=sorted(page.section_html.keys()),
        media_count=len(media),
        media=media,
        counts=counts,
        warnings=_preview_warnings(counts),
    )


async def extract_entry_confirmed(
    session: AsyncSession,
    settings: Settings,
    word: str,
) -> EntryModel:
    payload = await asyncio.to_thread(_fetch_zim_article, settings, word)
    meta = ZimReader(Path(payload.zim_path)).metadata()
    page = parse_wiktionary_page(
        word,
        payload.html,
        metadata_base={
            "zim_uuid": meta.uuid,
            "zim_date": meta.date,
            "zim_source": meta.source,
            "zim_path": payload.zim_path,
        },
    )
    row = await upsert_entry(session, page.entry)
    await upsert_entry_html(
        session,
        row.id,
        html_full=page.html_full,
        section_html=page.section_html,
    )
    await replace_entry_media(session, row.id, page.media)
    await session.commit()
    return row


async def list_field_values(
    session: AsyncSession,
    field: FieldName,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    rows, total = await list_entries(session, limit=limit, offset=offset)
    items = [{"entry": row.entry, "values": _field_values(row, field)} for row in rows]
    return items, total


async def list_entries(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[WiktionaryEntry], int]:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    total = int((await session.execute(select(func.count()).select_from(EntryModel))).scalar_one())
    stmt = (
        select(EntryModel)
        .order_by(EntryModel.entry_normalized.asc())
        .offset(safe_offset)
        .limit(safe_limit)
        .options(
            selectinload(EntryModel.definitions),
            selectinload(EntryModel.examples),
            selectinload(EntryModel.synonyms),
            selectinload(EntryModel.antonyms),
            selectinload(EntryModel.phonetics),
            selectinload(EntryModel.pronunciations),
            selectinload(EntryModel.derived_terms),
            selectinload(EntryModel.parts_of_speech),
        )
    )
    db_rows = (await session.execute(stmt)).scalars().all()
    return [entry_model_to_schema(r) for r in db_rows], total


async def get_entry(session: AsyncSession, word: str) -> WiktionaryEntry | None:
    row = await _load_entry_row(session, word)
    if row is None:
        return None
    return entry_model_to_schema(row)


async def get_entry_field(
    session: AsyncSession,
    word: str,
    field: FieldName,
) -> list[str] | None:
    row = await _load_entry_row(session, word)
    if row is None:
        return None
    schema = entry_model_to_schema(row)
    return _field_values(schema, field)


async def get_entry_html_full(session: AsyncSession, word: str) -> str | None:
    row = await _load_entry_row(session, word)
    if row is None:
        return None
    html_row = await get_entry_html(session, row.id)
    if html_row is not None:
        return html_row.html_full
    return None


async def get_entry_html_section(session: AsyncSession, word: str, section: str) -> str | None:
    row = await _load_entry_row(session, word)
    if row is None:
        return None
    html_row = await get_entry_html(session, row.id)
    if html_row is None:
        return None
    key = section.casefold()
    for stored_key, fragment in html_row.section_html.items():
        if stored_key == key or stored_key.replace(" ", "") == key.replace(" ", ""):
            return str(fragment)
    return None


async def list_entry_media(session: AsyncSession, word: str) -> list[dict[str, Any]] | None:
    row = await _load_entry_row(session, word)
    if row is None:
        return None
    stmt = select(EntryMediaModel).where(EntryMediaModel.entry_id == row.id)
    media_rows = (await session.execute(stmt)).scalars().all()
    return [
        {"kind": m.kind, "url": m.url, "local_path": m.local_path, "extra": m.extra}
        for m in media_rows
    ]


async def list_sparse_entries(
    session: AsyncSession,
    *,
    limit: int,
    mode: Literal["all_empty", "missing_relations"] = "missing_relations",
) -> list[dict[str, Any]]:
    stmt = (
        select(EntryModel)
        .options(
            selectinload(EntryModel.definitions),
            selectinload(EntryModel.synonyms),
            selectinload(EntryModel.antonyms),
        )
        .order_by(EntryModel.entry_normalized.asc())
        .limit(max(1, min(limit, 500)))
    )
    rows = (await session.execute(stmt)).scalars().all()
    sparse: list[dict[str, Any]] = []
    for row in rows:
        has_defs = bool(row.definitions)
        has_syn = bool(row.synonyms)
        has_ant = bool(row.antonyms)
        if mode == "all_empty":
            if has_defs or has_syn or has_ant:
                continue
            sparse.append(
                {
                    "entry": row.entry,
                    "entry_id": row.id,
                    "reason": "definitions_synonyms_antonyms_all_empty",
                }
            )
            continue
        if has_defs and not has_syn and not has_ant:
            sparse.append(
                {
                    "entry": row.entry,
                    "entry_id": row.id,
                    "reason": "definitions_present_relations_empty",
                }
            )
    return sparse


async def export_entries_json(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> str:
    rows, _ = await list_entries(session, limit=limit, offset=offset)
    payload = [row.model_dump() for row in rows]
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def export_entries_txt(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> str:
    rows, _ = await list_entries(session, limit=limit, offset=offset)
    lines: list[str] = []
    for row in rows:
        lines.append(f"=== {row.entry} ===")
        for definition in row.definitions:
            lines.append(f"  - {definition}")
        if row.synonyms:
            lines.append(f"  synonyms: {', '.join(row.synonyms)}")
        if row.antonyms:
            lines.append(f"  antonyms: {', '.join(row.antonyms)}")
        lines.append("")
    return "\n".join(lines)


async def zim_field_preview(
    settings: Settings,
    word: str,
    field: FieldName,
) -> dict[str, Any]:
    """Parse ZIM live; no database write — use before ``extract?confirm=true``."""
    preview = await preview_entry(settings, word)
    values = _field_values(preview.entry, field)
    return {
        "entry": word,
        "field": field,
        "values": values,
        "count": len(values),
        "source": "zim",
        "warnings": preview.warnings,
    }


async def zim_html_full(settings: Settings, word: str) -> dict[str, str]:
    payload = await asyncio.to_thread(_fetch_zim_article, settings, word)
    return {"entry": word, "html": payload.html, "source": "zim"}


async def zim_html_section(settings: Settings, word: str, section: str) -> dict[str, str] | None:
    payload = await asyncio.to_thread(_fetch_zim_article, settings, word)
    page = parse_wiktionary_page(word, payload.html)
    key = section.casefold()
    for stored_key, fragment in page.section_html.items():
        if stored_key == key or stored_key.replace(" ", "") == key.replace(" ", ""):
            return {"entry": word, "section": section, "html": fragment, "source": "zim"}
    return None


async def list_stored_html_index(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    count_stmt = select(func.count()).select_from(EntryHtmlModel)
    total = int((await session.execute(count_stmt)).scalar_one())
    stmt = (
        select(EntryHtmlModel, EntryModel.entry)
        .join(EntryModel, EntryModel.id == EntryHtmlModel.entry_id)
        .order_by(EntryModel.entry_normalized.asc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    rows = (await session.execute(stmt)).all()
    items = [
        {
            "entry": entry,
            "html_bytes": len(html_row.html_full.encode("utf-8")),
            "section_keys": sorted(html_row.section_html.keys()),
        }
        for html_row, entry in rows
    ]
    return items, total


async def list_stored_section_html_corpus(
    session: AsyncSession,
    section: str,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    key = section.casefold()
    stmt = (
        select(EntryHtmlModel, EntryModel.entry)
        .join(EntryModel, EntryModel.id == EntryHtmlModel.entry_id)
        .order_by(EntryModel.entry_normalized.asc())
    )
    all_rows = (await session.execute(stmt)).all()
    corpus: list[dict[str, Any]] = []
    for html_row, entry in all_rows:
        for stored_key, fragment in html_row.section_html.items():
            if stored_key == key or stored_key.replace(" ", "") == key.replace(" ", ""):
                corpus.append({"entry": entry, "section": section, "html": str(fragment)})
    return corpus[safe_offset : safe_offset + safe_limit], len(corpus)


async def list_stored_html_pages(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    include_html: bool,
) -> tuple[list[dict[str, Any]], int]:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    count_stmt = select(func.count()).select_from(EntryHtmlModel)
    total = int((await session.execute(count_stmt)).scalar_one())
    stmt = (
        select(EntryHtmlModel, EntryModel.entry)
        .join(EntryModel, EntryModel.id == EntryHtmlModel.entry_id)
        .order_by(EntryModel.entry_normalized.asc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    rows = (await session.execute(stmt)).all()
    items: list[dict[str, Any]] = []
    for html_row, entry in rows:
        item: dict[str, Any] = {
            "entry": entry,
            "html_bytes": len(html_row.html_full.encode("utf-8")),
            "section_keys": sorted(html_row.section_html.keys()),
        }
        if include_html:
            item["html"] = html_row.html_full
        items.append(item)
    return items, total


async def list_media_corpus(
    session: AsyncSession,
    *,
    kind: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    safe_limit = max(1, min(limit, 500))
    safe_offset = max(0, offset)
    count_stmt = select(func.count()).select_from(EntryMediaModel)
    list_stmt = select(EntryMediaModel, EntryModel.entry).join(
        EntryModel,
        EntryModel.id == EntryMediaModel.entry_id,
    )
    if kind:
        count_stmt = count_stmt.where(EntryMediaModel.kind == kind)
        list_stmt = list_stmt.where(EntryMediaModel.kind == kind)
    total = int((await session.execute(count_stmt)).scalar_one())
    stmt = (
        list_stmt.order_by(EntryModel.entry_normalized.asc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    rows = (await session.execute(stmt)).all()
    items = [
        {
            "entry": entry,
            "kind": media.kind,
            "url": media.url,
            "local_path": media.local_path,
            "extra": media.extra,
        }
        for media, entry in rows
    ]
    return items, total


_CHILD_TABLES: dict[str, type[Any]] = {
    "definitions": EntryDefinitionRow,
    "synonyms": EntrySynonymRow,
    "antonyms": EntryAntonymRow,
    "examples": EntryExampleRow,
    "pronunciations": EntryPronunciationRow,
    "phonetic_transcriptions": EntryPhoneticRow,
    "derived_terms": EntryDerivedTermRow,
    "part_of_speech": EntryPartOfSpeechRow,
}


async def duplicate_field_diagnostics(
    session: AsyncSession,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    """Rows where the same ``value`` appears more than once for one entry."""
    safe_limit = max(1, min(limit, 500))
    findings: list[dict[str, Any]] = []
    for field, table in _CHILD_TABLES.items():
        stmt = (
            select(
                table.entry_id,
                table.value,
                func.count().label("copies"),
            )
            .group_by(table.entry_id, table.value)
            .having(func.count() > 1)
            .limit(safe_limit)
        )
        for entry_id, value, copies in (await session.execute(stmt)).all():
            findings.append(
                {
                    "field": field,
                    "entry_id": entry_id,
                    "value": value,
                    "copies": int(copies),
                }
            )
            if len(findings) >= safe_limit:
                return findings
    return findings


def _media_file_exists(export_dir: Path, local_path: str | None) -> bool:
    if not local_path:
        return False
    return (export_dir / local_path).is_file()


def _committed_media_local_path(
    export_dir: Path,
    *,
    entry_normalized: str,
    kind: str,
    url: str,
    db_local_path: str | None,
) -> str | None:
    if db_local_path and _media_file_exists(export_dir, db_local_path):
        return db_local_path
    rel = local_media_relative_path(entry_normalized=entry_normalized, kind=kind, url=url)
    if _media_file_exists(export_dir, rel):
        return rel
    return None


async def _download_media_rows_for_entry(
    session: AsyncSession,
    settings: Settings,
    row: EntryModel,
    *,
    missing_only: bool,
    failure_logger: MediaDownloadRunLogger | None = None,
) -> dict[str, Any]:
    payload = await asyncio.to_thread(_fetch_zim_article, settings, row.entry)
    items = await list_entry_media(session, row.entry) or []
    if not items:
        page = parse_wiktionary_page(row.entry, payload.html)
        items = page.media

    export_dir = settings.media_export_dir
    results: list[dict[str, Any]] = []
    skipped = 0
    for item in items:
        url = str(item.get("url", ""))
        kind = str(item.get("kind", "other"))
        db_local_path = item.get("local_path")
        committed = _committed_media_local_path(
            export_dir,
            entry_normalized=row.entry_normalized,
            kind=kind,
            url=url,
            db_local_path=str(db_local_path) if db_local_path else None,
        )
        if missing_only and committed and db_local_path and committed == db_local_path:
            skipped += 1
            results.append({**item, "status": "skipped", "local_path": committed})
            continue

        outcome = await download_media_item(
            export_dir=export_dir,
            entry_normalized=row.entry_normalized,
            kind=kind,
            url=url,
            zim_path=Path(payload.zim_path),
            article_zim_path=payload.article_path,
            reuse_if_same_size=missing_only,
        )
        merged = {**item, **outcome}
        if outcome.get("status") == "reused":
            merged["status"] = "skipped"
            merged["local_path"] = outcome.get("local_path")
            skipped += 1
        elif outcome.get("local_path"):
            merged["status"] = "downloaded"
        else:
            merged["status"] = "failed"
            if failure_logger is not None:
                failure_logger.log_failure(
                    {
                        "entry": row.entry,
                        "entry_id": row.id,
                        "url": url,
                        "kind": kind,
                        "error": outcome.get("error"),
                        "source": outcome.get("source"),
                    }
                )
        results.append(merged)

    for item in results:
        local_path = item.get("local_path")
        if not local_path or item.get("status") == "failed":
            continue
        stmt = select(EntryMediaModel).where(
            EntryMediaModel.entry_id == row.id,
            EntryMediaModel.url == item.get("url"),
        )
        media_row = (await session.execute(stmt)).scalar_one_or_none()
        if media_row is not None:
            media_row.local_path = str(local_path)
            byte_size = item.get("bytes")
            if byte_size is not None:
                media_row.extra = {**media_row.extra, "bytes": int(byte_size)}

    return {
        "entry": row.entry,
        "entry_id": row.id,
        "items": results,
        "skipped": skipped,
        "export_dir": str(export_dir),
    }


@dataclass(frozen=True, slots=True)
class MediaDownloadProgressHooks:
    on_batch_start: Callable[..., None] | None = None
    on_tick: Callable[[ProgressTick], None] | None = None
    on_batch_finish: Callable[..., None] | None = None


def build_media_download_rich_hooks(
    job: CatalogJobProgress,
    *,
    run_all: bool,
) -> MediaDownloadProgressHooks:
    """Wire ``CatalogJobProgress`` to :func:`download_all_entry_media` callbacks."""

    def on_batch_start(
        *,
        batch_index: int,
        batch_total: int | None,
        item_total: int,
        corpus_pending: int,
        entries_pending: int | None,
    ) -> None:
        job.start_batch(
            batch_index=batch_index,
            batch_total=batch_total if run_all else 1,
            item_total=item_total,
            corpus_pending=corpus_pending,
        )

    def on_batch_finish(
        *,
        entries_selected: int,
        items_downloaded: int,
        items_skipped: int,
        items_failed: int,
        **_: object,
    ) -> None:
        job.finish_batch(
            attempted=entries_selected,
            extracted=items_downloaded,
            skipped=items_skipped,
            failed=items_failed,
        )

    return MediaDownloadProgressHooks(
        on_batch_start=on_batch_start,
        on_tick=job.on_tick,
        on_batch_finish=on_batch_finish,
    )


async def _count_entries_for_media_download(
    session: AsyncSession,
    *,
    missing_only: bool,
) -> int:
    if missing_only:
        ids_subq = (
            select(EntryMediaModel.entry_id)
            .where(EntryMediaModel.local_path.is_(None))
            .distinct()
            .subquery()
        )
    else:
        ids_subq = select(EntryMediaModel.entry_id).distinct().subquery()
    return int(
        (await session.execute(select(func.count()).select_from(ids_subq))).scalar_one()
    )


async def _media_download_summary(session: AsyncSession) -> dict[str, int]:
    total_rows = int(
        (await session.execute(select(func.count()).select_from(EntryMediaModel))).scalar_one()
    )
    missing_rows = int(
        (
            await session.execute(
                select(func.count())
                .select_from(EntryMediaModel)
                .where(EntryMediaModel.local_path.is_(None))
            )
        ).scalar_one()
    )
    distinct_entries = select(EntryMediaModel.entry_id).distinct().subquery()
    entry_count = int(
        (await session.execute(select(func.count()).select_from(distinct_entries))).scalar_one()
    )
    return {
        "entries_with_media": entry_count,
        "media_rows": total_rows,
        "media_rows_missing_local_path": missing_rows,
    }


async def _list_entry_rows_for_media_download(
    session: AsyncSession,
    *,
    limit: int,
    offset: int,
    missing_only: bool,
) -> list[EntryModel]:
    safe_limit = max(1, min(limit, 50_000))
    safe_offset = max(0, offset)
    if missing_only:
        ids_stmt = (
            select(EntryMediaModel.entry_id)
            .where(EntryMediaModel.local_path.is_(None))
            .distinct()
        )
    else:
        ids_stmt = select(EntryMediaModel.entry_id).distinct()
    stmt = (
        select(EntryModel)
        .where(EntryModel.id.in_(ids_stmt))
        .order_by(EntryModel.entry_normalized.asc())
        .offset(safe_offset)
        .limit(safe_limit)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return list(rows)


async def download_entry_media(
    session: AsyncSession,
    settings: Settings,
    word: str,
    *,
    confirm: bool,
    missing_only: bool = True,
) -> dict[str, Any]:
    if not confirm:
        items = await list_entry_media(session, word)
        if items is None:
            raise LookupError(word)
        return {
            "entry": word,
            "status": "preview",
            "items": items,
            "message": "Call again with confirm=true to write files under media_export_dir",
        }

    row = await _load_entry_row(session, word)
    if row is None:
        raise LookupError(f"Entry not found in SQL: {word}")
    payload = await _download_media_rows_for_entry(
        session,
        settings,
        row,
        missing_only=missing_only,
    )
    await session.commit()
    return {
        "entry": word,
        "status": "downloaded",
        "items": payload["items"],
        "export_dir": payload["export_dir"],
    }


async def _process_media_download_batch(
    session: AsyncSession,
    settings: Settings,
    entries: list[EntryModel],
    *,
    missing_only: bool,
    batch_label: str,
    on_tick: Callable[[ProgressTick], None] | None = None,
    failure_logger: MediaDownloadRunLogger | None = None,
) -> dict[str, Any]:
    downloaded_items = 0
    failed_items = 0
    skipped_items = 0
    entries_ok = 0
    entry_errors = 0
    errors: list[dict[str, str]] = []
    total = len(entries)

    for index, row in enumerate(entries, start=1):
        try:
            result = await _download_media_rows_for_entry(
                session,
                settings,
                row,
                missing_only=missing_only,
                failure_logger=failure_logger,
            )
        except Exception as exc:  # noqa: BLE001 — batch continues
            errors.append({"entry": row.entry, "error": str(exc)})
            entry_errors += 1
            if failure_logger is not None:
                failure_logger.log_failure(
                    {
                        "entry": row.entry,
                        "entry_id": row.id,
                        "url": "",
                        "kind": "",
                        "error": str(exc),
                        "source": "entry",
                    }
                )
            if on_tick is not None:
                on_tick(
                    ProgressTick(
                        done=index,
                        total=total,
                        extracted=downloaded_items,
                        skipped=skipped_items,
                        failed=failed_items + entry_errors,
                    )
                )
            continue
        await session.commit()
        entries_ok += 1
        for item in result["items"]:
            status = item.get("status")
            if status == "skipped":
                skipped_items += 1
            elif status == "downloaded":
                downloaded_items += 1
            elif status == "failed":
                failed_items += 1
                err = item.get("error")
                if err:
                    errors.append(
                        {
                            "entry": row.entry,
                            "url": str(item.get("url", "")),
                            "error": str(err),
                        }
                    )
        if on_tick is not None:
            on_tick(
                ProgressTick(
                    done=index,
                    total=total,
                    extracted=downloaded_items,
                    skipped=skipped_items,
                    failed=failed_items + entry_errors,
                )
            )
        elif index % 25 == 0:
            print(f"… {batch_label} {index}/{total} entries", flush=True)

    return {
        "entries_selected": len(entries),
        "entries_processed": entries_ok,
        "items_downloaded": downloaded_items,
        "items_skipped": skipped_items,
        "items_failed": failed_items,
        "errors": errors,
    }


async def download_all_entry_media(
    session: AsyncSession,
    settings: Settings,
    *,
    confirm: bool,
    limit: int = 500,
    offset: int = 0,
    missing_only: bool = True,
    run_all: bool = False,
    progress_hooks: MediaDownloadProgressHooks | None = None,
    failure_logger: MediaDownloadRunLogger | None = None,
) -> dict[str, Any]:
    summary = await _media_download_summary(session)
    if not confirm:
        return {
            "status": "preview",
            "message": "Call again with --confirm (add --all to run every batch until done)",
            "export_dir": str(settings.media_export_dir),
            **summary,
            "batch": {
                "limit": limit,
                "offset": offset,
                "missing_only": missing_only,
                "run_all": run_all,
            },
        }

    totals = {
        "batches": 0,
        "entries_processed": 0,
        "items_downloaded": 0,
        "items_skipped": 0,
        "items_failed": 0,
    }
    all_errors: list[dict[str, str]] = []
    page_offset = offset
    entries_pending_at_start = await _count_entries_for_media_download(
        session,
        missing_only=missing_only,
    )
    batch_total_est = (
        CatalogJobProgress.estimate_batch_count(entries_pending_at_start, limit)
        if run_all
        else 1
    )
    use_rich = progress_hooks is not None

    while True:
        # Pending set shrinks as local_path is filled — always take from the start.
        query_offset = 0 if missing_only else page_offset
        entries = await _list_entry_rows_for_media_download(
            session,
            limit=limit,
            offset=query_offset,
            missing_only=missing_only,
        )
        if not entries:
            break

        batch_index = totals["batches"] + 1
        batch_label = f"media batch {batch_index}"
        if progress_hooks and progress_hooks.on_batch_start:
            progress_hooks.on_batch_start(
                batch_index=batch_index,
                batch_total=batch_total_est if run_all else 1,
                item_total=len(entries),
                corpus_pending=summary["media_rows_missing_local_path"],
                entries_pending=entries_pending_at_start,
            )
        elif not use_rich:
            print(
                f"… {batch_label}: {len(entries)} entries "
                f"(missing rows ≈ {summary.get('media_rows_missing_local_path', '?')})",
                flush=True,
            )

        totals["batches"] += 1
        batch_stats = await _process_media_download_batch(
            session,
            settings,
            entries,
            missing_only=missing_only,
            batch_label=batch_label,
            on_tick=progress_hooks.on_tick if progress_hooks else None,
            failure_logger=failure_logger,
        )
        if failure_logger is not None:
            failure_logger.log_batch_summary(
                {
                    "batch_index": batch_index,
                    "entries_selected": batch_stats["entries_selected"],
                    "entries_processed": batch_stats["entries_processed"],
                    "items_downloaded": batch_stats["items_downloaded"],
                    "items_skipped": batch_stats["items_skipped"],
                    "items_failed": batch_stats["items_failed"],
                }
            )
        if progress_hooks and progress_hooks.on_batch_finish:
            progress_hooks.on_batch_finish(**batch_stats)
        totals["entries_processed"] += batch_stats["entries_processed"]
        totals["items_downloaded"] += batch_stats["items_downloaded"]
        totals["items_skipped"] += batch_stats["items_skipped"]
        totals["items_failed"] += batch_stats["items_failed"]
        all_errors.extend(batch_stats["errors"])

        summary = await _media_download_summary(session)
        if run_all:
            remaining_entries = max(
                0, entries_pending_at_start - totals["entries_processed"]
            )
            batch_total_est = CatalogJobProgress.estimate_batch_count(
                remaining_entries, limit
            )
        if not run_all:
            break
        if missing_only and summary["media_rows_missing_local_path"] == 0:
            break
        if not missing_only:
            page_offset += len(entries)
            if len(entries) < limit:
                break

    result: dict[str, Any] = {
        "status": "completed",
        "export_dir": str(settings.media_export_dir),
        "run_all": run_all,
        "batch": {
            "limit": limit,
            "start_offset": offset,
            "missing_only": missing_only,
            **totals,
        },
        "errors_sample": all_errors[:20],
        **summary,
    }
    if failure_logger is not None:
        manifest = failure_logger.finalize(totals=totals, summary=summary)
        result["run_log_dir"] = str(failure_logger.run_dir)
        result["failures_log"] = str(failure_logger.failures_path)
        result["run_manifest"] = str(manifest)
    return result
