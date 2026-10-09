from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.state import AppState
from src.config import DataSource, Settings, get_settings
from src.extraction.zim_reader import ZimReader
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


def get_app_state(request: Request) -> AppState:
    return getattr(request.app.state, "wiktionary", AppState())


AppStateDep = Annotated[AppState, Depends(get_app_state)]


@asynccontextmanager
async def lifespan_context(app: FastAPI, settings: Settings) -> AsyncIterator[None]:
    init_engine(settings.database_url)
    zim_reader: ZimReader | None = None
    if settings.zim_path.is_file():
        zim_reader = ZimReader(settings.zim_path)
    app.state.wiktionary = AppState(zim_reader=zim_reader)
    try:
        yield
    finally:
        app.state.wiktionary = AppState()
        await dispose_engine()
