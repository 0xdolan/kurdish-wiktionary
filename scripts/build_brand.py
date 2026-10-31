#!/usr/bin/env python3
# ruff: noqa: E501 - inline HTML layouts.
"""Render logos, screenshots, ads and the landing page from the real release data, in both themes.

All numbers come from build/release/quality/report.json and all screenshots from real outputs, so
marketing cannot drift from the dataset. Colours match assets/mdict/css/dictionary.css.
Usage: uv run python scripts/build_brand.py [stage ...]
Stages: logos screenshots creatives site (default: all).
"""

from __future__ import annotations

import html
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx
import xlsxwriter

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "assets" / "brand"
SRC = BRAND / "src"
EXPORT = BRAND / "export"
SHOTS = BRAND / "screenshots"
RELEASE = ROOT / "build" / "release"
SITE = ROOT / "site"
FONTS = ROOT / "assets" / "mdict" / "fonts"
CHROME = "google-chrome"
LOGO = SRC / "wiktionary-logo-ku.svg"
MANROPE_TTF_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/Manrope%5Bwght%5D.ttf"
KAGGLE_URL = "https://www.kaggle.com/datasets/zeroxdolan/wiktionary-wordlists"

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "bg": "#F6F8F9",
        "surface": "#FFFFFF",
        "raised": "#EEF2F4",
        "ink": "#101C22",
        "muted": "#566570",
        "line": "#DDE4E8",
        "accent": "#0B7285",
        "soft": "#E2F3F6",
        "highlight": "#B45309",
        "on_accent": "#FFFFFF",
        "code": "#101C22",
        "on_code": "#E9F0F2",
    },
    "dark": {
        "bg": "#0A1215",
        "surface": "#121C20",
        "raised": "#1A272C",
        "ink": "#E9F0F2",
        "muted": "#9DAFB7",
        "line": "#27363C",
        "accent": "#5CCBDE",
        "soft": "#123239",
        "highlight": "#F7B955",
        "on_accent": "#06181C",
        "code": "#071013",
        "on_code": "#E9F0F2",
    },
}

FONT_CSS = "".join(
    f"@font-face{{font-family:Manrope;font-weight:{w};src:url('file://{FONTS}/manrope/manrope-{s}-{w}.woff2')}}"
    for w in (400, 500, 600, 700)
    for s in ("latin", "latin-ext")
) + "".join(
    f"@font-face{{font-family:Sahel;font-weight:{w};src:url('file://{FONTS}/sahel/{name}.woff2')}}"
    for w, name in ((400, "Sahel-WOL"), (600, "Sahel-SemiBold-WOL"), (700, "Sahel-Bold-WOL"))
)


def report() -> dict:
    return json.loads((RELEASE / "quality" / "report.json").read_text(encoding="utf-8"))


def rounded(value: int) -> str:
    """Round down for marketing: never claim more than the data holds."""
    if value >= 1_000_000:
        return f"{int(value / 100_000) / 10:g}M+"
    if value >= 10_000:
        return f"{int(value / 1000)}K+"
    if value >= 1000:
        return f"{int(value / 100) / 10:g}K+"
    return str(value)


def stats(data: dict) -> dict[str, str]:
    rows = data["row_counts"]
    audio = sum(
        m["files"] for m in data["media"] if m["kind"] == "audio" and m["status"] == "present"
    )
    return {
        "entries": rounded(rows["entries"]),
        "senses": rounded(rows["senses"]),
        "translations": rounded(rows["translations"]),
        "languages": rounded(data["language_count"]),
        "audio": rounded(audio),
        "kurmanci": rounded(data["coverage"]["kurmanci"]["entries"]),
        "forms": rounded(rows["inflection_forms"]),
    }


def chrome_shot(
    page: Path,
    output: Path,
    width: int,
    height: int,
    *,
    transparent: bool = False,
    scale: int = 1,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        "--allow-file-access-from-files",
        f"--force-device-scale-factor={scale}",
        "--virtual-time-budget=4000",
        f"--window-size={width},{height}",
        f"--screenshot={output}",
    ]
    if transparent:
        command.append("--default-background-color=00000000")
    subprocess.run([*command, page.as_uri()], check=True, capture_output=True)


