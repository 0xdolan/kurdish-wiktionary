from pathlib import Path

from src.mdict.pack import extract_archive


async def unpack_to_job_dir(archive_path: Path, job_dir: Path) -> Path:
    output = job_dir / "extracted"
    await extract_archive(archive_path, output)
    return output
