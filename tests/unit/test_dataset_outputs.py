# ruff: noqa: E501 - HTML fixtures copied from real pages.
"""Media helpers, exporters and MDict rendering on a tiny database built by the real parser."""

import asyncio
import csv
import gzip
import hashlib
import json
import sqlite3
import time
import zipfile
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from src.dataset import bundle, entry_html, exporters, mdict_build, quality, verify
from src.dataset import media as media_stage
from src.dataset.build_db import _write_media, _write_rows, create_database
from src.dataset.page_parser import media_id_for, parse_page
from src.dataset.schema import INDEXES, TABLES

AUDIO = "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/aa/X.wav/X.wav.mp3"
HTML = (
    '<div class="mw-parser-output">'
    '<div class="mw-heading mw-heading2"><h2 id="K"><span class="besazimani" id="ku">Kurmancî</span></h2></div>'
    '<div class="mw-heading mw-heading3"><h3 id="B">Bilêvkirin</h3></div>'
    f'<ul><li><a role="button" href="{AUDIO}">guhdar</a></li></ul>'
    '<div class="mw-heading mw-heading3"><h3 id="N">Navdêr</h3></div>'
    '<figure><img src="./_assets_/abc.jpg" data-file-width="10" data-file-height="20"><figcaption>Wêne</figcaption></figure>'
    "<ol><li>=SUM(A1) it's a <a href=\"dost#K\" title=\"dost\">heval</a>"
    '<ul><li><span class="benimune">Nimûneyekê</span><span class="stubedit">edit</span></li></ul></li></ol>'
    '<div class="mw-heading mw-heading4"><h4 id="H">Hevmane</h4></div>'
    '<ul><li><span class="Latn" lang="ku"><a href="dost#K" title="dost">dost</a></span></li></ul>'
    "</div><!--htdig_noindex-->"
)


@pytest.fixture
def database(tmp_path: Path) -> Path:
    path = tmp_path / "sql" / "t.sqlite"
    conn = create_database(path)
    conn.execute("CREATE TABLE build_errors (title TEXT, error TEXT)")
    parsed = parse_page(html=HTML, title="heval", page_id=1, source_zim="maxi", in_latest_dump=True)
    _write_rows(conn, parsed.rows)
    _write_media(conn, parsed.media)
    conn.execute("INSERT INTO redirects VALUES ('hevall', 'heval', 'hard')")
    conn.commit()
    conn.close()
    return path


@pytest.fixture(autouse=True)
def _no_download_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_stage, "MEDIA_MIN_INTERVAL_S", 0.0)


def _conn(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path)


def _log(_message: str) -> None:
    return None


@pytest.mark.parametrize(
    ("payload", "mime"),
    [
        (b"RIFF\x9c%\x00\x00WEBPVP8 ", "image/webp"),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", "audio/wav"),
        (b"\x89PNG\r\n", "image/png"),
        (b"\xff\xd8\xff\xe0", "image/jpeg"),
        (b"ID3\x04", "audio/mpeg"),
        (b"\xff\xfb\x90", "audio/mpeg"),
        (b"OggS", "audio/ogg"),
        (b"<?xml?><svg ", "image/svg+xml"),
        (b"<html>", None),
    ],
)
def test_sniff_mime_reads_bytes_not_names(payload: bytes, mime: str | None) -> None:
    assert media_stage.sniff_mime(payload) == mime


def test_store_path_is_ascii_and_sharded() -> None:
    assert media_stage.store_path("abcd", "audio", "audio/mpeg") == "audio/ab/abcd.mp3"
    assert media_stage.store_path("abcd", "image", "image/webp") == "images/ab/abcd.webp"


def test_original_url_uses_mediawiki_hash_path() -> None:
    assert media_stage.original_url_for("LL-Q36368_(kur)-Dildadil-heval.wav").startswith(
        "https://upload.wikimedia.org/wikipedia/commons/a/aa/"
    )


