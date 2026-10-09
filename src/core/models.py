from typing import Any

from pydantic import BaseModel, Field, field_validator


def _ensure_str_list(value: list[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [item.strip() for item in value if item and item.strip()]


class WiktionaryEntry(BaseModel):
    entry: str
    part_of_speech: list[str] = Field(default_factory=list)
    definitions: list[str] = Field(default_factory=list)
    phonetic_transcriptions: list[str] = Field(default_factory=list)
    pronunciations: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    etymology: str | None = None
    derived_terms: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "part_of_speech",
        "definitions",
        "phonetic_transcriptions",
        "pronunciations",
        "examples",
        "synonyms",
        "antonyms",
        "derived_terms",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value: list[str] | str | None) -> list[str]:
        return _ensure_str_list(value)

    @field_validator("entry")
    @classmethod
    def entry_not_blank(cls, value: str) -> str:
        if not value.strip():
            msg = "entry must not be blank"
            raise ValueError(msg)
        return value.strip()
