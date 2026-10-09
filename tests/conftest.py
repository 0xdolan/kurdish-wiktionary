from collections.abc import AsyncGenerator, Iterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.api.app import create_app
from src.config import Settings, get_settings
from src.repository.db.base import dispose_engine, get_db_session


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def test_settings(monkeypatch: pytest.MonkeyPatch) -> Iterator[Settings]:
    monkeypatch.setenv("DEFAULT_DATA_SOURCE", "zim")
    monkeypatch.setenv("RATE_LIMIT_RPM", "1000")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


async def _fake_db_session() -> AsyncGenerator[AsyncSession, None]:
    session = AsyncMock(spec=AsyncSession)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    result_mock.scalar_one.return_value = 0
    result_mock.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result_mock)
    yield session


@pytest.fixture
async def app(test_settings: Settings, monkeypatch: pytest.MonkeyPatch):
    _ = test_settings
    await dispose_engine()
    application = create_app()
    application.dependency_overrides[get_db_session] = _fake_db_session
    async with application.router.lifespan_context(application):
        yield application
    application.dependency_overrides.clear()
    await dispose_engine()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
