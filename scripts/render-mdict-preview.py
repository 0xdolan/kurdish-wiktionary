#!/usr/bin/env python3
"""Write a browser-openable HTML preview for the MDict entry template."""

from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path

from src.config import get_settings
from src.core.models import WiktionaryEntry
from src.lexicon import service as lexicon_service
from src.mdict.constants import ENTRY_SCRIPT_HREF, STYLESHEET_HREF
from src.mdict.media_captions import image_captions_from_html
from src.mdict.renderer import render_entry_html, sample_brave_entry
from src.mdict.sql_loader import (
    attach_media_to_entry,
    load_entry_with_media,
    media_rows_to_render_items,
)
from src.repository.db.base import dispose_engine, get_session_factory, init_engine


def build_preview_document(*, css_href: str, body_html: str, banner: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ku" dir="auto">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>MDict entry preview</title>
  <link rel="stylesheet" type="text/css" href="{css_href}" />
  <style>
    body {{
      margin: 0;
      min-height: 100vh;
      padding: clamp(1.25rem, 4vw, 2rem) clamp(1rem, 3vw, 1.5rem) 2.5rem;
      background: #f1f5f9;
    }}
    .preview-banner {{
      max-width: 42rem;
      margin: 0 auto 1.25rem;
      padding: 0.875rem 1.125rem;
      font: 0.8rem/1.45 system-ui, sans-serif;
      color: #64748b;
      background: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .preview-banner code {{
      font-size: 0.85em;
      color: #2563eb;
    }}
  </style>
</head>
<body>
  <p class="preview-banner">{banner}</p>
  {body_html}
  <script type="text/javascript" src="../js/wikt-entry.js"></script>
</body>
</html>
"""


def _sync_preview_static_assets(preview_root: Path) -> None:
    assets = Path(__file__).resolve().parents[1] / "assets" / "mdict"
    icon_src = assets / "img" / "volume-up.png"
    icon_dest = preview_root / "img" / "volume-up.png"
    if icon_src.is_file():
        icon_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_src, icon_dest)


def _sync_preview_media(
    *,
    export_dir: Path,
    entry_normalized: str,
    preview_media_root: Path,
) -> Path:
    """Copy ``build/media/{lemma}/`` → ``assets/mdict/preview/media/{lemma}/``."""
    src = export_dir / entry_normalized
    dest = preview_media_root / entry_normalized
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    return dest


async def _load_from_database(
    word: str,
    *,
    media_href_prefix: str,
    refresh_extract: bool,
) -> WiktionaryEntry:
    settings = get_settings()
    init_engine(settings.database_url)
    session_factory = get_session_factory()
    async with session_factory() as session:
        if refresh_extract:
            await lexicon_service.extract_entry_confirmed(session, settings, word)
            await session.commit()
        loaded = await load_entry_with_media(session, word)
        if loaded is None:
            msg = f"No SQL entry for {word!r}"
            raise LookupError(msg)
        entry, media_rows, section_html, html_full = loaded
    await dispose_engine()

    export_dir = settings.media_export_dir
    preview_root = Path("assets/mdict/preview/media")
    _sync_preview_static_assets(Path("assets/mdict/preview"))
    _sync_preview_media(
        export_dir=export_dir,
        entry_normalized=entry.entry,
        preview_media_root=preview_root,
    )
    if not any(row.local_path for row in media_rows):
        hint = (
            f"No local_path on media for {word!r}. Run:\n"
            f"  ZIM_PATHS=... DATABASE_URL=... uv run python -m src.lexicon "
            f"media-download {word} --confirm"
        )
        raise RuntimeError(hint)
    captions = image_captions_from_html(html_full) if html_full else {}
    render_media = media_rows_to_render_items(
        rows=media_rows,
        href_prefix=media_href_prefix,
        captions=captions,
    )
    return attach_media_to_entry(
        entry,
        render_media,
        section_html=section_html,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--entry",
        default="heval",
        help="Lemma for --from-db (default: heval)",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Load entry + media from PostgreSQL (requires downloaded media)",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Use English demo entry (brave) instead of database",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Preview HTML path",
    )
    parser.add_argument(
        "--css-href",
        default=f"../css/{Path(STYLESHEET_HREF).name}",
        help="Stylesheet href relative to output file",
    )
    parser.add_argument(
        "--refresh-extract",
        action="store_true",
        help="Re-parse lemma from ZIM into SQL before rendering (updates section_html)",
    )
    args = parser.parse_args()

    use_db = args.from_db or (not args.demo and args.entry != "brave")
    if args.demo:
        use_db = False

    if use_db:
        word = args.entry
        media_prefix = "media/"
        entry = asyncio.run(
            _load_from_database(
                word,
                media_href_prefix=media_prefix,
                refresh_extract=args.refresh_extract,
            )
        )
        output = args.output or Path(f"assets/mdict/preview/{word}.html")
        banner = (
            f"Live preview for SQL lemma <code>{escape_html(word)}</code> "
            f"(definitions, audio, images from PostgreSQL + ZIM/Wikimedia). "
            f"MDict records use the same HTML with "
            f"<code>&lt;link href=&quot;{escape_html(STYLESHEET_HREF)}&quot; /&gt;</code>."
        )
    else:
        entry = sample_brave_entry()
        output = args.output or Path("assets/mdict/preview/brave.html")
        banner = (
            "Demo template (English <code>brave</code>). "
            "Use <code>--from-db --entry heval</code> for a real Kurdish entry."
        )

    body = render_entry_html(entry)
    doc = build_preview_document(css_href=args.css_href, body_html=body, banner=banner)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(doc, encoding="utf-8")
    print(f"Wrote {output.resolve()}")

    if use_db and word == "heval":
        redirect_html = """<!DOCTYPE html>
<html lang="ku">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="refresh" content="0; url=heval.html" />
  <title>MDict preview</title>
  <script>location.replace("heval.html");</script>
</head>
<body><p><a href="heval.html">heval.html</a></p></body>
</html>
"""
        for name in ("index.html", "brave.html"):
            redirect_path = output.parent / name
            redirect_path.write_text(redirect_html, encoding="utf-8")
            print(f"Wrote {redirect_path.resolve()} (→ heval.html)")

    return 0


def escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    raise SystemExit(main())
