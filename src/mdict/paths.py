from pathlib import Path


class UnsafePathError(ValueError):
    """Resolved path escapes the configured work directory."""


def resolve_under_work_dir(work_dir: Path, relative: str | Path) -> Path:
    base = work_dir.resolve()
    target = (base / relative).resolve()
    if not target.is_relative_to(base):
        msg = f"Path escapes MDX work directory: {relative}"
        raise UnsafePathError(msg)
    return target