def test_adopt_previous_downloads_links_file(database: Path, tmp_path: Path) -> None:
    legacy = tmp_path / "legacy" / "heval" / "audio"
    legacy.mkdir(parents=True)
    digest = hashlib.sha256(AUDIO.encode()).hexdigest()[:10]
    (legacy / f"X.wav-{digest}.mp3").write_bytes(b"ID3data")
    conn = _conn(database)
    store = tmp_path / "store"
    assert media_stage.adopt_previous_downloads(conn, store, tmp_path / "legacy") == 1
    status, local = conn.execute(
        "SELECT status, local_path FROM media WHERE media_id=?", (media_id_for(AUDIO),)
    ).fetchone()
    assert status == "present"
    assert (store / local).read_bytes() == b"ID3data"


def test_rediscover_store_reconnects_files_after_reparse(database: Path, tmp_path: Path) -> None:
    media_id = media_id_for(AUDIO)
    target = tmp_path / "store" / "audio" / media_id[:2] / f"{media_id}.mp3"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"ID3data")
    conn = _conn(database)
    assert media_stage.rediscover_store(conn, tmp_path / "store") == 1
    assert conn.execute(
        "SELECT status, local_path FROM media WHERE media_id=?", (media_id,)
    ).fetchone() == ("present", f"audio/{media_id[:2]}/{media_id}.mp3")


def test_licences_survive_a_rebuild(database: Path) -> None:
    conn = _conn(database)
    conn.execute("UPDATE media SET license='CC BY-SA 4.0', artist='A' WHERE kind='audio'")
    conn.commit()
    saved = media_stage.saved_licences(database)
    conn.execute("UPDATE media SET license=NULL, artist=NULL")
    media_stage.restore_licences(conn, saved)
    assert conn.execute("SELECT license, artist FROM media WHERE kind='audio'").fetchone() == (
        "CC BY-SA 4.0",
        "A",
    )
    assert media_stage.saved_licences(database.with_name("nope.sqlite")) == []


def test_audit_detects_vanished_file(database: Path, tmp_path: Path) -> None:
    conn = _conn(database)
    conn.execute(
        "UPDATE media SET status='present', bytes=5, local_path='audio/aa/gone.mp3' WHERE kind='audio'"
    )
    report = media_stage.audit(conn, tmp_path)
    assert report["missing"] == 2  # The audio that vanished and the image never extracted.
    assert conn.execute("SELECT status FROM media WHERE kind='audio'").fetchone()[0] == "missing"


def test_download_retries_429_and_falls_back_to_original(
    database: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        calls.append(url)
        if "transcoded" in url:
            return httpx.Response(404)
        if calls.count(url) == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, content=b"RIFF\x00\x00\x00\x00WAVEfmt ")

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        media_stage.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    conn = _conn(database)
    conn.execute("UPDATE media SET commons_file='X.wav' WHERE kind='audio'")
    counts = asyncio.run(media_stage.download_missing(conn, tmp_path))
    assert counts == {"downloaded": 1, "fallback": 1, "failed": 0}
    status, mime = conn.execute("SELECT status, mime FROM media WHERE kind='audio'").fetchone()
    assert (status, mime) == ("present", "audio/wav")


