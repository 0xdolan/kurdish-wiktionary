from src.config import DataSource, Settings
from src.repository.protocol import WiktionaryRepositoryProto
from src.repository.sql_repository import SqlRepository
from src.repository.zim_repository import ZimRepository


def resolve_data_source(settings: Settings, override: DataSource | None) -> DataSource:
    return override if override is not None else settings.default_data_source


def build_repository(
    settings: Settings,
    *,
    source_override: DataSource | None = None,
) -> WiktionaryRepositoryProto:
    source = resolve_data_source(settings, source_override)
    if source is DataSource.ZIM:
        return ZimRepository(settings.zim_path)
    return SqlRepository(settings.database_url, enabled=False)
