from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_validation_error_problem_json(client: AsyncClient) -> None:
    response = await client.get("/words", params={"limit": 0})
    assert response.status_code == 422
    body = response.json()
    assert body["title"] == "ValidationError"
    assert body["status"] == 422
    assert isinstance(body["detail"], list)


@pytest.mark.asyncio
async def test_not_found_problem_json(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.repository.zim_repository.ZimRepository.get_entry",
        AsyncMock(return_value=None),
    )
    response = await client.get("/words/missing-word-xyz")
    assert response.status_code == 404
    body = response.json()
    assert body["title"] == "NotFoundError"
    assert body["status"] == 404
    assert "missing-word-xyz" in body["detail"]


@pytest.mark.asyncio
async def test_list_words_empty_zim(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.repository.zim_repository.ZimRepository.list_entries",
        AsyncMock(return_value=([], 0)),
    )
    response = await client.get("/words", params={"limit": 5})
    assert response.status_code == 200
    assert response.json()["total"] == 0