def shot_html(body: str, width: int, height: int, output: Path, theme: str, extra_css: str = "") -> None:
    t = THEMES[theme]
    document = f"""<!doctype html><html lang="en"><meta charset="utf-8"><style>
{FONT_CSS}
*{{box-sizing:border-box;margin:0}}
html,body{{width:{width}px;height:{height}px;overflow:hidden}}
body{{font-family:Manrope,Sahel,sans-serif;color:{t["ink"]};background:{t["bg"]}}}
.num{{font-weight:700;letter-spacing:-.02em}}
.accent{{color:{t["accent"]}}}
.small{{color:{t["muted"]};font-weight:500}}
{extra_css}
</style><body>{body}</body></html>"""
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / "page.html"
        page.write_text(document, encoding="utf-8")
        chrome_shot(page, output, width, height)


def logo_plate(height: int, theme: str = "light") -> str:
    """The logo was drawn for white (its Arabic lines are white with a shadow), so it sits on white."""
    pad = max(height // 10, 5)
    border = f"border:1px solid {THEMES[theme]['line']};" if theme == "light" else ""
    return (
        f'<span style="display:inline-block;flex:none;align-self:flex-start;line-height:0;background:#fff;{border}border-radius:{pad + 2}px;padding:{pad}px">'
        f'<img src="{LOGO.as_uri()}" height="{height}" width="{round(height * 135 / 155)}" alt="Wîkîferheng"></span>'
    )


def logos() -> None:
    """High-resolution exports of the vector redraw, on white, plus the untouched original."""
    EXPORT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOGO, EXPORT / LOGO.name)
    shutil.copy2(LOGO.with_suffix(".png"), EXPORT / "wiktionary-logo-ku-original.png")
    for size in (64, 192, 512, 1024, 2048):
        inner = round(size * 0.88)
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "logo.html"
            page.write_text(
                f"<!doctype html><style>*{{margin:0}}html,body{{width:{size}px;height:{size}px;background:#fff;display:flex;align-items:center;justify-content:center}}</style>"
                f'<img src="{LOGO.as_uri()}" height="{inner}" width="{round(inner * 135 / 155)}" alt="">',
                encoding="utf-8",
            )
            chrome_shot(page, EXPORT / f"logo-{size}.png", size, size)


# ---- Screenshots from real outputs ----------------------------------------------------------


def _record(dict_txt: Path, headwords: set[str]) -> dict[str, str]:
    found: dict[str, str] = {}
    with dict_txt.open(encoding="utf-8") as handle:
        current = None
        for line in handle:
            if current is None:
                current = line.rstrip("\n")
                body: list[str] = []
            elif line == "</>\n":
                if current in headwords:
                    found[current] = "".join(body)
                    if len(found) == len(headwords):
                        break
                current = None
            else:
                body.append(line)
    return found


def _entry_page(title: str, record: str, theme: str) -> Path:
    """A preview next to the MDD resources, so CSS, fonts, images and scripts load for real."""
    staging = RELEASE / "mdict" / "staging"
    preview = staging / f"preview-{title}-{theme}.html"
    resources = (staging / "resources").resolve()
    preview.write_text(
        f'<!doctype html><html lang="ku" data-theme="{theme}"><meta charset="utf-8"><base href="{resources.as_uri()}/">'
        f"<body>{record}</body></html>",
        encoding="utf-8",
    )
    return preview


def _manrope_fontconfig() -> Path:
    """Make Manrope visible to LibreOffice without installing anything on the system."""
    folder = RELEASE / ".fonts"
    font = folder / "Manrope-Variable.ttf"
    if not font.is_file():
        folder.mkdir(parents=True, exist_ok=True)
        font.write_bytes(httpx.get(MANROPE_TTF_URL, follow_redirects=True, timeout=60).content)
    config = folder / "fonts.conf"
    config.write_text(
        f'<?xml version="1.0"?><fontconfig><dir>{folder.resolve()}</dir>'
        "<dir>/usr/share/fonts</dir></fontconfig>",
        encoding="utf-8",
    )
    return config


