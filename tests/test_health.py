import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_payload(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "zim" in data
    assert "db" in data
    assert "path" in data["zim"]
