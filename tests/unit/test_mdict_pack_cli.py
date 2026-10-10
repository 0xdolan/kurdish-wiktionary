import pytest
from src.mdict.pack import list_keys, mdict_cli_command, read_meta


def test_mdict_cli_command_uses_interpreter_module() -> None:
    command = mdict_cli_command()
    assert command[0].endswith("python") or "python" in command[0]
    assert command[-2:] == ["-m", "mdict_utils"]


@pytest.mark.asyncio
async def test_read_meta_delegates_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(*args: str) -> str:
        assert args[0] == "-m"
        assert args[1].endswith("sample.mdx")
        return "meta text"

    monkeypatch.setattr("src.mdict.pack.run_mdict_cli", fake_run)
    from pathlib import Path

    result = await read_meta(Path("sample.mdx"))
    assert result == "meta text"


@pytest.mark.asyncio
async def test_list_keys_splits_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_run(*args: str) -> str:
        return "alpha\n\nbeta\n"

    monkeypatch.setattr("src.mdict.pack.run_mdict_cli", fake_run)
    keys = await list_keys(__import__("pathlib").Path("x.mdx"))
    assert keys == ["alpha", "beta"]
