import asyncio
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from src.catalog.sync import WordlistSyncResult


@pytest.mark.asyncio
async def test_catalog_sync_job_returns_202(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.api.routers.catalog.sync_wordlist_to_sql",
        AsyncMock(return_value=WordlistSyncResult(scanned=10, inserted=10)),
    )
    response = await client.post("/catalog/wordlist/sync")
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    for _ in range(50):
        status = await client.get(f"/catalog/jobs/{job_id}")
        assert status.status_code == 200
        if status.json()["status"] in {"completed", "failed"}:
            break
        await asyncio.sleep(0.05)
    assert status.json()["status"] == "completed"
    assert status.json()["progress"]["scanned"] == 10
