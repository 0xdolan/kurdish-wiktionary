from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from src.api.app import create_app
from src.config import get_settings
from src.repository.db.base import dispose_engine, get_db_session

from tests.conftest import _fake_db_session


@pytest.mark.asyncio
async def test_rate_limit_returns_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_RPM", "2")
    monkeypatch.setenv("DEFAULT_DATA_SOURCE", "zim")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "src.repository.zim_repository.ZimRepository.list_entries",
        AsyncMock(return_value=([], 0)),
    )
    await dispose_engine()
    application = create_app()
    application.dependency_overrides[get_db_session] = _fake_db_session

    transport = ASGITransport(app=application)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as ac,
    ):
        for _ in range(2):
            ok = await ac.get("/words", params={"limit": 1, "offset": 0})
            assert ok.status_code == 200
        limited = await ac.get("/words", params={"limit": 1, "offset": 0})
        assert limited.status_code == 429
        assert limited.json()["title"] == "Too Many Requests"

    await dispose_engine()
