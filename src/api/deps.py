from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, Header

from src.config import DataSource, Settings, get_settings

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


@asynccontextmanager
async def lifespan_context(_settings: Settings) -> AsyncIterator[None]:
    yield
