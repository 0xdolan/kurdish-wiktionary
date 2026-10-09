from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.api.deps import DataSourceOverrideDep, DbSessionDep, SettingsDep
from src.api.schemas import WordListResponse
from src.core.models import WiktionaryEntry
from src.core.services.wiktionary_service import WiktionaryService
from src.repository.factory import build_repository

router = APIRouter(prefix="/words", tags=["words"])


def get_wiktionary_service(
    settings: SettingsDep,
    source_override: DataSourceOverrideDep,
    session: DbSessionDep,
) -> WiktionaryService:
    repository = build_repository(
        settings,
        source_override=source_override,
        session=session,
    )
    return WiktionaryService(repository)


ServiceDep = Annotated[WiktionaryService, Depends(get_wiktionary_service)]


@router.get("", response_model=WordListResponse)
async def list_words(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WordListResponse:
    items, total = await service.list_entries(limit=limit, offset=offset)
    return WordListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{word}", response_model=WiktionaryEntry)
async def get_word(word: str, service: ServiceDep) -> WiktionaryEntry:
    return await service.get_entry(word)
