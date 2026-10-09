import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.models import WiktionaryEntry
from src.repository.db.upsert import upsert_entry


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_reports_connected_postgres(
    postgres_api_client: AsyncClient,
) -> None:
    response = await postgres_api_client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["db"]["connected"] is True
    assert body["db"]["latency_ms"] is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_word_from_sql_after_upsert(
    postgres_api_client: AsyncClient,
    postgres_session: AsyncSession,
) -> None:
    entry = WiktionaryEntry(
        entry="heval",
        definitions=["friend"],
        metadata={"language_code": "ku"},
    )
    await upsert_entry(postgres_session, entry)
    await postgres_session.commit()

    response = await postgres_api_client.get(
        "/words/heval",
        headers={"X-Data-Source": "sql"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["entry"] == "heval"
    assert data["definitions"] == ["friend"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_words_from_sql(
    postgres_api_client: AsyncClient,
    postgres_session: AsyncSession,
) -> None:
    await upsert_entry(
        postgres_session,
        WiktionaryEntry(entry="alpha", definitions=["a"], metadata={"language_code": "ku"}),
    )
    await upsert_entry(
        postgres_session,
        WiktionaryEntry(entry="beta", definitions=["b"], metadata={"language_code": "ku"}),
    )
    await postgres_session.commit()

    response = await postgres_api_client.get(
        "/words",
        params={"limit": 10, "offset": 0},
        headers={"X-Data-Source": "sql"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 2
    entries = {item["entry"] for item in payload["items"]}
    assert {"alpha", "beta"}.issubset(entries)
