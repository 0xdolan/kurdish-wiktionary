"""Export the release SQLite database to SQL, CSV, Parquet, JSONL and Excel."""

from __future__ import annotations

import csv
import gzip
import json
import re
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
import xlsxwriter  # type: ignore[import-untyped]

from src.dataset.schema import INDEXES, TABLE_BY_NAME, TABLES, Table, create_table_sql
from src.dataset.sections import POS_LABELS, SECTION_LABELS

Progress = Callable[[str], None]

EXCEL_MAX_DATA_ROWS = 1_000_000  # Excel allows 1,048,576 rows; keep a round, safe page size.
EXCEL_MAX_CELL = 32_767
EXCEL_SHEETS_PER_FILE = 4
_BATCH = 10_000
_SQL_ROWS_PER_INSERT = 200
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")
# Project fonts: Manrope for left-to-right text, Sahel for right-to-left text.
FONT_LTR = "Manrope"
FONT_RTL = "Sahel"
_RTL_TEXT = re.compile(r"[\u0590-\u08FF\uFB1D-\uFDFF\uFE70-\uFEFF]")

# Too large or too technical for a spreadsheet; available in the other formats.
EXCEL_SKIP = frozenset({"section_html", "inflection_tables"})
CSV_SKIP = frozenset({"section_html"})
SQL_SEPARATE = frozenset({"section_html"})

# Excel gets the forms of real headwords only: bot-made form pages repeat these same tables.
EXCEL_QUERIES: dict[str, str] = {
    "inflection_forms": (
        "SELECT f.* FROM inflection_forms f JOIN entries e ON e.entry_id = f.entry_id"
        " WHERE e.pos_list NOT LIKE '%_form%' OR e.pos_list LIKE '%verb_conjugation%'"
    ),
}

_ARROW_TYPES = {"BIGINT": pa.int64(), "INTEGER": pa.int64(), "TEXT": pa.large_string()}


def _rows(conn: sqlite3.Connection, sql: str) -> Iterator[Sequence[Any]]:
    cursor = conn.execute(sql)
    while batch := cursor.fetchmany(_BATCH):
        yield from batch


def _column_names(table: Table) -> list[str]:
    return [column.name for column in table.columns]


# ---- CSV -------------------------------------------------------------------------------------


def export_csv(conn: sqlite3.Connection, directory: Path, progress: Progress) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        if table.name in CSV_SKIP:
            continue
        path = directory / f"{table.name}.csv"
        # utf-8-sig so Excel, which assumes a legacy code page otherwise, shows Kurdish correctly.
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(_column_names(table))
            writer.writerows(_rows(conn, f"SELECT * FROM {table.name}"))
        progress(f"csv {table.name}")


# ---- Parquet ---------------------------------------------------------------------------------


def export_parquet(conn: sqlite3.Connection, directory: Path, progress: Progress) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for table in TABLES:
        schema = pa.schema(
            [(column.name, _ARROW_TYPES[column.sql_type]) for column in table.columns]
        )
        cursor = conn.execute(f"SELECT * FROM {table.name}")
        with pq.ParquetWriter(
            directory / f"{table.name}.parquet", schema, compression="zstd"
        ) as out:
            while batch := cursor.fetchmany(100_000):
                columns = list(zip(*batch, strict=True))
                out.write_table(
                    pa.Table.from_arrays(
                        [
                            pa.array(list(col), type=field.type)
                            for col, field in zip(columns, schema, strict=True)
                        ],
                        schema=schema,
                    )
                )
        progress(f"parquet {table.name}")


# ---- SQL -------------------------------------------------------------------------------------


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, int | float):
        return str(value)
    text = str(value).replace("\x00", "").replace("'", "''")
    return f"'{text}'"


