from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CatalogStatsResponse(BaseModel):
    zim_path: str
    zim_uuid: str | None
    zim_title_count: int
    wordlist_total: int
    wordlist_pending: int
    wordlist_extracted: int
    wordlist_skipped: int
    wordlist_failed: int
    entries_total: int


class WordlistItemResponse(BaseModel):
    id: int
    title: str
    extract_status: Literal["pending", "extracted", "skipped", "failed"]
    entry_id: int | None
    discovered_at: datetime
    extracted_at: datetime | None


class WordlistPageResponse(BaseModel):
    items: list[WordlistItemResponse]
    total: int
    limit: int
    offset: int


class CatalogSyncResponse(BaseModel):
    scanned: int
    inserted: int


class CatalogExtractRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=10_000)


class CatalogExtractResponse(BaseModel):
    attempted: int
    extracted: int
    skipped: int
    failed: int