def _excel_excerpt(output: Path) -> None:
    """LibreOffice renders a 28-row excerpt of the real dictionary workbook's rows."""
    conn = sqlite3.connect(f"file:{RELEASE / 'sql' / 'wiktionary.sqlite'}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT e.title, s.pos, s.ordinal, s.definition FROM senses s JOIN entries e USING (entry_id)"
        " WHERE e.language_code = 'ku' AND s.depth = 0 AND s.pos = 'noun' AND LENGTH(s.definition) BETWEEN 20 AND 90"
        " AND e.title >= 'heval' ORDER BY e.title, s.sense_id LIMIT 28"
    ).fetchall()
    with tempfile.TemporaryDirectory() as folder:
        workbook_path = Path(folder) / "dictionary.xlsx"
        workbook = xlsxwriter.Workbook(str(workbook_path))
        workbook.formats[0].set_font_name("Manrope")
        sheet = workbook.add_worksheet("Kurmanci")
        header = workbook.add_format(
            {"font_name": "Manrope", "bold": True, "bg_color": "#0B7285", "font_color": "#FFFFFF"}
        )
        sheet.set_landscape()
        sheet.fit_to_pages(1, 1)
        for col, (name, width) in enumerate(
            (("word", 18), ("pos", 9), ("sense_number", 13), ("definition", 88))
        ):
            sheet.set_column(col, col, width)
            sheet.write(0, col, name, header)
        for r_index, row in enumerate(rows, start=1):
            sheet.write_row(r_index, 0, row)
        workbook.close()
        subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", folder, str(workbook_path)],
            check=True,
            capture_output=True,
            env={**os.environ, "FONTCONFIG_FILE": str(_manrope_fontconfig())},
        )
        subprocess.run(
            ["convert", "-density", "130", f"{folder}/dictionary.pdf[0]", "-background", "white",
             "-alpha", "remove", "-trim", "-bordercolor", "white", "-border", "24", str(output)],
            check=True,
            capture_output=True,
        )


def _sql_shot(output: Path, theme: str) -> None:
    conn = sqlite3.connect(f"file:{RELEASE / 'sql' / 'wiktionary.sqlite'}?mode=ro", uri=True)
    query = (
        "SELECT f.row_header, f.column_header, f.form\n"
        "FROM inflection_forms f JOIN entries e USING (entry_id)\n"
        "WHERE e.title = 'heval' AND e.language_code = 'ku'\nLIMIT 9;"
    )
    rows = conn.execute(query).fetchall()
    head = ("row_header", "column_header", "form")
    widths = [max(len(str(r[i])) for r in [head, *rows]) for i in range(3)]
    lines = [" | ".join(str(c).ljust(widths[i]) for i, c in enumerate(r)) for r in [head, *rows]]
    lines.insert(1, "-+-".join("-" * w for w in widths))
    code = html.escape("sqlite> " + query.replace("\n", "\n   ...> ") + "\n\n" + "\n".join(lines))
    t = THEMES[theme]
    shot_html(
        f'<pre style="padding:36px;font:24px/1.5 monospace,Sahel">{code}</pre>',
        1100,
        660,
        output,
        theme,
        f"body{{background:{t['code'] if theme == 'dark' else t['surface']};color:{t['ink']}}}",
    )


def screenshots() -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    records = _record(RELEASE / "mdict" / "staging" / "dict.txt", {"heval", "av", "Tewandin:cûn"})
    for theme in THEMES:
        heval = _entry_page("heval", records["heval"], theme)
        chrome_shot(heval, SHOTS / f"entry-heval-{theme}.png", 1360, 1250, scale=2)
        chrome_shot(heval, SHOTS / f"entry-heval-phone-{theme}.png", 500, 1200, scale=2)
        chrome_shot(_entry_page("av", records["av"], theme), SHOTS / f"entry-av-{theme}.png", 1360, 1100, scale=2)
        chrome_shot(
            _entry_page("Tewandin-cun", records["Tewandin:cûn"], theme),
            SHOTS / f"entry-conjugation-{theme}.png",
            900,
            1200,
            scale=2,
        )
        _sql_shot(SHOTS / f"sql-inflections-{theme}.png", theme)
    _excel_excerpt(SHOTS / "excel-dictionary.png")


# ---- Ads, covers, social cards --------------------------------------------------------------


def _brand(size: int, theme: str) -> str:
    return (
        f'<div style="display:flex;align-items:center;gap:{size}px">{logo_plate(size * 5, theme)}'
        f'<span style="font-size:{int(size * 2.1)}px;font-weight:700;letter-spacing:-.02em">Kurdish Wiktionary</span></div>'
    )


def _tiles(items: list[tuple[str, str]], number: int, label: int) -> str:
    return "".join(
        f'<div><div class="num" style="font-size:{number}px;line-height:1">{value}</div>'
        f'<div class="small" style="font-size:{label}px;margin-top:8px;line-height:1.3">{name}</div></div>'
        for value, name in items
    )


