from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.api.schemas_mdx import JobCreatedResponse, JobStatusResponse


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


CatalogJobCreatedResponse = JobCreatedResponse
CatalogJobStatusResponse = JobStatusResponse


class CatalogExtractSyncRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)


class ZimFileStatsResponse(BaseModel):
    path: str
    uuid: str | None
    title_count: int


class CanonicalStatsResponse(BaseModel):
    zim_files: list[ZimFileStatsResponse]
    total: int
    pending: int
    extracted: int
    skipped: int
    failed: int
    in_all_configured_zims: int
    in_one_zim_only: int
    entries_total: int


class CanonicalSyncResponse(BaseModel):
    zim_files: int
    unique_lemmas: int
    upserted: int
    in_all_zims: int
    in_single_zim: int


class CanonicalExtractResponse(BaseModel):
    attempted: int
    extracted: int
    skipped: int
    failed: int


class CatalogAuditResponse(BaseModel):
    canonical_total: int
    canonical_extracted: int
    canonical_pending: int
    canonical_skipped: int
    canonical_failed: int
    extracted_missing_entry_id: int
    entries_with_html_entities: int
    sample_entity_lemmas: list[str]


class OutcomeCategoryResponse(BaseModel):
    status: str
    category: str
    count: int
    sample_titles: list[str]


class OutcomeRowResponse(BaseModel):
    title: str
    title_normalized: str
    status: str
    reason: str | None
    category: str
    entry_id: int | None
    extracted_at: str | None
    retry_hint: str


class OutcomeReportResponse(BaseModel):
    scope: str
    generated_at: str
    skipped_total: int
    failed_total: int
    categories: list[OutcomeCategoryResponse]
    rows: list[OutcomeRowResponse]
