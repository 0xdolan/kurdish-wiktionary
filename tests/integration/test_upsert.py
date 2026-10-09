import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from src.core.models import WiktionaryEntry
from src.repository.db.models import Base, EntryModel
from src.repository.db.upsert import upsert_entry


@pytest.mark.integration
@pytest.mark.asyncio
async def test_upsert_idempotent_sqlite_memory() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        entry = WiktionaryEntry(
            entry="heval",
            definitions=["friend", "updated"],
            phonetic_transcriptions=["/heval/"],
            metadata={"language_code": "ku"},
        )
        row = await upsert_entry(session, entry)
        await session.commit()
        first_id = row.id

        updated = WiktionaryEntry(
            entry="heval",
            definitions=["friend only"],
            metadata={"language_code": "ku"},
        )
        row2 = await upsert_entry(session, updated)
        await session.commit()
        assert row2.id == first_id

        stmt = (
            select(EntryModel)
            .where(EntryModel.id == first_id)
            .options(selectinload(EntryModel.definitions))
        )
        loaded = (await session.execute(stmt)).scalar_one()
        assert len(loaded.definitions) == 1
        assert loaded.definitions[0].value == "friend only"

    await engine.dispose()
