import time
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import DataSource
from src.core.models import WiktionaryEntry
from src.extraction.normalize import normalize_entry_key
from src.repository.db.mappers import entry_model_to_schema
from src.repository.db.models import EntryModel
from src.repository.protocol import RepositoryHealth


class SqlRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @property
    def source(self) -> DataSource:
        return DataSource.SQL

    def _entry_options(self) -> tuple[Any, ...]:
        return (
            selectinload(EntryModel.definitions),
            selectinload(EntryModel.examples),
            selectinload(EntryModel.synonyms),
            selectinload(EntryModel.antonyms),
            selectinload(EntryModel.phonetics),
            selectinload(EntryModel.pronunciations),
            selectinload(EntryModel.derived_terms),
            selectinload(EntryModel.parts_of_speech),
        )

    async def get_entry(self, word: str, *, language_code: str = "ku") -> WiktionaryEntry | None:
        normalized = normalize_entry_key(word)
        stmt = (
            select(EntryModel)
            .where(
                EntryModel.entry_normalized == normalized,
                EntryModel.language_code == language_code,
            )
            .options(*self._entry_options())
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return entry_model_to_schema(row)

    async def list_entries(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[WiktionaryEntry], int]:
        safe_limit = max(1, min(limit, 500))
        safe_offset = max(0, offset)

        count_stmt = select(func.count()).select_from(EntryModel)
        total = int((await self._session.execute(count_stmt)).scalar_one())

        stmt = (
            select(EntryModel)
            .order_by(EntryModel.entry_normalized.asc())
            .offset(safe_offset)
            .limit(safe_limit)
            .options(*self._entry_options())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [entry_model_to_schema(row) for row in rows], total

    async def health_detail(self) -> RepositoryHealth:
        started = time.perf_counter()
        ready = False
        try:
            await self._session.execute(select(1))
            ready = True
        except Exception:
            ready = False
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return RepositoryHealth(
            source=DataSource.SQL,
            ready=ready,
            detail=f"latency_ms={latency_ms}",
        )
