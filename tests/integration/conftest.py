import os
import subprocess
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.api.app import create_app
from src.config import get_settings
from src.repository.db.base import dispose_engine
from testcontainers.community.postgres import PostgresContainer

REPO_ROOT = Path(__file__).resolve().parents[2]


def _async_database_url(container: PostgresContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(5432)
    user = container.username
    password = container.password
    dbname = container.dbname
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"


@pytest.fixture(scope="session")
def postgres_database_url() -> Iterator[str]:
    try:
        with PostgresContainer("postgres:16-alpine") as postgres:
            url = _async_database_url(postgres)
            yield url
    except Exception as exc:  # noqa: BLE001 — skip when Docker unavailable
        pytest.skip(f"Postgres testcontainer unavailable: {exc}")


@pytest.fixture(scope="session")
def migrated_postgres_url(postgres_database_url: str) -> Iterator[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = postgres_database_url
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    yield postgres_database_url


@pytest.fixture
async def postgres_session(migrated_postgres_url: str) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(migrated_postgres_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def postgres_api_client(
    migrated_postgres_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncClient, None]:
    monkeypatch.setenv("DATABASE_URL", migrated_postgres_url)
    monkeypatch.setenv("DEFAULT_DATA_SOURCE", "sql")
    get_settings.cache_clear()
    await dispose_engine()

    application = create_app()
    transport = ASGITransport(app=application)
    async with (
        application.router.lifespan_context(application),
        AsyncClient(transport=transport, base_url="http://test") as client,
    ):
        yield client

    await dispose_engine()
    get_settings.cache_clear()
