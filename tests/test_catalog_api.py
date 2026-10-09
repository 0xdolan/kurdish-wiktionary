from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from src.catalog.stats import CatalogStats


@pytest.mark.asyncio
async def test_catalog_stats(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.api.routers.catalog.fetch_catalog_stats",
        AsyncMock(
            return_value=CatalogStats(
                zim_path="/zim/test.zim",
                zim_uuid="uuid",
                zim_title_count=1000,
                wordlist_total=100,
                wordlist_pending=80,
                wordlist_extracted=15,
                wordlist_skipped=3,
                wordlist_failed=2,
                entries_total=15,
            )
        ),
    )
    response = await client.get("/catalog/stats")
    assert response.status_code == 200
    data = response.json()
    assert "zim_title_count" in data
    assert "wordlist_total" in data
    assert "entries_total" in data


@pytest.mark.asyncio
async def test_catalog_wordlist_empty(client: AsyncClient) -> None:
    response = await client.get("/catalog/wordlist", params={"limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 0
    assert "items" in payload
