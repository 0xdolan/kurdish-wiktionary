from pathlib import Path


def stage_resource_tree(
    staging_dir: Path,
    *,
    include_media: bool,
) -> Path:
    """Prepare MDD resource directory (media extraction is Phase 7 follow-up when include_media)."""
    resources_dir = staging_dir / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    css_path = resources_dir / "css" / "wikt.css"
    if not css_path.exists():
        css_path.parent.mkdir(parents=True, exist_ok=True)
        css_path.write_text(
            ".wikt-entry{font-family:system-ui,sans-serif;line-height:1.5;}\n"
            ".wikt-headword{font-size:1.4rem;margin:0 0 .5rem;}\n",
            encoding="utf-8",
        )
    if include_media:
        # ZIM media harvesting can be wired here; default ships stylesheet only.
        pass
    return resources_dir
