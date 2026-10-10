from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from src.catalog.audit import ExtractionAuditResult


@pytest.mark.asyncio
async def test_catalog_audit_endpoint(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = ExtractionAuditResult(
        canonical_total=100,
        canonical_extracted=80,
        canonical_pending=10,
        canonical_skipped=8,
        canonical_failed=2,
        extracted_missing_entry_id=0,
        entries_total=80,
        entries_with_html_entities=1,
        sample_entity_lemmas=["bad&html"],
    )
    monkeypatch.setattr(
        "src.api.routers.catalog.audit_canonical_extraction",
        AsyncMock(return_value=report),
    )
    response = await client.get("/catalog/audit")
    assert response.status_code == 200
    data = response.json()
    assert data["canonical_total"] == 100
    assert data["canonical_failed"] == 2
    assert data["sample_entity_lemmas"] == ["bad&html"]
