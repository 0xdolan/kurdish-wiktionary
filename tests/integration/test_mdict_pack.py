import shutil
from pathlib import Path

import pytest
from src.core.models import WiktionaryEntry
from src.mdict.export import build_mdict_artifacts
from src.mdict.pack import list_keys, mdict_executable


@pytest.mark.integration
@pytest.mark.asyncio
async def test_pack_three_entry_fixture(tmp_path: Path) -> None:
    if shutil.which("mdict") is None:
        pytest.skip("mdict CLI not installed")

    _ = mdict_executable()
    entries = [
        WiktionaryEntry(entry="alpha", definitions=["first"]),
        WiktionaryEntry(entry="beta", definitions=["second"]),
        WiktionaryEntry(entry="gamma", definitions=["third"]),
    ]
    from src.config import get_settings

    settings = get_settings()
    artifacts = await build_mdict_artifacts(
        settings,
        entries=entries,
        output_dir=tmp_path,
        include_media=True,
    )
    assert artifacts.mdx_path.is_file()
    keys = await list_keys(artifacts.mdx_path)
    assert {"alpha", "beta", "gamma"}.issubset(set(keys))
