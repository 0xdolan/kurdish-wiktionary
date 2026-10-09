from typing import Any, Literal

from pydantic import BaseModel, Field

from src.core.models import WiktionaryEntry

FieldName = Literal[
    "definitions",
    "synonyms",
    "antonyms",
    "examples",
    "pronunciations",
    "phonetic_transcriptions",
    "derived_terms",
    "part_of_speech",
]


class LexiconEntryListResponse(BaseModel):
    items: list[WiktionaryEntry]
    total: int
    limit: int
    offset: int


class LexiconFieldListResponse(BaseModel):
    field: FieldName
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class LexiconFieldValuesResponse(BaseModel):
    entry: str
    field: FieldName
    values: list[str]


class LexiconHtmlResponse(BaseModel):
    entry: str
    html: str


class LexiconSectionHtmlResponse(BaseModel):
    entry: str
    section: str
    html: str


class LexiconMediaListResponse(BaseModel):
    entry: str
    items: list[dict[str, Any]]


class LexiconPreviewResponse(BaseModel):
    title: str
    entry: WiktionaryEntry
    html_bytes: int
    section_html_keys: list[str]
    media_count: int
    media: list[dict[str, Any]]
    counts: dict[str, int]
    warnings: list[str]


class LexiconExtractResponse(BaseModel):
    entry: str
    entry_id: int
    message: str = "stored"


class LexiconSparseResponse(BaseModel):
    items: list[dict[str, Any]]


class LexiconExportQuery(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class LexiconHtmlIndexResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    include_html: bool


class LexiconSectionCorpusResponse(BaseModel):
    section: str
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


class LexiconMediaCorpusResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int
    kind: str | None = None


class LexiconZimFieldPreviewResponse(BaseModel):
    entry: str
    field: FieldName
    values: list[str]
    count: int
    source: str
    warnings: list[str]


class LexiconDuplicatesResponse(BaseModel):
    items: list[dict[str, Any]]


class LexiconMediaDownloadResponse(BaseModel):
    entry: str
    status: str
    items: list[dict[str, Any]]
    export_dir: str | None = None
    message: str | None = None
