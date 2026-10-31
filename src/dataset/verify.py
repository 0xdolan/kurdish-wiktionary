"""Prove a rebuild matches the published release: ZIM hashes, row counts and table contents."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from src.dataset.schema import TABLES

EXPECTED = Path(__file__).resolve().parents[2] / "assets" / "dataset" / "expected-release.json"

# Download status and licences live in `media`, and they change as Wikimedia's files change.
_CONTENT_SKIP = frozenset({"media"})


def table_digest(conn: sqlite3.Connection, table: str, columns: list[str]) -> str:
    """Hash rows in a fixed order, so parallel parsing can't change the result."""
    digest = hashlib.sha256()
    names = ", ".join(columns)
    for row in conn.execute(f"SELECT {names} FROM {table} ORDER BY {names}"):
        digest.update(repr(row).encode("utf-8"))
    return digest.hexdigest()


def measure(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    tables: dict[str, dict[str, Any]] = {}
    for table in TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table.name}").fetchone()[0]
        tables[table.name] = {"rows": count}
        if table.name not in _CONTENT_SKIP:
            columns = [column.name for column in table.columns]
            tables[table.name]["sha256"] = table_digest(conn, table.name, columns)
    return tables


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def write_expected(conn: sqlite3.Connection, archives: list[Path], path: Path = EXPECTED) -> None:
    payload = {
        "zim": {archive.name: file_sha256(archive) for archive in archives},
        "tables": measure(conn),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def compare(
    conn: sqlite3.Connection,
    archives: list[Path],
    path: Path = EXPECTED,
) -> list[str]:
    """Differences from the published release; an empty list means an exact match."""
    expected = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for name, wanted in expected["zim"].items():
        match = next((archive for archive in archives if archive.name == name), None)
        if match is None or not match.is_file():
            problems.append(f"ZIM not found: {name}")
        elif file_sha256(match) != wanted:
            problems.append(f"ZIM differs from the published one: {name}")
    actual = measure(conn)
    for table, wanted in expected["tables"].items():
        found = actual.get(table)
        if found is None:
            problems.append(f"table missing: {table}")
        elif found["rows"] != wanted["rows"]:
            problems.append(f"{table}: {found['rows']:,} rows, expected {wanted['rows']:,}")
        elif "sha256" in wanted and found.get("sha256") != wanted["sha256"]:
            problems.append(f"{table}: same row count, but the contents differ")
    return problems
