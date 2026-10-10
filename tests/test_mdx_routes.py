from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_mdx_meta_and_keys(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MDX_WORK_DIR", str(tmp_path))
    from src.config import get_settings

    get_settings.cache_clear()

    mdx_file = tmp_path / "sample.mdx"
    mdx_file.write_bytes(b"stub")

    monkeypatch.setattr(
        "src.api.routers.mdx.read_meta",
        AsyncMock(return_value='Record: "3"'),
    )
    monkeypatch.setattr(
        "src.api.routers.mdx.list_keys",
        AsyncMock(return_value=["alpha", "beta", "gamma"]),
    )

    meta = await client.get("/mdx/meta", params={"path": "sample.mdx"})
    assert meta.status_code == 200
    assert 'Record: "3"' in meta.json()["meta"]

    keys = await client.get("/mdx/keys", params={"path": "sample.mdx", "limit": 2})
    assert keys.status_code == 200
    body = keys.json()
    assert body["total"] == 3
    assert body["keys"] == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_mdx_meta_rejects_path_outside_work_dir(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MDX_WORK_DIR", str(tmp_path))
    from src.config import get_settings

    get_settings.cache_clear()

    response = await client.get("/mdx/meta", params={"path": "../../../etc/passwd"})
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_mdx_extract_job(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MDX_WORK_DIR", str(tmp_path))
    from src.config import get_settings

    get_settings.cache_clear()

    archive = tmp_path / "wikiferheng.mdx"
    archive.write_bytes(b"stub")

    monkeypatch.setattr(
        "src.api.routers.mdx.unpack_to_job_dir",
        AsyncMock(return_value=tmp_path / "out"),
    )

    create = await client.post(
        "/mdx/extract",
        json={"mdx_path": "wikiferheng.mdx"},
    )
    assert create.status_code == 202
    job_id = create.json()["job_id"]
    status = await client.get(f"/mdx/extract/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] in {"completed", "running", "pending", "failed"}
