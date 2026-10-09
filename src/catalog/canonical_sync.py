import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.extraction.normalize import normalize_entry_key
from src.extraction.zim_reader import ZimReader
from src.repository.db.models.canonical import CanonicalExtractStatus, CanonicalLemmaModel


@dataclass(frozen=True, slots=True)
class CanonicalSyncResult:
    zim_files: int
    unique_lemmas: int
    upserted: int
    in_all_zims: int
    in_single_zim: int


def _scan_zims(zim_paths: list[Path]) -> dict[str, dict[str, dict[str, str]]]:
    """title_normalized -> zim_uuid -> {title, zim_path, zim_uuid}."""
    merged: dict[str, dict[str, dict[str, str]]] = {}
    for zim_path in zim_paths:
        reader = ZimReader(zim_path)
        meta = reader.metadata()
        zim_uuid = str(meta.uuid)
        zim_path_str = str(meta.path)
        for title in reader.iter_article_titles():
            key = normalize_entry_key(title)
            bucket = merged.setdefault(key, {})
            bucket[zim_uuid] = {
                "title": title,
                "zim_uuid": zim_uuid,
                "zim_path": zim_path_str,
            }
    return merged


def _pick_display_title(sources: dict[str, dict[str, str]], zim_paths: list[Path]) -> str:
    for zim_path in zim_paths:
        for source in sources.values():
            if source.get("zim_path") == str(zim_path.resolve()):
                return source["title"]
    return next(iter(sources.values()))["title"]


async def sync_canonical_wordlist(
    session: AsyncSession,
    zim_paths: list[Path],
    *,
    batch_size: int = 2000,
    progress: Callable[[int, int], None] | None = None,
) -> CanonicalSyncResult:
    merged = await asyncio.to_thread(_scan_zims, zim_paths)
    keys = list(merged.keys())
    total = len(keys)
    upserted = 0
    in_all = in_single = 0
    zim_count = len(zim_paths)

    for offset in range(0, total, batch_size):
        chunk_keys = keys[offset : offset + batch_size]
        rows: list[dict[str, object]] = []
        for key in chunk_keys:
            sources = merged[key]
            sc = len(sources)
            if sc == zim_count:
                in_all += 1
            elif sc == 1:
                in_single += 1
            rows.append(
                {
                    "title": _pick_display_title(sources, zim_paths),
                    "title_normalized": key,
                    "zim_sources": sources,
                    "source_count": sc,
                    "extract_status": CanonicalExtractStatus.PENDING.value,
                }
            )
        insert_stmt = pg_insert(CanonicalLemmaModel).values(rows)
        excluded = insert_stmt.excluded
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["title_normalized"],
            set_={
                "title": excluded.title,
                "zim_sources": excluded.zim_sources,
                "source_count": excluded.source_count,
            },
        )
        await session.execute(stmt)
        await session.commit()
        upserted += len(rows)
        if progress is not None:
            progress(min(offset + len(chunk_keys), total), total)

    return CanonicalSyncResult(
        zim_files=zim_count,
        unique_lemmas=total,
        upserted=upserted,
        in_all_zims=in_all,
        in_single_zim=in_single,
    )
