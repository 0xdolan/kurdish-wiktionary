import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_word_from_zim(client: AsyncClient) -> None:
    response = await client.get(
        "/words/heval",
        headers={"X-Data-Source": "zim"},
    )
    if response.status_code == 404:
        pytest.skip("ZIM not available or entry missing")
    assert response.status_code == 200
    data = response.json()
    assert data["entry"] == "heval"


@pytest.mark.asyncio
async def test_sql_source_without_database(client: AsyncClient) -> None:
    response = await client.get(
        "/words/heval",
        headers={"X-Data-Source": "sql"},
    )
    assert response.status_code in {404, 500, 503}
