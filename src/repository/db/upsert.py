from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import WiktionaryEntry
from src.extraction.normalize import normalize_entry_key
from src.repository.db.models import (
    EntryAntonymRow,
    EntryDefinitionRow,
    EntryDerivedTermRow,
    EntryExampleRow,
    EntryModel,
    EntryPartOfSpeechRow,
    EntryPhoneticRow,
    EntryPronunciationRow,
    EntrySynonymRow,
)


def _language_code(entry: WiktionaryEntry) -> str:
    raw = entry.metadata.get("language_code")
    return str(raw) if raw else "ku"


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


async def _replace_child_rows(
    session: AsyncSession,
    entry_id: int,
    values: list[str],
    row_cls: type[Any],
) -> None:
    await session.execute(delete(row_cls).where(row_cls.entry_id == entry_id))
    rows = [
        row_cls(entry_id=entry_id, ordinal=index, value=value)
        for index, value in enumerate(_dedupe_preserve_order(values))
    ]
    session.add_all(rows)


async def upsert_entry(session: AsyncSession, entry: WiktionaryEntry) -> EntryModel:
    language_code = _language_code(entry)
    normalized = normalize_entry_key(entry.entry)
    stmt = select(EntryModel).where(
        EntryModel.entry_normalized == normalized,
        EntryModel.language_code == language_code,
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    zim_uuid = entry.metadata.get("zim_uuid")
    source_date = entry.metadata.get("zim_date")

    if row is None:
        row = EntryModel(
            entry=entry.entry,
            entry_normalized=normalized,
            language_code=language_code,
            etymology=entry.etymology,
            extra_metadata=entry.metadata,
            zim_uuid=str(zim_uuid) if zim_uuid else None,
            source_date=str(source_date) if source_date else None,
        )
        session.add(row)
        await session.flush()
    else:
        row.entry = entry.entry
        row.etymology = entry.etymology
        row.extra_metadata = entry.metadata
        row.zim_uuid = str(zim_uuid) if zim_uuid else row.zim_uuid
        row.source_date = str(source_date) if source_date else row.source_date

    await session.flush()
    entry_id = row.id
    await _replace_child_rows(session, entry_id, entry.definitions, EntryDefinitionRow)
    await _replace_child_rows(session, entry_id, entry.examples, EntryExampleRow)
    await _replace_child_rows(session, entry_id, entry.synonyms, EntrySynonymRow)
    await _replace_child_rows(session, entry_id, entry.antonyms, EntryAntonymRow)
    await _replace_child_rows(session, entry_id, entry.phonetic_transcriptions, EntryPhoneticRow)
    await _replace_child_rows(session, entry_id, entry.pronunciations, EntryPronunciationRow)
    await _replace_child_rows(session, entry_id, entry.derived_terms, EntryDerivedTermRow)
    await _replace_child_rows(session, entry_id, entry.part_of_speech, EntryPartOfSpeechRow)
    await session.flush()
    return row


async def upsert_entries(session: AsyncSession, entries: list[WiktionaryEntry]) -> int:
    count = 0
    for item in entries:
        await upsert_entry(session, item)
        count += 1
    await session.commit()
    return count
