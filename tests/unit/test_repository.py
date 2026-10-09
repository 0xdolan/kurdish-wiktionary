from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.config import DataSource
from src.core.exceptions import NotFoundError
from src.core.models import WiktionaryEntry
from src.core.services.wiktionary_service import WiktionaryService
from src.repository.factory import build_repository, resolve_data_source
from src.repository.sql_repository import SqlRepository


@pytest.mark.asyncio
async def test_service_raises_not_found() -> None:
    repo = MagicMock()
    repo.get_entry = AsyncMock(return_value=None)
    service = WiktionaryService(repo)
    with pytest.raises(NotFoundError):
        await service.get_entry("missing")


@pytest.mark.asyncio
async def test_service_returns_entry() -> None:
    entry = WiktionaryEntry(entry="heval", definitions=["friend"])
    repo = MagicMock()
    repo.get_entry = AsyncMock(return_value=entry)
    service = WiktionaryService(repo)
    result = await service.get_entry("heval")
    assert result.entry == "heval"


def test_resolve_data_source_override() -> None:
    from src.config import Settings

    settings = Settings(default_data_source=DataSource.SQL)
    assert resolve_data_source(settings, DataSource.ZIM) is DataSource.ZIM
    assert resolve_data_source(settings, None) is DataSource.SQL


def test_build_repository_zim() -> None:
    from src.config import Settings

    settings = Settings(default_data_source=DataSource.ZIM)
    repo = build_repository(settings)
    assert repo.source is DataSource.ZIM


def test_build_repository_sql_requires_session() -> None:
    from src.config import Settings

    settings = Settings(default_data_source=DataSource.SQL)
    with pytest.raises(RuntimeError):
        build_repository(settings)


@pytest.mark.asyncio
async def test_sql_repository_health_and_get() -> None:
    session = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)
    repo = SqlRepository(session)
    health = await repo.health_detail()
    assert health.ready is True
    assert await repo.get_entry("heval") is None
