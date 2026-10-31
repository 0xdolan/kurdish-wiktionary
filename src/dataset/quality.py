"""Quality report: what is in the release, how complete it is, and what to distrust."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from src.dataset.schema import TABLES


def _one(conn: sqlite3.Connection, sql: str, *args: Any) -> Any:
    return conn.execute(sql, args).fetchone()[0]


def _coverage(conn: sqlite3.Connection, where: str) -> dict[str, Any]:
    total, senses, ipa, audio, etymology, translations, auto, pending, lemmas = conn.execute(
        "SELECT COUNT(*), SUM(sense_count > 0), SUM(has_ipa), SUM(has_audio), SUM(has_etymology),"
        " SUM(has_translations), SUM(is_auto_generated), SUM(definition_pending),"
        " SUM(sense_count > 0 AND pos_list NOT LIKE '%\\_form%' ESCAPE '\\'"
        f" AND pos_list != '') FROM entries WHERE {where}"
    ).fetchone()

    def share(value: int | None) -> float:
        return round(100 * (value or 0) / total, 2) if total else 0.0

    return {
        "entries": total,
        "with_senses_pct": share(senses),
        "with_ipa_pct": share(ipa),
        "with_audio_pct": share(audio),
        "with_etymology_pct": share(etymology),
        "with_translations_pct": share(translations),
        "auto_generated": auto or 0,
        "auto_generated_pct": share(auto),
        "definition_pending": pending or 0,
        "headword_entries": lemmas or 0,
    }


def build_report(conn: sqlite3.Connection, build_meta: dict[str, str]) -> dict[str, Any]:
    tables = {t.name: _one(conn, f"SELECT COUNT(*) FROM {t.name}") for t in TABLES}
    media_status = [
        {"kind": kind, "role": role, "status": status, "files": files, "bytes": size or 0}
        for kind, role, status, files, size in conn.execute(
            "SELECT kind, role, status, COUNT(*), SUM(bytes) FROM media"
            " GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
        )
    ]
    return {
        "build": build_meta,
        "row_counts": tables,
        "page_kinds": dict(conn.execute("SELECT page_kind, COUNT(*) FROM pages GROUP BY 1")),
        "pages_only_in_older_zim": _one(
            conn, "SELECT COUNT(*) FROM pages WHERE in_latest_dump = 0"
        ),
        "language_count": _one(conn, "SELECT COUNT(DISTINCT language_code) FROM entries"),
        "top_languages": [
            {"code": code, "name": name, "entries": entries, "senses": senses}
            for code, name, entries, senses in conn.execute(
                "SELECT language_code, language_name, COUNT(*), SUM(sense_count) FROM entries"
                " GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 25"
            )
        ],
        "coverage": {
            "all": _coverage(conn, "1=1"),
            "kurmanci": _coverage(conn, "language_code = 'ku'"),
            "sorani": _coverage(conn, "language_code = 'ckb'"),
        },
        "section_types": dict(
            conn.execute("SELECT section_type, COUNT(*) FROM sections GROUP BY 1 ORDER BY 2 DESC")
        ),
        "parts_of_speech": dict(
            conn.execute(
                "SELECT pos, COUNT(*) FROM sections WHERE pos IS NOT NULL"
                " GROUP BY 1 ORDER BY 2 DESC"
            )
        ),
        "unclassified_headings": dict(
            conn.execute(
                "SELECT heading, COUNT(*) FROM sections WHERE section_type = 'other'"
                " GROUP BY 1 ORDER BY 2 DESC LIMIT 100"
            )
        ),
        "unclassified_section_count": _one(
            conn, "SELECT COUNT(*) FROM sections WHERE section_type = 'other'"
        ),
        "pos_sections_without_senses": _one(
            conn,
            "SELECT COUNT(*) FROM sections s WHERE s.section_type = 'pos' AND NOT EXISTS"
            " (SELECT 1 FROM senses x WHERE x.section_id = s.section_id)",
        ),
        "entries_without_senses": _one(
            conn,
            "SELECT COUNT(*) FROM entries WHERE sense_count = 0"
            " AND pos_list NOT LIKE '%verb_conjugation%'",
        ),
        "duplicate_entry_keys": _one(
            conn,
            "SELECT COUNT(*) FROM (SELECT entry_key FROM entries GROUP BY 1 HAVING COUNT(*) > 1)",
        ),
        "parse_errors": _one(conn, "SELECT COUNT(*) FROM build_errors"),
        "audio_by_language": [
            {"code": code, "name": name, "recordings": count}
            for code, name, count in conn.execute(
                "SELECT e.language_code, e.language_name, COUNT(*) FROM pronunciations p"
                " JOIN entries e USING (entry_id) WHERE p.kind = 'audio'"
                " GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15"
            )
        ],
        "most_common_definitions": [
            {"definition": text, "senses": count}
            for text, count in conn.execute(
                "SELECT definition, COUNT(*) FROM senses GROUP BY 1 ORDER BY 2 DESC LIMIT 15"
            )
        ],
        "media": media_status,
        "media_licences": [
            {"licence": licence, "files": files}
            for licence, files in conn.execute(
                "SELECT COALESCE(license, '(unknown)'), COUNT(*) FROM media"
                " GROUP BY 1 ORDER BY 2 DESC"
            )
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    """Human summary shipped as QUALITY.md."""
    every = report["coverage"]["all"]
    kurmanci = report["coverage"]["kurmanci"]
    rows = "\n".join(f"| `{name}` | {count:,} |" for name, count in report["row_counts"].items())
    coverage_rows = "\n".join(
        f"| {label} | {block['entries']:,} | {block['with_senses_pct']}% "
        f"| {block['with_ipa_pct']}% "
        f"| {block['with_audio_pct']}% | {block['with_etymology_pct']}% "
        f"| {block['with_translations_pct']}% | {block['auto_generated_pct']}% |"
        for label, block in (
            ("All languages", every),
            ("Kurmancî", kurmanci),
            ("Soranî", report["coverage"]["sorani"]),
        )
    )
    audio_line = ", ".join(
        f"{item['name']}: {item['recordings']:,}" for item in report["audio_by_language"][:5]
    )
    common = "\n".join(
        f"| {item['definition']} | {item['senses']:,} |"
        for item in report["most_common_definitions"]
    )
    media_rows = "\n".join(
        f"| {m['kind']} | {m['role']} | {m['status']} | {m['files']:,} "
        f"| {m['bytes'] / 1e6:,.1f} MB |"
        for m in report["media"]
    )
    licence_rows = "\n".join(
        f"| {item['licence']} | {item['files']:,} |" for item in report["media_licences"]
    )
    headings = "\n".join(
        f"| {heading} | {count:,} |"
        for heading, count in list(report["unclassified_headings"].items())[:30]
    )
    return f"""# Quality report

