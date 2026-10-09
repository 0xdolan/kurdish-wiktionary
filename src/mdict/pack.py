import asyncio
import shutil
from pathlib import Path


class MdictCliError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, stderr: str) -> None:
        self.command = command
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"mdict failed ({returncode}): {' '.join(command)}\n{stderr}")


def mdict_executable() -> str:
    binary = shutil.which("mdict")
    if binary is None:
        msg = "mdict CLI not found; install mdict-utils (uv sync)."
        raise FileNotFoundError(msg)
    return binary


async def run_mdict_cli(*args: str) -> str:
    executable = mdict_executable()
    command = [executable, *args]
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout_bytes, stderr_bytes = await process.communicate()
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if process.returncode != 0:
        raise MdictCliError(command, process.returncode or 1, stderr)
    return stdout


async def pack_mdx(
    *,
    title_html: Path,
    description_html: Path,
    dict_txt: Path,
    output_mdx: Path,
) -> None:
    output_mdx.parent.mkdir(parents=True, exist_ok=True)
    await run_mdict_cli(
        "--title",
        str(title_html),
        "--description",
        str(description_html),
        "-a",
        str(dict_txt),
        str(output_mdx),
    )


async def pack_mdd(
    *,
    title_html: Path,
    description_html: Path,
    resources_dir: Path,
    output_mdd: Path,
) -> None:
    if not any(resources_dir.rglob("*")):
        return
    output_mdd.parent.mkdir(parents=True, exist_ok=True)
    await run_mdict_cli(
        "--title",
        str(title_html),
        "--description",
        str(description_html),
        "-a",
        str(resources_dir),
        str(output_mdd),
    )


async def read_meta(mdx_path: Path) -> str:
    return await run_mdict_cli("-m", str(mdx_path))


async def list_keys(mdx_path: Path) -> list[str]:
    output = await run_mdict_cli("-k", str(mdx_path))
    return [line.strip() for line in output.splitlines() if line.strip()]


async def query_key(mdx_path: Path, headword: str) -> str:
    return await run_mdict_cli("-q", headword, str(mdx_path))


async def extract_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    await run_mdict_cli("-x", str(archive_path), "-d", str(destination))
