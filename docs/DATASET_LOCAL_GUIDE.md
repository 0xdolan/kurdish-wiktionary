# Kurdish Wiktionary dataset: local guide

Use the dataset on your own machine. To build it from scratch, follow [REPRODUCE.md](REPRODUCE.md) first. For publishing, see [DATASET_KAGGLE_GUIDE.md](DATASET_KAGGLE_GUIDE.md). Every column is documented in [DATASET_SCHEMA.md](DATASET_SCHEMA.md).

## What you need

- The ZIM files in `zim/wiktionary/`: `wiktionary_ku_all_maxi_2026-08.zim` and `wiktionary_ku_all_nopic_2026-06.zim`. Other dumps work with `--maxi` and `--nopic`.
- [uv](https://docs.astral.sh/uv/), then `uv sync`
- About 30 GB of free disk for the full build
- No database server. This pipeline reads ZIM files and writes SQLite; PostgreSQL is optional

## Build everything

```bash
./scripts/build-release.sh                  # includes the long media download
./scripts/build-release.sh --skip-download  # uses the media you already have
```

Output goes to `build/release/`, which git ignores. Every stage can be rerun. Times below were measured on an 8-core machine with an SSD.

| Stage | Command (`uv run python -m src.dataset ...`) | Time | Output |
|---|---|---|---|
| 1. Parse | `parse` | ~6 min | `sql/wiktionary.sqlite` |
| 2. ZIM media | `media-extract` | ~1 min | `media/images/`, plus reuse of old downloads |
| 3. Download | `media-download` | 1 to 2 days from nothing | `media/audio/` |
| 4. Licences | `media-licences` | ~30 min | Licence columns in `media` |
| 5. Check media | `media-audit` | Seconds | `quality/media_audit.json`, `quality/media_missing.jsonl` |
| 6. Export | `export` | ~12 min | `sql/`, `parquet/`, `csv/`, `jsonl/`, `excel/` |
| 7. Dictionary | `mdict` | ~4 min | `mdict/wiktionary.mdx`, `.mdd`, `.1.mdd`, `mdict/staging/dict.txt` |
| 8. Package | `bundle` | ~2 min | `kaggle/` |

If a download was interrupted, or you want to finish a release without re-parsing, run `./scripts/finish-release.sh`. It resumes the download and rebuilds every output.

Choose formats with `export --only excel --only csv`. Stop the dictionary stage before packing with `mdict --txt-only`. Rerunning `parse` rebuilds the database. Licence data carries over. Run `media-extract` straight after it to reconnect the files already downloaded.

## Media

**The ZIM files do not contain the audio.** The maxi ZIM holds the images, as WebP thumbnails even where the name says `.jpg`. Every recording lives on Wikimedia, so the pipeline downloads them.

```bash
uv run python -m src.dataset media-extract   # Everything in the ZIMs
uv run python -m src.dataset media-audit     # What is still missing?
uv run python -m src.dataset media-download  # Fetch the gaps; stop and resume freely
uv run python -m src.dataset media-licences  # Licence and author per file
uv run python -m src.dataset media-audit     # Confirm
```

What the audit compares: every media reference in every page, the `media` table, and the files on disk. Anything absent is listed in `quality/media_missing.jsonl` with the reason.

How downloading behaves:

- It follows the [Wikimedia robot policy](https://wikitech.wikimedia.org/wiki/Robot_policy): at most 2 connections and 25 Mbps, and it honours `Retry-After`. It paces itself at 1 request per second, because Wikimedia answers faster bursts with HTTP 429. The full audio set takes more than a day: the measured average is about 0.6 files per second.
- If a converted MP3 no longer exists (HTTP 404), it tries the original recording. If that is gone too, it asks Commons whether the file was renamed and fetches it under the new name.
- It checks that each response really is media before saving.
- Set a User-Agent with your own contact details: `export MEDIA_USER_AGENT="MyProject/1.0 (you@example.org)"`.

Files are stored as `audio/ab/abcdef0123456789.mp3`. These ASCII names work on every filesystem and in every dictionary app, and each file is stored once however many pages use it. To find a file for a word:

```sql
SELECT m.local_path, m.commons_file, m.license, m.artist
FROM pronunciations p
JOIN entries e USING (entry_id)
JOIN media m USING (media_id)
WHERE e.title = 'heval' AND p.kind = 'audio';
```

## Use the data

### SQLite

```bash
uv run python - <<'PY'
import sqlite3
conn = sqlite3.connect("build/release/sql/wiktionary.sqlite")
for row in conn.execute("""
    SELECT s.pos, s.ordinal, s.definition
    FROM senses s JOIN entries e USING (entry_id)
    WHERE e.title = 'heval' AND e.language_code = 'ku'
"""):
    print(row)
PY
```

Useful queries:

```sql
-- Kurmancî synonyms of a word
SELECT r.term FROM relations r JOIN entries e USING (entry_id)
WHERE e.title = 'heval' AND e.language_code = 'ku' AND r.relation_type = 'synonyms';

-- A Kurmancî to English glossary from the translation tables
SELECT e.title, t.term FROM translations t JOIN entries e USING (entry_id)
WHERE e.language_code = 'ku' AND t.target_code = 'en';

-- All declined forms of a noun
SELECT f.group_header, f.row_header, f.column_header, f.form
FROM inflection_forms f JOIN entries e USING (entry_id)
WHERE e.title = 'heval' AND e.language_code = 'ku';

-- Literary citations before 1800
SELECT e.title, q.year, q.author, q.work, q.passage
FROM quotations q JOIN entries e USING (entry_id)
WHERE CAST(q.year AS INTEGER) < 1800 ORDER BY CAST(q.year AS INTEGER);

-- Leave out entries the wiki marks as bot-made, and those with no definition yet
SELECT COUNT(*) FROM entries WHERE is_auto_generated = 0 AND definition_pending = 0;
```

### PostgreSQL

```bash
createdb wiktionary
./scripts/load-postgres.sh postgresql://localhost/wiktionary              # Without section HTML
./scripts/load-postgres.sh postgresql://localhost/wiktionary build/release/sql --with-html
```

Run one of the two, on an empty database. The same `wiktionary_schema.sql` and data files also load into SQLite. MySQL is not supported as is, because the schema uses `TEXT` primary keys.

### Excel and LibreOffice

Open `excel/00_START_HERE_overview.xlsx`: it lists every table, column, section type, part of speech and language. To read the dictionary rather than study the data, use `excel/dictionary_kurmanci.xlsx` or `excel/dictionary_sorani.xlsx`, which have one row per definition.

Each workbook has an `about` sheet describing its columns. A sheet holds at most 1,000,000 rows here, so large tables continue on the next sheet and in `.part02.xlsx` files. These files are large, and opening the biggest can take minutes. For filtering millions of rows, the Parquet or SQLite files are a better tool.

### Parquet, CSV and JSONL

```python
import pandas as pd
entries = pd.read_parquet("build/release/parquet/entries.parquet")
kurmanci = entries[(entries.language_code == "ku") & (entries.sense_count > 0)]
```

CSV files start with a UTF-8 byte order mark so Excel shows Kurdish letters correctly. Pass `encoding="utf-8-sig"` when reading them with other tools. `jsonl/entries.jsonl.gz` holds one nested object per entry.

## Build the dictionary (MDX and MDD)

```bash
uv run python -m src.dataset mdict
```

| File | Contents |
|---|---|
| `mdict/staging/dict.txt` | The source text: UTF-8 records of headword, HTML and `</>` |
| `mdict/staging/resources/` | `css/`, `js/`, `fonts/`, `img/`, `images/` |
| `mdict/staging/resources_audio/` | `audio/` |
| `mdict/wiktionary.mdx` | The dictionary |
| `mdict/wiktionary.mdd` | CSS, scripts, fonts and images |
| `mdict/wiktionary.1.mdd` | Audio. Dictionary apps load `.1.mdd` automatically |

Keep all three files in one folder and add the `.mdx` to GoldenDict, MDict or a similar app.

A record looks like this:

```text
heval
<link rel="stylesheet" type="text/css" href="css/dictionary.css" /><article class="wk">...</article><script type="text/javascript" src="js/dictionary.js"></script>
</>
```

Redirects and other-script spellings are alias records, so searching `هه‌ڤال` opens `heval`:

```text
هه‌ڤال
@@@LINK=heval
</>
```

To make your own edition, edit `assets/mdict/css/dictionary.css`, `assets/mdict/js/dictionary.js` or `src/dataset/entry_html.py`, or `dict.txt` directly, then rerun `mdict`, or pack by hand:

```bash
uv run python -m mdict_utils --title title.html --description description.html \
  -a build/release/mdict/staging/dict.txt my.mdx
uv run python -m mdict_utils -m my.mdx          # Read the metadata back
uv run python -m mdict_utils -q heval my.mdx    # Look up a word
```

The first line of the CSS file must stay blank (an MDict quirk). The format is described in [MDX_ENTRY_FORMAT.md](MDX_ENTRY_FORMAT.md).

## Fonts

Right-to-left text uses **Sahel**, which covers Soranî letters such as ڕ ڵ ێ ۆ ە. Left-to-right text uses **Manrope**.

| Where | How |
|---|---|
| Dictionary (`.mdx`, `.mdd`) | Both fonts are bundled, so they work offline. Sahel has no Latin letters, so each script picks its font automatically |
| Landing page | Manrope from Google Fonts, Sahel from `site/assets/fonts/` |
| Ads and screenshots | Rendered with both fonts, in light and dark |
| Excel | Cells name Manrope, and right-to-left cells name Sahel. Excel can't embed fonts: install [Manrope](https://fonts.google.com/specimen/Manrope) and [Sahel](https://github.com/rastikerdar/sahel-font), or Excel substitutes others |

Hebrew, Syriac and other right-to-left scripts aren't in Sahel, so they use a system font. CSV, Markdown and notebooks don't carry fonts, so your viewer decides.

## Check the build

```bash
uv run python -m src.dataset quality   # Writes quality/QUALITY.md and report.json
uv run pytest tests/unit/test_dataset_parser.py tests/unit/test_dataset_outputs.py
```

## Update to a new dump

1. Download new ZIMs from [Kiwix](https://download.kiwix.org/zim/wiktionary/).
2. Pass them with `--maxi` and `--nopic`, or update the defaults in `src/dataset/__main__.py`.
3. Run `./scripts/build-release.sh`. Earlier downloads are reused when their URLs have not changed.
4. Check `quality/QUALITY.md`: a sudden jump in `unclassified_section_count` means the wiki's markup changed.
5. Raise `DATASET_VERSION` in `src/dataset/bundle.py` and update `assets/dataset/CHANGELOG.md`.

If the wiki gains a new heading variant, add it to `src/dataset/sections.py`.

## Troubleshooting

| Problem | Fix |
|---|---|
| Many `HTTP 429` errors | Wikimedia is throttling. Stop for a while, set a `MEDIA_USER_AGENT` with contact details, and rerun |
| `failed` media rows | See `error` in the `media` table. Most are files deleted from Commons. Rerunning retries them |
| Kurdish letters garbled in a CSV | Read as UTF-8 with BOM; in Excel, open the file rather than importing as ANSI |
| `bundle` says the database is still in WAL mode | Wait for `media-download` and `media-licences` to finish, or stop them. Kaggle can't open a WAL database |
| Excel is slow or runs out of memory | Use the `dictionary_*` workbooks, Parquet or SQLite |
| Audio does not play in a dictionary app | Keep `.mdx`, `.mdd` and `.1.mdd` together with the same base name |
| No contents list or theme button in a dictionary app | That app has JavaScript off. The article still works, and audio plays through `sound://` |
