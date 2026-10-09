from pathlib import Path

from src.config import Settings


def resolve_zim_paths(settings: Settings, overrides: list[Path] | None = None) -> list[Path]:
    if overrides:
        return [p.expanduser().resolve() for p in overrides]
    raw = getattr(settings, "zim_paths", "") or ""
    if isinstance(raw, str) and raw.strip():
        parts = [part.strip() for part in raw.split(",") if part.strip()]
        return [Path(part).expanduser().resolve() for part in parts]
    return [settings.zim_path.expanduser().resolve()]


def sort_zim_paths_for_extract(paths: list[Path]) -> list[Path]:
    """Prefer maxi (media-rich HTML) before nopic when merging."""

    def rank(path: Path) -> tuple[int, str]:
        name = path.name.casefold()
        if "maxi" in name:
            return (0, name)
        if "nopic" in name:
            return (1, name)
        return (2, name)

    return sorted(paths, key=rank)
