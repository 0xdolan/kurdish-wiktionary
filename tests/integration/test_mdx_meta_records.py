import shutil
from pathlib import Path

import pytest
from src.config import get_settings
from src.core.models import WiktionaryEntry
from src.mdict.export import build_mdict_artifacts
from src.mdict.pack import mdict_executable, read_meta


@pytest.mark.integration
@pytest.mark.asyncio
async def test_packed_mdx_reports_nonzero_records(tmp_path: Path) -> None:
    if shutil.which("mdict") is None:
        pytest.skip("mdict CLI not installed")

    _ = mdict_executable()
    entries = [WiktionaryEntry(entry="lemma", definitions=["definition text"])]
    artifacts = await build_mdict_artifacts(
        get_settings(),
        entries=entries,
        output_dir=tmp_path,
        include_media=False,
    )
    meta = await read_meta(artifacts.mdx_path)
    assert 'Record: "1"' in meta
