from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DataSource(StrEnum):
    ZIM = "zim"
    SQL = "sql"


def _default_zim_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    candidates = sorted(root.glob("zim/**/*.zim"))
    if candidates:
        return candidates[-1]
    return root / "zim" / "wiktionary" / "wiktionary_ku_all_nopic_2026-06.zim"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://wiktionary:wiktionary@localhost:5432/wiktionary",
        description="Async SQLAlchemy URL",
    )
    zim_path: Path = Field(default_factory=_default_zim_path)
    zim_paths: str = Field(
        default="",
        description="Comma-separated ZIM paths for canonical wordlist (falls back to zim_path)",
    )
    default_data_source: DataSource = DataSource.SQL
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    rate_limit_rpm: int = Field(default=120, ge=1)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    mdx_work_dir: Path = Field(default=Path("build/mdict"))
    mdx_default_title: str = Field(default="Wîkîferheng")
    mdx_build_max_concurrent: int = Field(default=1, ge=1)
    mdx_include_media: bool = True
    media_export_dir: Path = Field(default=Path("build/media"))

    app_name: str = "wikitionary-to-mdx"
    api_prefix: str = ""

    @field_validator("zim_path", "mdx_work_dir", "media_export_dir", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path) -> Path:
        return Path(value).expanduser()

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
