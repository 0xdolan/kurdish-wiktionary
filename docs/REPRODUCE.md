# Rebuild the Kurdish Wiktionary dataset yourself

This repository holds the code and guides, not the data. ZIM files, the SQLite database, Excel, CSV, Parquet, `dict.txt`, MDX, MDD and media are too large for Git, so you generate them on your own machine. With the same ZIM files you get the same tables, and one command proves it.

## What you need

| | |
|---|---|
| System | Linux or macOS. Windows through WSL |
| Tools | `git`, `curl`, `sha256sum` (on macOS, install coreutils) and [uv](https://docs.astral.sh/uv/getting-started/installation/) |
| Disk | About 30 GB free, including the 1 GB of ZIM files |
| Memory | 8 GB is enough |
| Network | About 1 GB for the ZIMs, about 2 GB for the audio |
| Optional | Google Chrome, LibreOffice and ImageMagick, only to regenerate the images and landing page |

No database server, Docker or paid service is needed.

## The short version

```bash
git clone https://github.com/0xdolan/wiktionary_to_mdx.git
cd wiktionary_to_mdx
uv sync
./scripts/fetch-zims.sh
./scripts/build-release.sh --skip-download   # Everything except the audio: under an hour
uv run python -m src.dataset verify          # Proves your tables match the published ones
```

To include the recordings, run `./scripts/finish-release.sh` next. It downloads them and rebuilds every output, and it can take more than a day, because Wikimedia limits download speed.

Results land in `build/release/`.

## Step by step

### 1. Get the code

```bash
git clone https://github.com/0xdolan/wiktionary_to_mdx.git
cd wiktionary_to_mdx
uv sync
```

`uv sync` installs the exact package versions from `uv.lock`, which matters for matching results.

### 2. Get the ZIM files

```bash
./scripts/fetch-zims.sh
```

This puts these two files in `zim/wiktionary/` and checks their hashes:

| File | Size | Date | SHA-256 |
|---|---:|---|---|
| `wiktionary_ku_all_maxi_2026-08.zim` | 572 MB | 2026-08-25 | `8534326d9d89e59274d946458460cef4106dee8bd80d532dd1e4bc0e9710f03a` |
| `wiktionary_ku_all_nopic_2026-06.zim` | 486 MB | 2026-06-23 | `26f820ae99bc560d1b873bcf7bab295ca8d3865798eb41f0819460e8a8b5eb13` |

You can also download them by hand from [download.kiwix.org/zim/wiktionary](https://download.kiwix.org/zim/wiktionary/). The maxi file is the main source and holds the images. The nopic file only adds pages that were later removed from the wiki.

### 3. Build the tables

```bash
uv run python -m src.dataset parse           # ~6 min. Creates sql/wiktionary.sqlite
uv run python -m src.dataset media-extract   # ~1 min. Copies all images out of the ZIM
uv run python -m src.dataset verify          # ~3 min. Compares your tables with the release
```

`verify` checks the ZIM hashes, the row count of every table and a hash of every table's contents. A match prints `MATCH`. Anything else lists what differs.

### 4. Download the recordings (optional, slow)

The ZIM files contain no audio, so all 94,032 recordings come from Wikimedia.

```bash
export MEDIA_USER_AGENT="YourProject/1.0 (you@example.org)"   # Wikimedia asks bots to identify themselves
uv run python -m src.dataset media-download
uv run python -m src.dataset media-licences
uv run python -m src.dataset media-audit
```

Stop and rerun the download at any time. It continues where it stopped, at about 0.6 files per second. Please don't speed it up: Wikimedia's [robot policy](https://wikitech.wikimedia.org/wiki/Robot_policy) sets the limits, and it answers faster requests with errors.

Your audio count may differ slightly from the release, because files get deleted from Wikimedia over time. Check `quality/media_missing.jsonl`.

Without this step everything else still works, but dictionary entries link to the recordings online instead of playing them offline.

### 5. Export every format

```bash
uv run python -m src.dataset export    # ~12 min. SQL, Parquet, CSV, JSONL, Excel
uv run python -m src.dataset mdict     # ~4 min. dict.txt, MDX, MDD
uv run python -m src.dataset quality   # Seconds. Quality report
```

### 6. Package (optional)

```bash
uv run python scripts/build_brand.py   # Regenerates images with your numbers. Needs Chrome and LibreOffice
uv run python -m src.dataset bundle    # ~2 min. Folder for sharing, with checksums
```

## What you get

Everything is under `build/release/`.

| Path | Contents | Approx. size |
|---|---|---:|
| `sql/wiktionary.sqlite` | The whole dataset as one database | 3.3 GB |
| `sql/wiktionary_schema.sql` | Table definitions for PostgreSQL or SQLite | 6 KB |
| `sql/wiktionary_data.sql.gz` | Data as SQL | 210 MB |
| `sql/wiktionary_section_html.sql.gz` | Section HTML as SQL | 135 MB |
| `parquet/` | Every table | 400 MB |
| `csv/` | Every table except section HTML | 1.3 GB |
| `excel/` | One workbook per table, plus Kurmancî and Soranî dictionaries | 510 MB |
| `jsonl/entries.jsonl.gz` | One nested object per entry | 75 MB |
| `mdict/staging/dict.txt` | Dictionary source: headword, HTML, `</>` | 2.3 GB |
| `mdict/staging/resources/` | CSS, scripts, fonts and images for the dictionary | 65 MB |
| `mdict/wiktionary.mdx` | The dictionary | ~200 MB |
| `mdict/wiktionary.mdd` | Styles, fonts and images | 57 MB |
| `mdict/wiktionary.1.mdd` | Audio | ~2 GB with all recordings |
| `media/images/`, `media/audio/` | Every media file | 65 MB, ~2 GB |
| `quality/` | `QUALITY.md`, `report.json`, `media_audit.json`, `media_missing.jsonl` | Small |

Put `wiktionary.mdx`, `wiktionary.mdd` and `wiktionary.1.mdd` in one folder and open the `.mdx` in GoldenDict or MDict.

## The numbers you should get

From `verify`, with the two ZIM files above:

| Table | Rows |
|---|---:|
| `pages` | 1,038,509 |
| `redirects` | 2,918 |
| `entries` | 1,109,037 |
| `sections` | 3,024,919 |
| `section_html` | 1,919,559 |
| `headwords` | 1,079,876 |
| `senses` | 1,220,879 |
| `examples` | 21,010 |
| `quotations` | 14,454 |
| `pronunciations` | 309,237 |
| `etymologies` | 102,091 |
| `translations` | 799,382 |
| `relations` | 298,147 |
| `inflection_tables` | 277,209 |
| `inflection_forms` | 1,692,571 |
| `reference_notes` | 241,525 |
| `media` | 98,622 |
| `media_usages` | 374,613 |

## If `verify` reports differences

| Message | Meaning | What to do |
|---|---|---|
| `ZIM not found` or `ZIM differs` | Different source files | Run `./scripts/fetch-zims.sh`. A newer dump gives different numbers by design |
| `rows, expected` or `contents differ` | Different package versions, or changed code | Run `uv sync`, and check `git status` for local changes |

If you changed the parser on purpose, that's expected: run `uv run python -m src.dataset verify --write-expected` to record your own baseline.

## If the exact ZIMs are gone

Kiwix replaces old dumps with newer ones, so these files may disappear. You then have two options:

1. **Find a copy.** Search for the file name or the hash above; anyone holding the file can share it, and the hash proves it's the same one.
2. **Use a newer dump.** Download the current `wiktionary_ku_all_maxi_*.zim` and `wiktionary_ku_all_nopic_*.zim`, and pass them in:

   ```bash
   uv run python -m src.dataset --maxi zim/wiktionary/NEW_MAXI.zim --nopic zim/wiktionary/NEW_NOPIC.zim parse
   ```

   Pass the same `--maxi` and `--nopic` to `media-extract`, `mdict` and `bundle`. The numbers will be newer, so `verify` will report differences. That's expected, and it's how to make an updated release.

## Fonts

Sahel sets right-to-left text and Manrope left-to-right text. Both are bundled for the dictionary. Excel can't embed fonts, so install them to see the workbooks as designed: [Manrope](https://fonts.google.com/specimen/Manrope) and [Sahel](https://github.com/rastikerdar/sahel-font).

## Rebuilding the logo

The vector logo is already in the repository, so you don't need this. To regenerate it, install Linux Libertine, Arial and Sahel, set the font paths at the top of `scripts/build_logo.py`, and run:

```bash
uv run --with uharfbuzz --with fonttools --with pillow --with numpy \
  python scripts/build_logo.py assets/brand/src/wiktionary-logo-ku.png assets/brand/src/wiktionary-logo-ku.svg
```

## Common problems

| Problem | Fix |
|---|---|
| `uv: command not found` | Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and open a new terminal |
| `parse` stops with a file-not-found error | Run `./scripts/fetch-zims.sh` from the repository folder |
| Many `HTTP 429` errors while downloading | Wikimedia is throttling. Stop for a while, set `MEDIA_USER_AGENT` with your contact details, and rerun |
| `bundle` says the database is in WAL mode | A download is still running, or was killed. Let it finish, or run `media-audit`, then retry |
| Out of disk space | Delete `csv/` or `excel/` if you don't need them, or skip them with `export --only parquet --only sql` |

More detail on using the data: [DATASET_LOCAL_GUIDE.md](DATASET_LOCAL_GUIDE.md). Every column: [DATASET_SCHEMA.md](DATASET_SCHEMA.md).
