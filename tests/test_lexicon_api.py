from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from src.core.models import WiktionaryEntry
from src.lexicon.service import PreviewResult


@pytest.mark.asyncio
async def test_lexicon_preview(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    preview = PreviewResult(
        title="heval",
        entry=WiktionaryEntry(entry="heval", definitions=["friend"], synonyms=["dost"]),
        html_bytes=100,
        section_html_keys=["beranber"],
        media_count=1,
        media=[{"url": "https://example.com/a.mp3", "kind": "audio"}],
        counts={"definitions": 1, "synonyms": 1, "antonyms": 0, "examples": 0,
                "pronunciations": 0, "phonetic_transcriptions": 0, "derived_terms": 0,
                "part_of_speech": 0},
        warnings=["antonyms_empty"],
    )
    monkeypatch.setattr(
        "src.api.routers.lexicon.lexicon_service.preview_entry",
        AsyncMock(return_value=preview),
    )
    response = await client.post("/lexicon/entries/heval/preview")
    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["synonyms"] == 1
    assert "antonyms_empty" in body["warnings"]


@pytest.mark.asyncio
async def test_lexicon_extract_requires_confirm(client: AsyncClient) -> None:
    response = await client.post("/lexicon/entries/heval/extract")
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_lexicon_zim_field_preview(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.api.routers.lexicon.lexicon_service.zim_field_preview",
        AsyncMock(
            return_value={
                "entry": "heval",
                "field": "synonyms",
                "values": ["dost"],
                "count": 1,
                "source": "zim",
                "warnings": ["antonyms_empty"],
            }
        ),
    )
    response = await client.get("/lexicon/entries/heval/zim/fields/synonyms")
    assert response.status_code == 200
    assert response.json()["values"] == ["dost"]
