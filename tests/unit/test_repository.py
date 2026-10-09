from unittest.mock import AsyncMock, MagicMock

import pytest
from src.config import DataSource
from src.core.exceptions import DatabaseError, NotFoundError
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


@pytest.mark.asyncio
async def test_sql_repository_not_enabled() -> None:
    repo = SqlRepository("postgresql+asyncpg://localhost/test", enabled=False)
    health = await repo.health_detail()
    assert health.ready is False
    with pytest.raises(DatabaseError):
        await repo.get_entry("heval")
