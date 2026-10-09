from dataclasses import dataclass
from typing import Protocol

from src.config import DataSource
from src.core.models import WiktionaryEntry


@dataclass(frozen=True, slots=True)
class RepositoryHealth:
    source: DataSource
    ready: bool
    detail: str


class WiktionaryRepositoryProto(Protocol):
    @property
    def source(self) -> DataSource: ...

    async def get_entry(self, word: str) -> WiktionaryEntry | None: ...

    async def list_entries(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[WiktionaryEntry], int]: ...

    async def health_detail(self) -> RepositoryHealth: ...
