"""Build the MDict source (dict.txt + resources) from the release database and pack MDX/MDD.

Record format, per docs/MDX_ENTRY_FORMAT.md::

    headword
    <link rel="stylesheet" ...><article class="wk">...</article><script ...></script>
    </>

Article HTML comes from entry_html.py.
"""

from __future__ import annotations

import multiprocessing
import shutil
import sqlite3
import subprocess
import sys
from collections.abc import Callable
from html import escape
from pathlib import Path
from typing import TYPE_CHECKING

from src.dataset.entry_html import (
    SCRIPT_TAG,
    STYLESHEET_LINK,
    clean_fragment,
    render_article,
    rewrite_media,
)
from src.dataset.page_parser import ID_SPACE

if TYPE_CHECKING:
    from _typeshed import SupportsWrite

__all__ = ["clean_fragment", "render_article", "rewrite_media"]

RECORD_END = "</>"
_WORKERS = 6
_PAGES_PER_TASK = 3000


_local_paths: dict[str, str] = {}
_conn: sqlite3.Connection | None = None


def format_record(headword: str, article: str) -> str:
    key = " ".join(headword.split())
    return f"{key}\n{STYLESHEET_LINK}{article}{SCRIPT_TAG}\n{RECORD_END}\n"


def format_link(alias: str, target: str) -> str:
    return f"{' '.join(alias.split())}\n@@@LINK={' '.join(target.split())}\n{RECORD_END}\n"


def _init_worker(database: str, local_paths: dict[str, str]) -> None:
    global _conn, _local_paths
    _conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    _local_paths = local_paths


def _render_chunk(page_ids: list[int]) -> str:
    assert _conn is not None
    low, high = page_ids[0] * ID_SPACE, (page_ids[-1] + 1) * ID_SPACE
    sections: dict[int, list[tuple[int, int, int, int, str, str, str | None, str]]] = {}
    for row in _conn.execute(
        "SELECT s.section_id, s.entry_id, s.ordinal, s.level, s.heading, s.section_type, s.pos,"
        " COALESCE(h.html, '') FROM sections s LEFT JOIN section_html h USING (section_id)"
        " WHERE s.section_id > ? AND s.section_id < ? ORDER BY s.section_id",
        (low, high),
    ):
        sections.setdefault(row[0] // ID_SPACE, []).append(row)
    languages: dict[int, tuple[str | None, str]] = {
        row[0]: (row[1], row[2])
        for row in _conn.execute(
            "SELECT entry_id, language_name, language_code FROM entries"
            " WHERE entry_id > ? AND entry_id < ?",
            (low, high),
        )
    }
    out: list[str] = []
    marks = ",".join("?" * len(page_ids))
    for page_id, title, url in _conn.execute(
        f"SELECT page_id, title, url FROM pages WHERE page_kind != 'soft_redirect'"
        f" AND page_id IN ({marks})",
        page_ids,
    ):
        rows = sections.get(page_id)
        if not rows:
            continue
        out.append(format_record(title, render_article(title, url, rows, languages, _local_paths)))
    return "".join(out)


def _page_chunks(conn: sqlite3.Connection) -> list[list[int]]:
    # A list, not a generator: the pool reads tasks from another thread, and SQLite forbids that.
    page_ids = [row[0] for row in conn.execute("SELECT page_id FROM pages ORDER BY page_id")]
    return [page_ids[i : i + _PAGES_PER_TASK] for i in range(0, len(page_ids), _PAGES_PER_TASK)]


def write_alias_records(conn: sqlite3.Connection, handle: SupportsWrite[str]) -> int:
    """Redirects, then other-script spellings, so ``هه‌ڤال`` finds ``heval``."""
    titles = {
        row[0] for row in conn.execute("SELECT title FROM pages WHERE page_kind != 'soft_redirect'")
    }
    seen: set[str] = set()
    count = 0

    def emit(alias: str, target: str) -> None:
        nonlocal count
        key = " ".join(alias.split())
        if key and key != target and key not in titles and key not in seen and target in titles:
            seen.add(key)
            handle.write(format_link(key, target))
            count += 1

    for alias, target in conn.execute("SELECT alias, target FROM redirects"):
        emit(alias, target)
    for alias, target in conn.execute(
        "SELECT r.term, e.title FROM relations r JOIN entries e ON e.entry_id = r.entry_id"
        " WHERE r.relation_type = 'other_scripts'"
    ):
        emit(alias, target)
    return count


def write_dict_txt(database: Path, path: Path, progress: Callable[[str], None]) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    local_paths = dict(
        conn.execute("SELECT media_id, local_path FROM media WHERE status = 'present'")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    records = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        with multiprocessing.get_context("fork").Pool(
            _WORKERS,
            _init_worker,
            (str(database), local_paths),
        ) as pool:
            for done, chunk in enumerate(pool.imap(_render_chunk, _page_chunks(conn)), start=1):
                handle.write(chunk)
                records += chunk.count(f"\n{RECORD_END}\n")
                if done % 50 == 0:
                    progress(f"dict.txt: {records} records")
        aliases = write_alias_records(conn, handle)
    return {"articles": records, "aliases": aliases}


def stage_resources(store: Path, assets: Path, staging: Path) -> tuple[Path, Path]:
    """Lay out the two MDD trees: base (css/js/fonts/images) and audio (``.1.mdd``)."""
    base, audio = staging / "resources", staging / "resources_audio"
    for folder in (base, audio):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
    for name in ("css", "js", "img", "fonts"):
        shutil.copytree(assets / name, base / name)
    if (store / "images").is_dir():
        shutil.copytree(store / "images", base / "images", copy_function=_link_file)
    if (store / "audio").is_dir():
        shutil.copytree(store / "audio", audio / "audio", copy_function=_link_file)
    return base, audio


def _link_file(source: str, destination: str) -> None:
    Path(destination).hardlink_to(source)


def write_templates(
    directory: Path, *, version: str, zim_date: str, entries: int
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    title = directory / "title.html"
    description = directory / "description.html"
    title.write_text("Kurdish Wiktionary", encoding="utf-8")
    description.write_text(
        "<p><b>Kurdish Wiktionary</b> "
        f"{escape(version)}: {entries:,} entries from the "
        f"{escape(zim_date)} snapshot of "
        '<a href="https://ku.wiktionary.org/">Wîkîferheng</a> (Kurdish Wiktionary).</p>'
        "<p>Text: CC BY-SA 4.0. Media licences vary per file. Unofficial: not produced or "
        "endorsed by the Wikimedia Foundation.</p>",
        encoding="utf-8",
    )
    return title, description


def _pack(title: Path, description: Path, source: Path, output: Path, log: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "mdict_utils",
        "--title",
        str(title),
        "--description",
        str(description),
        "-a",
        str(source),
        str(output),
    ]
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        subprocess.run(command, check=True, stdout=handle, stderr=subprocess.STDOUT)


def pack_all(
    *,
    dict_txt: Path,
    resources: Path,
    resources_audio: Path,
    templates: tuple[Path, Path],
    output_dir: Path,
    log: Path,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    title, description = templates
    outputs = [output_dir / "wiktionary.mdx", output_dir / "wiktionary.mdd"]
    for stale in output_dir.glob("wiktionary*.md[xd]"):
        stale.unlink()
    _pack(title, description, dict_txt, outputs[0], log)
    _pack(title, description, resources, outputs[1], log)
    if any(resources_audio.rglob("*.*")):
        audio_mdd = output_dir / "wiktionary.1.mdd"
        _pack(title, description, resources_audio, audio_mdd, log)
        outputs.append(audio_mdd)
    return outputs
