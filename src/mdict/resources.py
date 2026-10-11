import shutil
from pathlib import Path


def _project_assets_mdict_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "assets" / "mdict"


def stage_resource_tree(
    staging_dir: Path,
    *,
    include_media: bool,
) -> Path:
    """Copy shared CSS (and future media) into MDD staging directory."""
    resources_dir = staging_dir / "resources"
    resources_dir.mkdir(parents=True, exist_ok=True)

    assets = _project_assets_mdict_dir()
    css_src = assets / "css" / "wiktionary.css"
    css_dest = resources_dir / "css" / "wiktionary.css"
    if css_src.is_file():
        css_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(css_src, css_dest)
    js_src = assets / "js" / "wikt-entry.js"
    js_dest = resources_dir / "js" / "wikt-entry.js"
    if js_src.is_file():
        js_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(js_src, js_dest)
    icon_src = assets / "img" / "volume-up.png"
    icon_dest = resources_dir / "img" / "volume-up.png"
    if icon_src.is_file():
        icon_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, icon_dest)
    elif not css_dest.exists():
        css_dest.parent.mkdir(parents=True, exist_ok=True)
        css_dest.write_text(
            "\n.wikt-entry{font-family:system-ui,sans-serif;}\n",
            encoding="utf-8",
        )

    fonts_src = assets / "fonts" / "sahel"
    fonts_dest = resources_dir / "fonts" / "sahel"
    if fonts_src.is_dir():
        if fonts_dest.exists():
            shutil.rmtree(fonts_dest)
        shutil.copytree(fonts_src, fonts_dest)

    if include_media:
        # ZIM media harvesting: wire audio/images into resources_dir with paths
        # referenced from HTML (e.g. audio/heval.opus, img/...).
        pass
    return resources_dir