def test_pacer_spaces_requests_and_waits_after_429(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(media_stage, "MEDIA_MIN_INTERVAL_S", 0.05)

    async def run() -> tuple[float, float]:
        pacer = media_stage._Pacer(10**9)
        start = time.monotonic()
        await asyncio.gather(pacer.wait(), pacer.wait(), pacer.wait())
        spaced = time.monotonic() - start
        pacer.back_off(0.2)
        start = time.monotonic()
        await pacer.wait()
        return spaced, time.monotonic() - start

    spaced, paused = asyncio.run(run())
    assert spaced >= 0.09
    assert paused >= 0.19


def test_download_rejects_non_media_response(
    database: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        media_stage.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(
            transport=httpx.MockTransport(lambda _r: httpx.Response(200, content=b"<html>")),
            **kwargs,
        ),
    )
    conn = _conn(database)
    assert asyncio.run(media_stage.download_missing(conn, tmp_path))["failed"] == 1
    assert conn.execute("SELECT status FROM media WHERE kind='audio'").fetchone()[0] == "failed"


def test_sql_export_loads_back_into_sqlite(database: Path, tmp_path: Path) -> None:
    exporters.export_sql(_conn(database), tmp_path / "sql_out", _log)
    target = sqlite3.connect(tmp_path / "copy.sqlite")
    target.executescript((tmp_path / "sql_out" / "wiktionary_schema.sql").read_text(encoding="utf-8"))
    for name in ("wiktionary_data.sql.gz", "wiktionary_section_html.sql.gz"):
        with gzip.open(tmp_path / "sql_out" / name, "rt", encoding="utf-8") as handle:
            target.executescript(handle.read())
    source = _conn(database)
    for table in TABLES:
        sql = f"SELECT * FROM {table.name} ORDER BY 1"
        assert target.execute(sql).fetchall() == source.execute(sql).fetchall(), table.name


def test_schema_sql_has_every_index(tmp_path: Path) -> None:
    path = tmp_path / "schema.sql"
    exporters.write_schema_sql(path)
    text = path.read_text(encoding="utf-8")
    assert all(statement in text for statement in INDEXES)


def test_csv_opens_with_bom_and_keeps_kurdish(database: Path, tmp_path: Path) -> None:
    exporters.export_csv(_conn(database), tmp_path / "csv", _log)
    assert not (tmp_path / "csv" / "section_html.csv").exists()
    raw = (tmp_path / "csv" / "entries.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    with (tmp_path / "csv" / "entries.csv").open(encoding="utf-8-sig", newline="") as handle:
        row = next(csv.DictReader(handle))
    assert row["language_name"] == "Kurmancî"


def test_parquet_round_trip_with_empty_tables(database: Path, tmp_path: Path) -> None:
    exporters.export_parquet(_conn(database), tmp_path / "parquet", _log)
    senses = pq.read_table(tmp_path / "parquet" / "senses.parquet")
    assert senses.num_rows == 1
    assert pq.read_table(tmp_path / "parquet" / "translations.parquet").num_rows == 0


def test_jsonl_nests_children_under_entry(database: Path, tmp_path: Path) -> None:
    path = tmp_path / "entries.jsonl.gz"
    assert exporters.export_jsonl(database, path, _log) == 1
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        record = json.loads(handle.readline())
    assert record["entry_key"] == "heval|ku"
    assert record["relations"][0]["term"] == "dost"
    assert record["pronunciations"][0]["kind"] == "audio"
    assert record["senses"][0]["pos"] == "noun"


def _sheet_xml(path: Path, sheet: str = "sheet2") -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read(f"xl/worksheets/{sheet}.xml").decode("utf-8")


def test_excel_keeps_formula_like_text_as_text(database: Path, tmp_path: Path) -> None:
    exporters.export_excel(_conn(database), tmp_path / "excel", _log)
    xml = _sheet_xml(tmp_path / "excel" / "senses.xlsx")
    assert "=SUM(A1)" in xml
    assert "<f>" not in xml
    assert not (tmp_path / "excel" / "section_html.xlsx").exists()
    assert (tmp_path / "excel" / "00_START_HERE_overview.xlsx").is_file()
    assert (tmp_path / "excel" / "dictionary_kurmanci.xlsx").is_file()


def test_excel_uses_manrope_and_sahel_for_rtl_text(tmp_path: Path) -> None:
    path = tmp_path / "fonts.xlsx"
    workbook = exporters._new_workbook(path)
    sheet = workbook.add_worksheet("s")
    rtl = exporters._rtl_format(workbook)
    exporters._write_cell(sheet, 0, 0, "heval", rtl)
    exporters._write_cell(sheet, 1, 0, "هەڤاڵ", rtl)
    workbook.close()
    with zipfile.ZipFile(path) as archive:
        styles = archive.read("xl/styles.xml").decode("utf-8")
        cells = archive.read("xl/worksheets/sheet1.xml").decode("utf-8")
    assert 'val="Manrope"' in styles
    assert 'val="Sahel"' in styles
    assert 'readingOrder="2"' in styles
    assert '<c r="A1" t="inlineStr">' in cells
    assert '<c r="A2" s="1" t="inlineStr">' in cells


def test_excel_splits_sheets_and_files_at_limits(
    database: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(exporters, "EXCEL_MAX_DATA_ROWS", 2)
    monkeypatch.setattr(exporters, "EXCEL_SHEETS_PER_FILE", 2)
    conn = _conn(database)
    table = exporters.TABLE_BY_NAME["redirects"]
    conn.executemany(
        "INSERT INTO redirects VALUES (?, 'heval', 'hard')",
        [(f"a{i}",) for i in range(8)],
    )
    produced = exporters._export_excel_table(
        conn,
        table,
        "SELECT * FROM redirects",
        tmp_path,
        _log,
    )
    assert produced == ["redirects.xlsx", "redirects.part02.xlsx", "redirects.part03.xlsx"]


def test_excel_value_truncates_and_strips_control_characters() -> None:
    assert exporters._excel_value("a\x01b") == "ab"
    long = exporters._excel_value("x" * 40_000)
    assert len(long) == exporters.EXCEL_MAX_CELL
    assert long.endswith("…")
    assert exporters._excel_value(5) == 5


def test_render_article_links_media_and_removes_wiki_chrome(database: Path, tmp_path: Path) -> None:
    conn = _conn(database)
    rows = conn.execute(
        "SELECT s.section_id, s.entry_id, s.ordinal, s.level, s.heading, s.section_type, s.pos,"
        " COALESCE(h.html, '') FROM sections s LEFT JOIN section_html h USING (section_id)"
        " ORDER BY s.section_id"
    ).fetchall()
    entry_id = rows[0][1]
    local = {
        media_id_for(AUDIO): "audio/aa/x.mp3",
        media_id_for("_assets_/abc.jpg"): "images/bb/y.webp",
    }
    article = mdict_build.render_article(
        "heval",
        "https://ku.wiktionary.org/wiki/heval",
        rows,
        {entry_id: ("Kurmancî", "ku")},
        local,
    )
    assert 'href="sound://audio/aa/x.mp3"' in article
    assert 'data-audio="audio/aa/x.mp3"' in article
    assert 'src="images/bb/y.webp"' in article
    assert 'href="entry://dost"' in article
    assert "benimune" not in article
    assert "stubedit" not in article
    assert 'class="wk-lang"' in article
    assert 'class="wk-gallery"' in article
    assert 'class="wk-fig"' in article


def test_unbalanced_fragment_cannot_close_the_article() -> None:
    assert "</div>" not in mdict_build.clean_fragment("<p>a</p></div>")


def test_audio_we_lack_keeps_a_web_link() -> None:
    fragment = f'<a role="button" href="{AUDIO}">guhdar</a>'
    out = mdict_build.rewrite_media(fragment, {})
    assert f'href="{AUDIO}"' in out
    assert "wk-voice--web" in out


def test_rtl_headword_gets_rtl_direction() -> None:
    url = "https://ku.wiktionary.org/wiki/x"
    assert '<h1 class="wk-word" dir="rtl">' in mdict_build.render_article("هەڤاڵ", url, [], {}, {})
    assert '<h1 class="wk-word">' in mdict_build.render_article("heval", url, [], {}, {})


def test_each_voice_gets_its_own_card_with_dialect_and_speaker() -> None:
    first = "https://upload.wikimedia.org/wikipedia/commons/transcoded/a/aa/LL-Q36368_(kur)-Dildadil-heval.wav/x.mp3"
    second = "https://upload.wikimedia.org/wikipedia/commons/transcoded/3/32/LL-Q36163_(kmr)-Ebulfîda-heval.wav/y.mp3"
    fragment = (
        '<ul><li><span class="IPA">/hɛˈvɑːl/</span></li>'
        f'<li><table class="audiotable"><tr><td><span class="label-content">Amed</span></td><td><a href="{first}">g</a></td></tr></table></li>'
        f'<li><table class="audiotable"><tr><td></td><td><a href="{second}">g</a></td></tr></table></li>'
        '<li><a href="entry://kîte">Kîtekirin</a>: he·val</li></ul>'
    )
    out = entry_html.render_pronunciation(fragment, {media_id_for(first): "audio/aa/a.mp3"})
    assert out is not None
    assert out.count("wk-voice-name") == 2
    assert '<span class="wk-voice-name">Amed</span><span class="wk-voice-sub">Dildadil</span>' in out
    assert '<span class="wk-voice-name">Ebulfîda</span>' in out
    assert "/hɛˈvɑːl/" in out
    assert "he·val" in out
    assert 'title="' not in out.replace('href="entry://kîte"', "")
    assert '<span class="wk-pron-label"><a href="entry://kîte">Kîtekirin</a></span>' in out


def test_wrap_tables_makes_data_tables_scroll_and_layout_tables_stack() -> None:
    plain = entry_html.wrap_tables("<table><tr><td>a</td></tr></table>")
    assert plain.startswith('<div class="wk-table"><table>')
    nested = entry_html.wrap_tables("<table><tr><td><table><tr><td>a</td></tr></table></td></tr></table>")
    assert nested.startswith('<div class="wk-layout"><table>')
    assert '<div class="wk-table"><table><tr><td>a' in nested
    audio = '<table class="audiotable"><tr><td>a</td></tr></table>'
    assert entry_html.wrap_tables(audio) == audio


def test_figures_leave_the_text_flow_for_a_gallery() -> None:
    text, gallery = entry_html.extract_gallery(
        '<figure class="x"><img src="i.webp" width="9"><figcaption>Du <b>heval</b>.</figcaption></figure><p>t</p>'
    )
    assert text == "<p>t</p>"
    assert 'alt="Du heval."' in gallery
    assert "<figcaption>Du <b>heval</b>.</figcaption>" in gallery
    assert entry_html.extract_gallery("<p>t</p>") == ("<p>t</p>", "")


def test_inline_colours_cannot_fight_the_themes() -> None:
    out = entry_html.render_section_body(
        "inflection", '<table style="color:red" width="5"><tr><td bgcolor="#fff">a</td></tr></table>', {}
    )
    assert "style=" not in out
    assert "bgcolor" not in out
    assert "width=" not in out


def test_long_translation_sections_start_closed_with_a_count() -> None:
    items = "".join(f"<li>{i}</li>" for i in range(30))
    closed = entry_html._section(1, "translations", None, "Werger", f"<ul>{items}</ul>")
    assert "open" not in closed.split(">", 1)[0]
    assert '<span class="wk-count">30</span>' in closed
    assert " open" in entry_html._section(2, "synonyms", None, "Hevmane", "<ul><li>a</li></ul>")


def test_only_first_language_opens_on_many_language_pages() -> None:
    url = "https://ku.wiktionary.org/wiki/x"
    rows = [(10 * i, i, i, 3, "Mane", "pos", "sense", "<ol><li>d</li></ol>") for i in range(1, 6)]
    languages = {i: (f"Ziman{i}", f"l{i}") for i in range(1, 6)}
    article = mdict_build.render_article("x", url, rows, languages, {})
    assert article.count('<details class="wk-lang" open') == 1
    assert article.count('<details class="wk-lang"') == 5


def test_packing_works_on_a_fresh_machine_without_a_logs_folder(tmp_path: Path) -> None:
    source = tmp_path / "dict.txt"
    source.write_text("heval\n<p>x</p>\n</>\n", encoding="utf-8")
    title, description = mdict_build.write_templates(
        tmp_path / "templates", version="1", zim_date="2026-08-25", entries=1
    )
    output = tmp_path / "out.mdx"
    mdict_build._pack(title, description, source, output, tmp_path / "new" / "logs" / "pack.log")
    assert output.is_file()


def test_record_format() -> None:
    assert mdict_build.format_record("a  b", "<x/>").endswith("\n</>\n")
    assert mdict_build.format_record("a  b", "<x/>").startswith("a b\n<link ")
    assert mdict_build.format_link("هه‌ڤال", "heval") == "هه‌ڤال\n@@@LINK=heval\n</>\n"


def test_alias_records_skip_existing_titles_and_dangling_targets(database: Path) -> None:
    conn = _conn(database)
    conn.execute("INSERT INTO redirects VALUES ('heval', 'heval', 'hard')")
    conn.execute("INSERT INTO redirects VALUES ('x', 'no-such-page', 'soft')")

    class Sink:
        text = ""

        def write(self, value: str) -> None:
            self.text += value

    sink = Sink()
    assert mdict_build.write_alias_records(conn, sink) == 1
    assert "hevall\n@@@LINK=heval" in sink.text


def test_quality_report_counts_and_markdown(database: Path, tmp_path: Path) -> None:
    conn = _conn(database)
    report = quality.write_report(conn, {"parse_errors": "0"}, tmp_path)
    assert report["row_counts"]["entries"] == 1
    assert report["coverage"]["kurmanci"]["with_senses_pct"] == 100.0
    assert report["duplicate_entry_keys"] == 0
    assert "bot-made" in (tmp_path / "QUALITY.md").read_text(encoding="utf-8")


def test_finalized_database_opens_from_read_only_storage(database: Path) -> None:
    conn = _conn(database)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("UPDATE pages SET title = title")
    conn.commit()
    bundle.finalize_database(conn)
    conn.close()
    assert not database.with_name(f"{database.name}-wal").exists()
    database.parent.chmod(0o555)
    database.chmod(0o444)
    try:
        reader = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        assert reader.execute("SELECT COUNT(*) FROM entries").fetchone() == (1,)
        reader.close()
    finally:
        database.parent.chmod(0o755)
        database.chmod(0o644)


def test_finalize_refuses_while_another_process_writes(database: Path) -> None:
    writer = _conn(database)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("UPDATE pages SET title = title")  # Holds the write lock, as a download does.
    other = sqlite3.connect(database, timeout=0.1)
    with pytest.raises((SystemExit, sqlite3.OperationalError)):
        bundle.finalize_database(other)
    writer.rollback()


def test_verify_matches_then_catches_changes(database: Path, tmp_path: Path) -> None:
    archive = tmp_path / "a.zim"
    archive.write_bytes(b"zim")
    expected = tmp_path / "expected.json"
    conn = _conn(database)
    verify.write_expected(conn, [archive], expected)
    assert verify.compare(conn, [archive], expected) == []

    # Download status lives in `media` and may change without being a difference.
    conn.execute("UPDATE media SET status = 'present'")
    assert verify.compare(conn, [archive], expected) == []

    conn.execute("UPDATE senses SET definition = 'changed'")
    assert verify.compare(conn, [archive], expected) == ["senses: same row count, but the contents differ"]
    conn.execute("DELETE FROM senses")
    assert verify.compare(conn, [archive], expected) == ["senses: 0 rows, expected 1"]

    archive.write_bytes(b"other")
    assert "ZIM differs from the published one: a.zim" in verify.compare(conn, [archive], expected)
    assert verify.compare(conn, [], expected)[0] == "ZIM not found: a.zim"


def test_data_dictionary_lists_every_column() -> None:
    text = bundle.data_dictionary()
    for table in TABLES:
        assert f"## `{table.name}`" in text
        assert all(f"`{column.name}`" in text for column in table.columns)


def test_render_template_fills_and_rejects_unknown_names() -> None:
    assert bundle.render_template("a {{x}}", {"x": "b"}) == "a b"
    with pytest.raises(KeyError):
        bundle.render_template("{{nope}}", {})
