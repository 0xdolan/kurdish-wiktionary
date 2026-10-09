from pydantic import BaseModel, Field

from src.core.models import WiktionaryEntry


class WordListResponse(BaseModel):
    items: list[WiktionaryEntry]
    total: int
    limit: int
    offset: int


class PaginationParams(BaseModel):
    limit: int = Field(default=20, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