def _word_card(theme: str) -> str:
    t = THEMES[theme]
    return f"""
<div style="background:{t['surface']};border:1px solid {t['line']};border-radius:24px;padding:44px">
  <div style="font-size:76px;font-weight:700;letter-spacing:-.02em;line-height:1.1">heval</div>
  <div style="font-size:26px;color:{t['accent']};font-weight:600;margin-top:10px">/hɛˈvɑːl/ · Navdêr · Noun</div>
  <div style="font-size:33px;line-height:1.45;margin-top:18px">Kesên hev dinasin û têkiliyên baş li gel hev hene û ji hev hez dikin.</div>
  <div class="small" style="font-size:26px;margin-top:18px;line-height:1.5">Hevmane: dost, birader, hevrê<br>Dijmane: dijmin, neyar<br><span dir="rtl" style="font-family:Sahel,Manrope;font-size:30px">هه‌ڤال</span> · Sound · Declension · Etymology · Translations</div>
</div>"""


def creatives() -> None:
    s = stats(report())
    tiles = [
        (s["entries"], "dictionary entries"),
        (s["senses"], "definitions"),
        (s["translations"], "translations"),
        (s["audio"], "recordings, many languages"),
    ]
    note = "Independent project. Text CC BY-SA 4.0 from Wîkîferheng contributors."
    formats_rows = (
        ("Parquet", "pandas, DuckDB, R"),
        ("SQL", "SQLite, PostgreSQL"),
        ("Excel", "one workbook per section"),
        ("JSONL", "nested, for NLP"),
        ("MDX / MDD", "GoldenDict, MDict"),
        ("Audio", f"{s['audio']} clips, many languages"),
    )
    accent = '<span class="accent">open data</span>'
    for theme, t in THEMES.items():
        shot_html(
            f"""<div style="height:100%;padding:60px 90px;display:flex;flex-direction:column;justify-content:space-between">
            {logo_plate(120, theme)}
            <div><div style="font-size:82px;font-weight:700;letter-spacing:-.03em;line-height:1.05">The Kurdish Wiktionary<br>as {accent}</div>
            <div class="small" style="font-size:30px;margin-top:20px">Every section as a table. SQL, Excel, Parquet, audio, and an offline dictionary.</div></div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:24px">{_tiles(tiles, 58, 22)}</div>
            <div class="small" style="font-size:18px">{note}</div></div>""",
            1200,
            800,
            EXPORT / f"kaggle-cover-{theme}.png",
            theme,
        )
        shot_html(
            f"""<div style="height:100%;padding:50px 70px;display:flex;flex-direction:column;justify-content:space-between">
            {logo_plate(104, theme)}
            <div style="font-size:70px;font-weight:700;letter-spacing:-.03em;line-height:1.08">The Kurdish Wiktionary<br>as {accent}</div>
            <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px">{_tiles(tiles, 48, 20)}</div></div>""",
            1200,
            630,
            EXPORT / f"social-card-{theme}.png",
            theme,
        )
        shot_html(
            f"""<div style="height:100%;padding:64px;display:flex;flex-direction:column;justify-content:space-between">
            <div style="font-size:68px;font-weight:700;letter-spacing:-.03em;line-height:1.08">Kurdish words,<br><span class="accent">ready to build with.</span></div>
            {_word_card(theme)}
            <div style="display:flex;justify-content:space-between;align-items:center">{_brand(22, theme)}<span class="small" style="font-size:26px">{s['entries']} entries</span></div></div>""",
            1080,
            1080,
            EXPORT / f"ad-square-{theme}.png",
            theme,
        )
        formats = "".join(
            f'<div style="display:flex;justify-content:space-between;border-top:2px solid {t["line"]};padding:24px 0;font-size:34px"><b>{a}</b><span class="small" style="font-size:28px">{b}</span></div>'
            for a, b in formats_rows
        )
        shot_html(
            f"""<div style="height:100%;padding:70px;display:flex;flex-direction:column;justify-content:space-between">
            {_brand(24, theme)}
            <div style="font-size:84px;font-weight:700;letter-spacing:-.03em;line-height:1.05">One lexicon.<br><span class="accent">Every format.</span></div>
            <div>{formats}</div>
            <div class="small" style="font-size:24px">{note}</div></div>""",
            1080,
            1350,
            EXPORT / f"ad-portrait-{theme}.png",
            theme,
        )
        shot = (SHOTS / f"entry-heval-phone-{theme}.png").resolve().as_uri()
        shot_html(
            f"""<div style="height:100%;padding:110px 70px;display:flex;flex-direction:column;gap:44px">
            {_brand(26, theme)}
            <div style="font-size:82px;font-weight:700;letter-spacing:-.03em;line-height:1.06">{s['kurmanci']} Kurmancî entries, <span class="accent">offline.</span></div>
            <div style="flex:1;border-radius:28px;border:1px solid {t['line']};overflow:hidden;background:url('{shot}') top center/100% auto no-repeat"></div>
            <div class="small" style="font-size:30px">Offline dictionary for GoldenDict and MDict</div></div>""",
            1080,
            1920,
            EXPORT / f"ad-story-{theme}.png",
            theme,
        )
        shot_html(
            f"""<div style="height:100%;padding:0 22px;display:flex;align-items:center;justify-content:space-between;gap:16px">
            <span style="display:flex;align-self:center">{logo_plate(68, theme)}</span><span style="font-size:24px;font-weight:700;letter-spacing:-.01em">The Kurdish Wiktionary as {accent}</span>
            <span style="flex:none;background:{t['accent']};color:{t['on_accent']};font-weight:700;font-size:17px;padding:10px 16px;border-radius:8px">Get the data</span></div>""",
            728,
            90,
            EXPORT / f"ad-leaderboard-{theme}.png",
            theme,
        )


