from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import DataSource, Settings, get_settings
from src.repository.db.base import dispose_engine, get_db_session, init_engine

SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_data_source_override(
    x_data_source: Annotated[str | None, Header(alias="X-Data-Source")] = None,
) -> DataSource | None:
    if x_data_source is None:
        return None
    normalized = x_data_source.strip().lower()
    try:
        return DataSource(normalized)
    except ValueError:
        return None


DataSourceOverrideDep = Annotated[DataSource | None, Depends(get_data_source_override)]


DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


@asynccontextmanager
async def lifespan_context(settings: Settings) -> AsyncIterator[None]:
    init_engine(settings.database_url)
    try:
        yield
    finally:
        await dispose_engine()
