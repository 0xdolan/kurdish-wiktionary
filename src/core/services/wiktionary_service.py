from src.core.exceptions import NotFoundError
from src.core.models import WiktionaryEntry
from src.repository.protocol import WiktionaryRepositoryProto


class WiktionaryService:
    def __init__(self, repository: WiktionaryRepositoryProto) -> None:
        self._repository = repository

    @property
    def repository(self) -> WiktionaryRepositoryProto:
        return self._repository

    async def get_entry(self, word: str) -> WiktionaryEntry:
        entry = await self._repository.get_entry(word)
        if entry is None:
            raise NotFoundError(f"No Wiktionary entry found for '{word}'.")
        return entry

    async def list_entries(
        self,
        limit: int,
        offset: int,
    ) -> tuple[list[WiktionaryEntry], int]:
        return await self._repository.list_entries(limit=limit, offset=offset)
