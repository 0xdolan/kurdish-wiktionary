import asyncio

import pytest
from httpx import AsyncClient
from src.config import get_settings
from src.core.models import WiktionaryEntry
from src.mdict.export import BuildArtifacts


@pytest.mark.asyncio
async def test_mdx_about(client: AsyncClient) -> None:
    response = await client.get("/mdx/about")
    assert response.status_code == 200
    body = response.json()
    assert "mdict-utils" in body["body"]
    assert body["references"]


@pytest.mark.asyncio
async def test_mdx_build_job_and_download(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setenv("MDX_WORK_DIR", str(tmp_path))
    get_settings.cache_clear()

    async def fake_collect(*_args, **_kwargs):
        return [
            WiktionaryEntry(entry="one", definitions=["1"]),
            WiktionaryEntry(entry="two", definitions=["2"]),
        ]

    async def fake_build(_settings, *, entries, output_dir, **_kwargs):
        job_dir = output_dir
        job_dir.mkdir(parents=True, exist_ok=True)
        mdx = job_dir / "wikiferheng.mdx"
        mdx.write_bytes(b"stub")
        manifest = job_dir / "manifest.json"
        manifest.write_text("{}", encoding="utf-8")
        return BuildArtifacts(
            staging_dir=job_dir / "staging",
            dict_txt=job_dir / "staging" / "dict.txt",
            mdx_path=mdx,
            mdd_path=None,
            entry_count=2,
            manifest_path=manifest,
        )

    monkeypatch.setattr("src.api.routers.mdx.collect_entries", fake_collect)
    monkeypatch.setattr("src.api.routers.mdx.build_mdict_artifacts", fake_build)

    create = await client.post(
        "/mdx/build",
        json={"data_source": "zim", "limit": 10, "include_media": False},
    )
    assert create.status_code == 202
    job_id = create.json()["job_id"]

    for _ in range(50):
        status = await client.get(f"/mdx/build/{job_id}")
        assert status.status_code == 200
        if status.json()["status"] in {"completed", "failed"}:
            break
        await asyncio.sleep(0.05)
    assert status.json()["status"] == "completed"

    download = await client.get(f"/mdx/build/{job_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert len(download.content) > 0