Generated from the release database. Machine-readable version: `quality/report.json`.

## Read this before using the data

- **{every["auto_generated"]:,} of {every["entries"]:,} entries ({every["auto_generated_pct"]}%) are
  bot-made.** The wiki marks them as generated from translation tables and warns that they may
  contain translation errors. Filter with `is_auto_generated = 0` to leave out entries with that
  marker. Bots may have made other pages without leaving one.
- **Entries are unequal.** Many are one-line glosses or inflected forms (`pos` ending in `_form`).
  Of {kurmanci["entries"]:,} Kurmancî entries, {kurmanci["headword_entries"]:,} are headwords with a
  definition that are not inflected-form pages.
- **{every["definition_pending"]:,} entries have no definition yet.** The wiki shows "the meaning is
  not written yet" on them. They are kept, with `definition_pending = 1` and no row in `senses`.
- **Recordings are mostly not Kurdish.** {audio_line}
- **Most words are not Kurdish.** This is the Kurdish-language Wiktionary: it describes words of
  {report["language_count"]:,} language codes in Kurdish. Filter on `language_code`.
- **Parsing is heuristic.** The wiki is free-form. {report["unclassified_section_count"]:,} sections
  have headings we could not classify; they are kept as `other`, with their text and HTML.

## Row counts

| Table | Rows |
|---|---:|
{rows}

## Coverage

| Scope | Entries | Senses | IPA | Audio | Etymology | Translations | Bot-made |
|---|---:|---:|---:|---:|---:|---:|---:|
{coverage_rows}

## Most repeated definitions

Many entries share a stock gloss, such as "Paşnavek e." (a surname). Allow for this in any
frequency or embedding work.

| Definition | Senses |
|---|---:|
{common}

## Integrity checks

| Check | Result |
|---|---:|
| Pages that failed to parse | {report["parse_errors"]:,} |
| Duplicate `entry_key` values | {report["duplicate_entry_keys"]:,} |
| Part-of-speech sections with no senses | {report["pos_sections_without_senses"]:,} |
| Entries with no senses (excluding conjugation pages) | {report["entries_without_senses"]:,} |
| Pages only in the older ZIM (`in_latest_dump = 0`) | {report["pages_only_in_older_zim"]:,} |

## Media

| Kind | Role | Status | Files | Size |
|---|---|---|---:|---:|
{media_rows}

## Media licences

Licences come from Wikimedia Commons, per file. `(unknown)` means none could be confirmed: check
the source before reusing that file.

| Licence | Files |
|---|---:|
{licence_rows}

## Most common unclassified headings

| Heading | Sections |
|---|---:|
{headings}
"""


def write_report(
    conn: sqlite3.Connection, build_meta: dict[str, str], directory: Path
) -> dict[str, Any]:
    directory.mkdir(parents=True, exist_ok=True)
    report = build_report(conn, build_meta)
    (directory / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (directory / "QUALITY.md").write_text(render_markdown(report), encoding="utf-8")
    return report
