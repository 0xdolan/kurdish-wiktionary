"""Load WiktionaryEntry + MDict media paths from PostgreSQL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.models import WiktionaryEntry
from src.extraction.normalize import normalize_entry_key
from src.repository.db.mappers import entry_model_to_schema
from src.mdict.media_captions import lookup_image_caption
from src.repository.db.models import EntryHtmlModel, EntryMediaModel, EntryModel


@dataclass(frozen=True, slots=True)
class MdictRenderMedia:
    kind: str
    href: str
    label: str | None = None
    caption: str | None = None
    source_url: str | None = None


def _audio_label_from_path(local_path: str) -> str:
    name = local_path.rsplit("/", maxsplit=1)[-1]
    if "Ebulf" in name or "Ebulfîda" in name:
        return "Ebulfîda (Kurmancî)"
    if "Dildadil" in name:
        return "Dildadil (Kurdî)"
    return "Guhdar bike"


def media_rows_to_render_items(
    *,
    rows: list[EntryMediaModel],
    href_prefix: str = "",
    captions: dict[str, str] | None = None,
) -> list[MdictRenderMedia]:
    """Build renderer media list from DB rows with ``local_path`` set."""
    cap = captions or {}
    items: list[MdictRenderMedia] = []
    for row in rows:
        if not row.local_path:
            continue
        rel = row.local_path.replace("\\", "/")
        href = f"{href_prefix}{rel}" if href_prefix else rel
        label: str | None = None
        caption: str | None = None
        if row.kind == "audio":
            label = _audio_label_from_path(rel)
        elif row.kind == "image":
            caption = lookup_image_caption(cap, url=row.url, local_href=href)
            if isinstance(row.extra, dict):
                caption = caption or row.extra.get("caption") or row.extra.get("alt")
            label = caption
        items.append(
            MdictRenderMedia(
                kind=row.kind,
                href=href,
                label=label,
                caption=caption,
                source_url=(row.url or None),
            )
        )
    return items


def attach_media_to_entry(
    entry: WiktionaryEntry,
    media: list[MdictRenderMedia],
    *,
    section_html: dict[str, str] | None = None,
    max_images: int = 12,
) -> WiktionaryEntry:
    """Copy entry and attach ``metadata.mdict_media`` + ``section_html`` for HTML rendering."""
    audio = [m for m in media if m.kind == "audio"]
    images = [m for m in media if m.kind == "image"]
    images.sort(key=lambda m: (0 if ".jpg" in m.href.casefold() else 1, m.href))
    selected_images = images[:max_images]
    payload: list[dict[str, Any]] = []
    for m in [*audio, *selected_images]:
        payload.append(
            {
                "kind": m.kind,
                "href": m.href,
                "label": m.label,
                "caption": m.caption,
                "source_url": m.source_url,
            }
        )
    metadata = dict(entry.metadata)
    metadata["mdict_media"] = payload
    metadata["data_source"] = "sql"
    if section_html:
        metadata["section_html"] = section_html
    return entry.model_copy(update={"metadata": metadata})


async def load_entry_with_media(
    session: AsyncSession,
    word: str,
    *,
    language_code: str = "ku",
) -> tuple[WiktionaryEntry, list[EntryMediaModel], dict[str, str], str] | None:
    normalized = normalize_entry_key(word)
    stmt = (
        select(EntryModel)
        .where(
            EntryModel.entry_normalized == normalized,
            EntryModel.language_code == language_code,
        )
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
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        return None
    media_stmt = (
        select(EntryMediaModel)
        .where(EntryMediaModel.entry_id == row.id)
        .order_by(EntryMediaModel.kind.asc(), EntryMediaModel.id.asc())
    )
    media_rows = list((await session.execute(media_stmt)).scalars().all())
    html_stmt = select(EntryHtmlModel).where(EntryHtmlModel.entry_id == row.id)
    html_row = (await session.execute(html_stmt)).scalar_one_or_none()
    section_html: dict[str, str] = {}
    html_full = ""
    if html_row is not None:
        raw_sections = html_row.section_html or {}
        section_html = {str(k): str(v) for k, v in raw_sections.items()}
        html_full = html_row.html_full or ""
    return entry_model_to_schema(row), media_rows, section_html, html_full
