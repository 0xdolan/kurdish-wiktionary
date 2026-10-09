from src.config import DataSource
from src.core.exceptions import DatabaseError
from src.core.models import WiktionaryEntry
from src.repository.protocol import RepositoryHealth


class SqlRepository:
    """PostgreSQL-backed repository (implemented in Phase 3)."""

    def __init__(self, database_url: str, *, enabled: bool = False) -> None:
        self._database_url = database_url
        self._enabled = enabled

    @property
    def source(self) -> DataSource:
        return DataSource.SQL

    def _require_enabled(self) -> None:
        if not self._enabled:
            raise DatabaseError(
                "SQL repository is not available until Phase 3 migrations and ingest are complete.",
            )

    async def get_entry(self, word: str) -> WiktionaryEntry | None:
        self._require_enabled()
        _ = word
        return None

    async def list_entries(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[WiktionaryEntry], int]:
        self._require_enabled()
        _ = (limit, offset)
        return [], 0

    async def health_detail(self) -> RepositoryHealth:
        return RepositoryHealth(
            source=DataSource.SQL,
            ready=self._enabled,
            detail=self._database_url.split("@")[-1],
        )
