# Lexicon API and CLI

Structured access to **full entries**, **per-field slices**, **raw HTML**, **section HTML**, and **media URLs** — with a **preview-then-confirm** workflow so you can verify synonyms/antonyms from ZIM before writing to PostgreSQL.

## Why synonyms/antonyms were empty

Older extracts used a parser that never filled `synonyms` / `antonyms`. Re-parse with preview/extract or re-run canonical extract after upgrading. Stored HTML lives in `entry_html`; media URL rows in `entry_media` (unique on `entry_id` + `url`).

## Operator setup

```bash
docker compose up -d --build postgres api   # runs Alembic through 20261010_0005
```

## Workflow (recommended)

1. **Check one field from ZIM (no DB write)**  
   `GET /lexicon/entries/{word}/zim/fields/synonyms`

2. **Full parse preview**  
   `POST /lexicon/entries/{word}/preview` → inspect `counts`, `warnings`, `media`

3. **Persist**  
   `POST /lexicon/entries/{word}/extract?confirm=true`

4. **Read from SQL**  
   `GET /lexicon/entries/{word}` or `GET /lexicon/entries/{word}/fields/synonyms`

5. **Download binaries (optional)**  
   `POST /lexicon/entries/{word}/media/download?confirm=false` (preview)  
   `POST /lexicon/entries/{word}/media/download?confirm=true` (writes under `MEDIA_EXPORT_DIR`, default `build/media/`)

Folder layout per asset:

```text
build/media/{entry_normalized}/{kind}/{filename-stem}-{url-hash10}.{ext}
```

Remote Wikimedia URLs are fetched over HTTPS; ZIM-local paths are resolved via `libzim` (`I/…`, `C/…`, etc.).

## HTTP reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/lexicon/entries` | Paginated full entries from SQL |
| GET | `/lexicon/entries/{word}` | One entry |
| GET | `/lexicon/entries/{word}/fields/{field}` | One field from SQL |
| GET | `/lexicon/fields/{field}` | Field values across corpus (paginated) |
| GET | `/lexicon/entries/{word}/html` | Stored full HTML |
| GET | `/lexicon/entries/{word}/html/sections/{section}` | Stored section fragment (e.g. `beranber`) |
| GET | `/lexicon/html?include_html=true` | All stored HTML (paginated; set `include_html` for bodies) |
| GET | `/lexicon/html/sections/{section}` | Section HTML for all entries that have it |
| GET | `/lexicon/entries/{word}/media` | Media URLs for one entry |
| GET | `/lexicon/media?kind=audio` | Media URLs corpus-wide |
| GET | `/lexicon/entries/{word}/zim/html` | Raw HTML from ZIM |
| GET | `/lexicon/entries/{word}/zim/html/sections/{section}` | Section HTML from live ZIM parse |
| GET | `/lexicon/entries/{word}/zim/fields/{field}` | One field from live ZIM parse |
| POST | `/lexicon/entries/{word}/preview` | Full ZIM parse, no write |
| POST | `/lexicon/entries/{word}/extract?confirm=true` | Upsert entry + HTML + media |
| POST | `/lexicon/entries/{word}/media/download?confirm=true` | Download files + update `local_path` |
| GET | `/lexicon/diagnostics/sparse?mode=missing_relations` | Defs present but syn/ant empty |
| GET | `/lexicon/diagnostics/duplicates` | Duplicate child rows per entry |
| GET | `/lexicon/export?format=json\|txt` | Export slice |

`field` ∈ `definitions`, `synonyms`, `antonyms`, `examples`, `pronunciations`, `phonetic_transcriptions`, `derived_terms`, `part_of_speech`.

## Example curls

```bash
# 1) Can we get synonyms from ZIM?
curl -s 'http://127.0.0.1:8000/lexicon/entries/heval/zim/fields/synonyms' | jq .

# 2) Preview
curl -s -X POST 'http://127.0.0.1:8000/lexicon/entries/heval/preview' | jq .

# 3) Extract
curl -s -X POST 'http://127.0.0.1:8000/lexicon/entries/heval/extract?confirm=true' | jq .

# 4) Raw HTML (stored)
curl -s 'http://127.0.0.1:8000/lexicon/entries/heval/html' | jq -r .html | head

# 5) All synonym section HTML in DB (paginated)
curl -s 'http://127.0.0.1:8000/lexicon/html/sections/beranber?limit=5' | jq .

# 6) Stale rows (re-extract candidates)
curl -s 'http://127.0.0.1:8000/lexicon/diagnostics/sparse?mode=missing_relations&limit=20' | jq .
```

## CLI (mirrors API)

```bash
uv run python -m src.lexicon preview heval
uv run python -m src.lexicon zim-field heval synonyms
uv run python -m src.lexicon extract heval --confirm
uv run python -m src.lexicon get heval --field synonyms
uv run python -m src.lexicon zim-html heval
uv run python -m src.lexicon zim-html heval --section beranber
uv run python -m src.lexicon media-download heval --confirm

# Bulk: all extracted entries with media URL rows
uv run python -m src.lexicon media-download-all                    # preview counts
uv run python -m src.lexicon media-download-all --confirm --all    # one command until done
./scripts/media-download-all.sh                                    # same (batch size: MEDIA_DOWNLOAD_BATCH_SIZE)
uv run python -m src.lexicon media-download-all --confirm --limit 500  # single batch only
uv run python -m src.lexicon media-download-all --confirm --all --force  # re-fetch everything
```

With `--confirm`, each run writes a failure JSONL under `build/media/state/runs/media-download-<timestamp>/failures.jsonl` (override with `MEDIA_DOWNLOAD_STATE_DIR`; Wikimedia 429/5xx are retried with backoff). Existing files are reused when on-disk size matches the ZIM payload or remote `Content-Length`.

```bash
uv run python -m src.lexicon sparse --mode missing_relations --limit 50
```

## Deduplication

- Upsert key: `(entry_normalized, language_code)` on `entries`.
- Child lists: delete-and-reinsert with **in-list dedupe** on each extract.
- Media: unique `(entry_id, url)`; replace-all on extract per entry.
- Audit: `GET /lexicon/diagnostics/duplicates`.

## Tests

```bash
uv run pytest tests/test_lexicon_api.py tests/unit/test_html_parser.py -q
uv run pytest tests/unit/test_zim_media.py -q   # path resolution helpers
```