# ---- Landing page ---------------------------------------------------------------------------


def _language_bars(data: dict) -> str:
    top = [item for item in data["top_languages"] if item["name"]][:10]
    peak = top[0]["entries"]
    return "".join(
        f'<tr title="{html.escape(item["name"])}: {item["entries"]:,} entries, {(item["senses"] or 0):,} definitions">'
        f'<th scope="row">{html.escape(item["name"])}</th>'
        f'<td class="bar-cell"><span class="bar" style="width:{max(item["entries"] / peak * 100, 1):.1f}%"></span></td>'
        f'<td class="value">{item["entries"]:,}</td></tr>'
        for item in top
    )


def site() -> None:
    data = report()
    s = stats(data)
    rows = data["row_counts"]
    every = data["coverage"]["all"]
    template = (SRC / "landing.html").read_text(encoding="utf-8")
    values = {
        **{f"stat_{key}": value for key, value in s.items()},
        "entries_exact": f"{rows['entries']:,}",
        "pages_exact": f"{rows['pages']:,}",
        "senses_exact": f"{rows['senses']:,}",
        "auto_pct": str(every["auto_generated_pct"]),
        "language_bars": _language_bars(data),
        "zim_date": data["build"].get("zim_date", "2026-08-25"),
        "kurmanci_headwords": rounded(data["coverage"]["kurmanci"]["headword_entries"]),
        "audio_kurmanci": rounded(
            next((i["recordings"] for i in data["audio_by_language"] if i["code"] == "ku"), 0)
        ),
        "kaggle_url": KAGGLE_URL,
    }
    page = template
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", value)
    if "{{" in page:
        raise SystemExit(f"Unfilled placeholder near: {page[page.index('{{'):][:40]}")
    assets = SITE / "assets"
    if assets.exists():
        shutil.rmtree(assets)
    assets.mkdir(parents=True)
    (SITE / "index.html").write_text(page, encoding="utf-8")
    sources = [EXPORT / "wiktionary-logo-ku.svg", EXPORT / "logo-192.png", SHOTS / "excel-dictionary.png"]
    for theme in THEMES:
        sources += [
            EXPORT / f"social-card-{theme}.png",
            SHOTS / f"entry-heval-{theme}.png",
            SHOTS / f"entry-heval-phone-{theme}.png",
            SHOTS / f"sql-inflections-{theme}.png",
        ]
    for source in sources:
        shutil.copy2(source, assets / source.name)
    # Manrope comes from Google Fonts on the page; Sahel is not there, so it ships with the site.
    fonts = assets / "fonts"
    fonts.mkdir(exist_ok=True)
    for path in (FONTS / "sahel").glob("*.woff2"):
        shutil.copy2(path, fonts / path.name)
    (SITE / ".nojekyll").write_text("", encoding="utf-8")


STAGES = {"logos": logos, "screenshots": screenshots, "creatives": creatives, "site": site}


def main() -> None:
    wanted = sys.argv[1:] or list(STAGES)
    for name in wanted:
        STAGES[name]()
        print(f"{name}: done")


if __name__ == "__main__":
    main()
