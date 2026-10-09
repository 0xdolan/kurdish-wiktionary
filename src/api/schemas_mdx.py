from typing import Any, Literal

from pydantic import BaseModel, Field

from src.config import DataSource


class MdxAboutResponse(BaseModel):
    format: str = "text/markdown"
    body: str
    references: list[str] = Field(default_factory=list)


class MdxBuildRequest(BaseModel):
    data_source: DataSource = DataSource.SQL
    include_media: bool | None = None
    limit: int | None = Field(default=100, ge=1, le=500_000)
    zim_path: str | None = None
    title: str | None = None
    description: str | None = None


class MdxExtractRequest(BaseModel):
    mdx_path: str
    mdd_path: str | None = None


class JobCreatedResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    kind: Literal[
        "build",
        "extract",
        "catalog_sync",
        "catalog_extract",
        "catalog_canonical_sync",
        "catalog_canonical_extract",
    ]
    status: Literal["pending", "running", "completed", "failed"]
    progress: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    artifact_dir: str | None = None


class MdxMetaResponse(BaseModel):
    path: str
    meta: str


class MdxKeysResponse(BaseModel):
    path: str
    total: int
    offset: int
    limit: int
    keys: list[str]


class MdxLookupResponse(BaseModel):
    headword: str
    html: str
    source: Literal["repository", "mdx"]
