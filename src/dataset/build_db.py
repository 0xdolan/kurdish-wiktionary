"""Parse ZIM archives into the release SQLite database (parallel, deterministic ids)."""

from __future__ import annotations

import multiprocessing
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from libzim.reader import Archive

from src.dataset.page_parser import page_id_for, parse_page
from src.dataset.schema import INDEXES, TABLE_BY_NAME, TABLES, create_table_sql

_CHUNK = 4000
_WORKERS = 6
_RESERVED_PREFIXES = ("_", "fulltext/", "listing/")

_archive: Archive | None = None
_other: Archive | None = None


@dataclass(frozen=True, slots=True)
class _Task:
    start: int
    stop: int


def connect(database: Path) -> sqlite3.Connection:
    # Long timeout: a download and a licence fetch may share the database for hours.
    conn = sqlite3.connect(database, timeout=120)
    conn.execute("PRAGMA foreign_keys=OFF")
    return conn


def create_database(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    for suffix in (".sqlite", ".sqlite-journal", ".sqlite-wal", ".sqlite-shm"):
        database.with_suffix(suffix).unlink(missing_ok=True)
    conn = connect(database)
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA synchronous=OFF")
    for table in TABLES:
        conn.execute(create_table_sql(table))
    conn.execute("CREATE TABLE build_meta (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


def _init_worker(path: str, skip_if_in: str | None) -> None:
    global _archive, _other
    _archive = Archive(path)
    _other = Archive(skip_if_in) if skip_if_in else None


def _parse_chunk(args: tuple[_Task, str, bool]) -> dict[str, Any]:
    task, flavour, in_latest = args
    assert _archive is not None
    rows: dict[str, list[tuple[Any, ...]]] = {}
    media: dict[str, dict[str, Any]] = {}
    placeholders = 0
    errors: list[tuple[str, str]] = []
    for index in range(task.start, task.stop):
        entry = _archive._get_entry_by_id(index)
        path = entry.path
        if path.startswith(_RESERVED_PREFIXES):
            continue
        if _other is not None and _other.has_entry_by_path(path):
            continue
        if entry.is_redirect:
            target = entry.get_redirect_entry()
            rows.setdefault("redirects", []).append((entry.title, target.title, "hard"))
            continue
        item = entry.get_item()
        if not item.mimetype.startswith("text/html"):
            continue
        html = bytes(item.content).decode("utf-8", "replace")
        try:
            parsed = parse_page(
                html=html,
                title=path,
                page_id=page_id_for(index, from_nopic=flavour == "nopic"),
                source_zim=flavour,
                in_latest_dump=in_latest,
            )
        except Exception as exc:  # A single bad page must not lose the whole run.
            errors.append((path, repr(exc)[:300]))
            continue
        for table, values in parsed.rows.items():
            rows.setdefault(table, []).extend(values)
        media.update(parsed.media)
        placeholders += parsed.placeholder_examples
    return {"rows": rows, "media": media, "placeholders": placeholders, "errors": errors}


def _write_rows(conn: sqlite3.Connection, rows: dict[str, list[tuple[Any, ...]]]) -> None:
    for table, values in rows.items():
        marks = ",".join("?" * len(TABLE_BY_NAME[table].columns))
        conn.executemany(f"INSERT INTO {table} VALUES ({marks})", values)


def _write_media(conn: sqlite3.Connection, media: dict[str, dict[str, Any]]) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO media (media_id, kind, source, zim_path, source_url, commons_file,"
        " status, original_width, original_height) VALUES"
        " (:media_id, :kind, :source, :zim_path, :source_url, :commons_file, 'missing',"
        " :original_width, :original_height)",
        [{**m, "source": "zim" if m["zim_path"] else "wikimedia"} for m in media.values()],
    )


def _ingest(
    conn: sqlite3.Connection,
    zim: Path,
    *,
    flavour: str,
    in_latest: bool,
    skip_if_in: Path | None,
    progress: Callable[[str, int, int], None] | None,
) -> dict[str, int]:
    total = Archive(str(zim)).all_entry_count
    tasks = [
        (_Task(start, min(total, start + _CHUNK)), flavour, in_latest)
        for start in range(0, total, _CHUNK)
    ]
    placeholders = 0
    errors: list[tuple[str, str]] = []
    with multiprocessing.get_context("fork").Pool(
        _WORKERS,
        _init_worker,
        (str(zim), str(skip_if_in) if skip_if_in else None),
    ) as pool:
        for done, result in enumerate(pool.imap_unordered(_parse_chunk, tasks), start=1):
            _write_rows(conn, result["rows"])
            _write_media(conn, result["media"])
            placeholders += result["placeholders"]
            errors.extend(result["errors"])
            if progress:
                progress(flavour, done, len(tasks))
    conn.commit()
    conn.executemany("INSERT INTO build_errors VALUES (?, ?)", errors)
    conn.commit()
    return {"placeholder_examples": placeholders, "parse_errors": len(errors)}


def build_database(
    *,
    database: Path,
    maxi: Path,
    nopic: Path | None,
    progress: Callable[[str, int, int], None] | None = None,
) -> dict[str, int]:
    """Read the newest ZIM fully, then only the pages unique to the older ZIM."""
    conn = create_database(database)
    conn.execute("CREATE TABLE build_errors (title TEXT, error TEXT)")
    stats = _ingest(
        conn,
        maxi,
        flavour="maxi",
        in_latest=True,
        skip_if_in=None,
        progress=progress,
    )
    if nopic is not None:
        older = _ingest(
            conn,
            nopic,
            flavour="nopic",
            in_latest=False,
            skip_if_in=maxi,
            progress=progress,
        )
        stats = {key: stats[key] + older[key] for key in stats}
    for statement in INDEXES:
        conn.execute(statement)
    conn.commit()
    conn.close()
    return stats