def write_schema_sql(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    statements = [create_table_sql(table) + ";" for table in TABLES]
    statements.extend(f"{statement};" for statement in INDEXES)
    path.write_text(
        "-- Kurdish Wiktionary schema. Runs unchanged on PostgreSQL and SQLite.\n\n"
        + "\n\n".join(statements)
        + "\n",
        encoding="utf-8",
    )


def _write_inserts(handle: Any, conn: sqlite3.Connection, table: Table) -> None:
    names = ", ".join(_column_names(table))
    handle.write(f"\n-- {table.name}\nBEGIN;\n")
    pending: list[str] = []
    for row in _rows(conn, f"SELECT * FROM {table.name}"):
        pending.append("(" + ", ".join(_sql_literal(value) for value in row) + ")")
        if len(pending) == _SQL_ROWS_PER_INSERT:
            handle.write(
                f"INSERT INTO {table.name} ({names}) VALUES\n" + ",\n".join(pending) + ";\n"
            )
            pending.clear()
    if pending:
        handle.write(f"INSERT INTO {table.name} ({names}) VALUES\n" + ",\n".join(pending) + ";\n")
    handle.write("COMMIT;\n")


def export_sql(conn: sqlite3.Connection, directory: Path, progress: Progress) -> None:
    write_schema_sql(directory / "wiktionary_schema.sql")
    with gzip.open(
        directory / "wiktionary_data.sql.gz", "wt", encoding="utf-8", compresslevel=6
    ) as handle:
        handle.write("-- Kurdish Wiktionary data. Load wiktionary_schema.sql first.\n")
        for table in TABLES:
            if table.name not in SQL_SEPARATE:
                _write_inserts(handle, conn, table)
                progress(f"sql {table.name}")
    with gzip.open(
        directory / "wiktionary_section_html.sql.gz", "wt", encoding="utf-8", compresslevel=6
    ) as handle:
        for name in sorted(SQL_SEPARATE):
            _write_inserts(handle, conn, TABLE_BY_NAME[name])
            progress(f"sql {name}")


# ---- JSONL -----------------------------------------------------------------------------------

_NESTED: dict[str, tuple[str, list[str]]] = {
    "headwords": ("headwords", ["pos", "homograph", "headword", "gender"]),
    "pronunciations": ("pronunciations", ["kind", "value", "qualifier", "media_id"]),
    "etymologies": ("etymologies", ["etymology"]),
    "senses": (
        "senses",
        ["sense_id", "parent_sense_id", "ordinal", "depth", "pos", "labels", "definition"],
    ),
    "examples": ("examples", ["sense_id", "example", "translation", "transliteration"]),
    "quotations": (
        "quotations",
        ["sense_id", "year", "author", "work", "passage", "transliteration", "translation"],
    ),
    "translations": (
        "translations",
        [
            "gloss",
            "target_language",
            "target_code",
            "term",
            "term_page",
            "transliteration",
            "gender",
        ],
    ),
    "relations": ("relations", ["sense_id", "relation_type", "term", "term_page", "qualifier"]),
    "references": ("reference_notes", ["note"]),
}


def _child_stream(
    conn: sqlite3.Connection, table: str, columns: list[str]
) -> Iterator[tuple[Any, dict[str, Any]]]:
    selected = ", ".join(columns)
    for row in conn.execute(f"SELECT entry_id, {selected} FROM {table} ORDER BY entry_id"):
        yield (
            row[0],
            {
                name: value
                for name, value in zip(columns, row[1:], strict=True)
                if value is not None
            },
        )


def export_jsonl(database: Path, path: Path, progress: Progress) -> int:
    """One nested object per entry: the shape most NLP users want, streaming to low memory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    streams: dict[str, Iterator[tuple[Any, dict[str, Any]]]] = {}
    heads: dict[str, tuple[Any, dict[str, Any]] | None] = {}
    for key, (table, columns) in _NESTED.items():
        stream_conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        streams[key] = _child_stream(stream_conn, table, columns)
        heads[key] = next(streams[key], None)
    count = 0
    sql = (
        "SELECT e.entry_id, e.entry_key, e.title, e.language_name, e.language_code, e.pos_list,"
        " e.is_auto_generated, e.auto_source_page, p.page_kind, p.revision_id, p.last_edited, p.url"
        " FROM entries e JOIN pages p ON p.page_id = e.page_id ORDER BY e.entry_id"
    )
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as handle:
        for row in conn.execute(sql):
            record: dict[str, Any] = {
                "entry_key": row[1],
                "title": row[2],
                "language_name": row[3],
                "language_code": row[4],
                "pos": row[5].split(", ") if row[5] else [],
                "is_auto_generated": bool(row[6]),
                "auto_source_page": row[7],
                "page_kind": row[8],
                "revision_id": row[9],
                "last_edited": row[10],
                "url": row[11],
            }
            entry_id = row[0]
            for key in _NESTED:
                items: list[dict[str, Any]] = []
                head = heads[key]
                while head is not None and head[0] < entry_id:
                    head = next(streams[key], None)
                while head is not None and head[0] == entry_id:
                    items.append(head[1])
                    head = next(streams[key], None)
                heads[key] = head
                if items:
                    record[key] = items
            handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
            if count % 200_000 == 0:
                progress(f"jsonl {count}")
    return count


# ---- Excel -----------------------------------------------------------------------------------


def _excel_value(value: Any) -> Any:
    if isinstance(value, str):
        cleaned = _ILLEGAL_XML.sub("", value)
        if len(cleaned) > EXCEL_MAX_CELL:
            return cleaned[: EXCEL_MAX_CELL - 1] + "…"
        return cleaned
    return value


def _new_workbook(path: Path, *, constant_memory: bool = True) -> Any:
    workbook = xlsxwriter.Workbook(
        str(path),
        {
            "constant_memory": constant_memory,
            # Dictionary text is data: "=x" must stay text, and URLs must not hit Excel's limit.
            "strings_to_formulas": False,
            "strings_to_urls": False,
            "strings_to_numbers": False,
        },
    )
    workbook.formats[0].set_font_name(FONT_LTR)
    return workbook


def _rtl_format(workbook: Any) -> Any:
    return workbook.add_format({"font_name": FONT_RTL, "reading_order": 2})


def _header_format(workbook: Any) -> Any:
    return workbook.add_format(
        {"font_name": FONT_LTR, "bold": True, "bg_color": "#0B7285", "font_color": "#FFFFFF"}
    )


def _wrap_format(workbook: Any) -> Any:
    return workbook.add_format({"font_name": FONT_LTR, "text_wrap": True, "valign": "top"})


def _write_cell(sheet: Any, row: int, column: int, value: Any, rtl: Any) -> None:
    cleaned = _excel_value(value)
    if cleaned is None:
        return
    if not isinstance(cleaned, str):
        sheet.write_number(row, column, cleaned)
    elif _RTL_TEXT.search(cleaned):
        sheet.write_string(row, column, cleaned, rtl)
    else:
        sheet.write_string(row, column, cleaned)


def _column_width(table: Table, index: int) -> int:
    column = table.columns[index]
    if column.sql_type != "TEXT":
        return 13
    return {
        "definition": 70,
        "text": 80,
        "etymology": 70,
        "passage": 70,
        "example": 60,
        "translation": 40,
        "note": 70,
        "url": 45,
        "source_url": 45,
    }.get(column.name, 24)


def _start_sheet(workbook: Any, table: Table, name: str, header: Any, names: list[str]) -> Any:
    sheet = workbook.add_worksheet(name)
    for index, column in enumerate(names):
        sheet.set_column(index, index, _column_width(table, index))
        sheet.write_string(0, index, column, header)
    sheet.freeze_panes(1, 0)
    return sheet


def _write_about_sheet(workbook: Any, table: Table, *, header: Any) -> None:
    about = workbook.add_worksheet("about")
    wrap = _wrap_format(workbook)
    about.set_column(0, 0, 24)
    about.set_column(1, 1, 90, wrap)
    about.write_string(0, 0, table.name, header)
    about.write_string(0, 1, table.description, wrap)
    about.write_string(1, 0, "licence")
    about.write_string(
        1,
        1,
        "Text from ku.wiktionary.org, CC BY-SA 4.0. Unofficial: not produced or endorsed by the "
        "Wikimedia Foundation.",
        wrap,
    )
    about.write_string(2, 0, "long cells")
    about.write_string(
        2,
        1,
        f"Excel cells hold {EXCEL_MAX_CELL} characters. Longer values end with … here; "
        "the CSV, Parquet and SQL files keep them whole.",
        wrap,
    )
    row = 4
    about.write_string(row, 0, "column", header)
    about.write_string(row, 1, "meaning", header)
    for offset, column in enumerate(table.columns, start=row + 1):
        about.write_string(offset, 0, column.name)
        about.write_string(offset, 1, column.description, wrap)


def _export_excel_table(
    conn: sqlite3.Connection,
    table: Table,
    sql: str,
    directory: Path,
    progress: Progress,
) -> list[str]:
    names = _column_names(table)
    produced: list[str] = []
    part = 1
    sheet_number = 1
    row_number = 0
    workbook: Any = None
    sheet: Any = None
    header: Any = None
    rtl: Any = None
    sheets_in_file = 0

    def open_workbook() -> None:
        nonlocal workbook, header, rtl, sheets_in_file
        filename = f"{table.name}.xlsx" if part == 1 else f"{table.name}.part{part:02d}.xlsx"
        produced.append(filename)
        workbook = _new_workbook(directory / filename)
        header = _header_format(workbook)
        rtl = _rtl_format(workbook)
        # constant_memory writes sheets in creation order, so the guide sheet comes first.
        _write_about_sheet(workbook, table, header=header)
        sheets_in_file = 0

    open_workbook()
    sheet = _start_sheet(workbook, table, f"{table.name}_1"[:31], header, names)
    sheets_in_file = 1
    for row in _rows(conn, sql):
        if row_number == EXCEL_MAX_DATA_ROWS:
            sheet.autofilter(0, 0, row_number, len(names) - 1)
            sheet_number += 1
            if sheets_in_file == EXCEL_SHEETS_PER_FILE:
                workbook.close()
                part += 1
                open_workbook()
            sheet = _start_sheet(
                workbook, table, f"{table.name}_{sheet_number}"[:31], header, names
            )
            sheets_in_file += 1
            row_number = 0
        row_number += 1
        for column, value in enumerate(row):
            _write_cell(sheet, row_number, column, value, rtl)
    sheet.autofilter(0, 0, max(row_number, 1), len(names) - 1)
    workbook.close()
    progress(f"excel {table.name}: {produced}")
    return produced


_LANGUAGE_DICTIONARY_SQL = """
SELECT e.title AS word, s.pos, h.gender, s.ordinal AS sense_number, s.labels, s.definition,
       (SELECT group_concat(x.example, ' | ') FROM examples x
        WHERE x.sense_id = s.sense_id) AS examples,
       (SELECT p.value FROM pronunciations p
        WHERE p.entry_id = e.entry_id AND p.kind = 'ipa' LIMIT 1) AS ipa,
       (SELECT t.etymology FROM etymologies t WHERE t.entry_id = e.entry_id LIMIT 1) AS etymology,
       e.is_auto_generated, pg.url
FROM senses s
JOIN entries e ON e.entry_id = s.entry_id
JOIN pages pg ON pg.page_id = e.page_id
LEFT JOIN headwords h ON h.section_id = s.section_id
WHERE e.language_code = ? AND s.depth = 0 AND s.pos NOT LIKE '%_form'
GROUP BY s.sense_id
ORDER BY e.title, s.sense_id
"""
_LANGUAGE_DICTIONARY_COLUMNS = (
    ("word", 24),
    ("pos", 14),
    ("gender", 10),
    ("sense_number", 8),
    ("labels", 18),
    ("definition", 70),
    ("examples", 50),
    ("ipa", 16),
    ("etymology", 50),
    ("is_auto_generated", 10),
    ("url", 40),
)


def export_language_dictionary(
    conn: sqlite3.Connection,
    *,
    code: str,
    name: str,
    path: Path,
    progress: Progress,
) -> int:
    """A ready-to-read one-sheet dictionary for people who only want the words."""
    workbook = _new_workbook(path)
    header = _header_format(workbook)
    wrap = _wrap_format(workbook)
    rtl = _rtl_format(workbook)
    about = workbook.add_worksheet("about")
    about.set_column(0, 0, 100, wrap)
    for index, line in enumerate(
        (
            f"{name} dictionary from the Kurdish Wiktionary dataset, one row per definition. "
            "Inflected-form entries are left out; they are in the senses workbook.",
            "is_auto_generated = 1 marks bot-made entries that the wiki warns may contain "
            "translation errors.",
            "Text from ku.wiktionary.org, CC BY-SA 4.0. Unofficial: not produced or endorsed by "
            "the Wikimedia Foundation.",
        )
    ):
        about.write_string(index, 0, line, wrap)
    sheet = workbook.add_worksheet(name[:31])
    for index, (column, width) in enumerate(_LANGUAGE_DICTIONARY_COLUMNS):
        sheet.set_column(index, index, width)
        sheet.write_string(0, index, column, header)
    sheet.freeze_panes(1, 1)
    count = 0
    cursor = conn.execute(_LANGUAGE_DICTIONARY_SQL, (code,))
    for row in cursor:
        if count == EXCEL_MAX_DATA_ROWS:
            progress(f"excel {name}: stopped at the Excel row limit")
            break
        count += 1
        for col_index, value in enumerate(row):
            _write_cell(sheet, count, col_index, value, rtl)
    sheet.autofilter(0, 0, max(count, 1), len(_LANGUAGE_DICTIONARY_COLUMNS) - 1)
    workbook.close()
    progress(f"excel dictionary {name}: {count} rows")
    return count


def export_overview_workbook(conn: sqlite3.Connection, path: Path, progress: Progress) -> None:
    """The start-here workbook: data dictionary, section types and counts."""
    workbook = _new_workbook(path, constant_memory=False)
    header = _header_format(workbook)
    wrap = _wrap_format(workbook)

    def sheet_from(name: str, columns: list[tuple[str, int]], rows: list[Sequence[Any]]) -> None:
        sheet = workbook.add_worksheet(name)
        for index, (column, width) in enumerate(columns):
            sheet.set_column(index, index, width)
            sheet.write_string(0, index, column, header)
        for r_index, row in enumerate(rows, start=1):
            for c_index, value in enumerate(row):
                if value is None:
                    continue
                if isinstance(value, str):
                    sheet.write_string(r_index, c_index, value, wrap)
                else:
                    sheet.write_number(r_index, c_index, value)
        sheet.freeze_panes(1, 0)
        sheet.autofilter(0, 0, max(len(rows), 1), len(columns) - 1)

    sheet_from(
        "tables",
        [("table", 22), ("rows", 14), ("what it holds", 90)],
        [
            (
                table.name,
                conn.execute(f"SELECT COUNT(*) FROM {table.name}").fetchone()[0],
                table.description,
            )
            for table in TABLES
        ],
    )
    sheet_from(
        "columns",
        [("table", 22), ("column", 22), ("type", 10), ("meaning", 90)],
        [
            (table.name, column.name, column.sql_type, column.description)
            for table in TABLES
            for column in table.columns
        ],
    )
    sheet_from(
        "section_types",
        [("section_type", 22), ("Kurmancî", 22), ("English", 22), ("sections", 12)],
        [
            (
                kind,
                SECTION_LABELS.get(kind, (kind, kind))[0],
                SECTION_LABELS.get(kind, (kind, kind))[1],
                count,
            )
            for kind, count in conn.execute(
                "SELECT section_type, COUNT(*) FROM sections GROUP BY 1 ORDER BY 2 DESC"
            )
        ],
    )
    sheet_from(
        "parts_of_speech",
        [("pos", 22), ("Kurmancî", 22), ("English", 26), ("sections", 12)],
        [
            (
                pos,
                POS_LABELS.get(pos, (pos, pos))[0],
                POS_LABELS.get(pos, (pos, pos))[1],
                count,
            )
            for pos, count in conn.execute(
                "SELECT pos, COUNT(*) FROM sections WHERE pos IS NOT NULL"
                " GROUP BY 1 ORDER BY 2 DESC"
            )
        ],
    )
    sheet_from(
        "languages",
        [("language_code", 14), ("language_name", 30), ("entries", 12), ("senses", 12)],
        list(
            conn.execute(
                "SELECT language_code, language_name, COUNT(*), SUM(sense_count) FROM entries"
                " GROUP BY 1, 2 ORDER BY 3 DESC"
            )
        ),
    )
    workbook.close()
    progress("excel overview")


def export_excel(conn: sqlite3.Connection, directory: Path, progress: Progress) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    export_overview_workbook(conn, directory / "00_START_HERE_overview.xlsx", progress)
    export_language_dictionary(
        conn,
        code="ku",
        name="Kurmanci",
        path=directory / "dictionary_kurmanci.xlsx",
        progress=progress,
    )
    export_language_dictionary(
        conn,
        code="ckb",
        name="Sorani",
        path=directory / "dictionary_sorani.xlsx",
        progress=progress,
    )
    for table in TABLES:
        if table.name in EXCEL_SKIP:
            continue
        query = EXCEL_QUERIES.get(table.name, f"SELECT * FROM {table.name}")
        _export_excel_table(conn, table, query, directory, progress)
