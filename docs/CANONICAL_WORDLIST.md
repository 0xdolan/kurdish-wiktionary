# Canonical wordlist workflow (dual ZIM → UTF-8 plain text)

## Rephrased goal

Build **one deduplicated lemma list** from every configured Kiwix ZIM, then for **each lemma** load HTML from **each archive that contains it**, parse to **decoded UTF-8 plain text** (no HTML entities), merge fields, and store in PostgreSQL. Report **ZIM-side and SQL-side statistics**, and **audit** that extracted rows have linked entries and clean text.

## Operator steps (Docker)

```bash
# 1. Stack + migrations (API/catalog entrypoints run alembic)
docker compose up -d postgres api

# 2. Build canonical wordlist from nopic + maxi (see ZIM_PATHS in compose)
docker compose --profile catalog run --rm --build catalog sync-canonical

# 3. Statistics: per-ZIM title counts + canonical_lemmas + legacy wordlist totals
docker compose --profile catalog run --rm --build catalog stats

# 4. Extract batch: HTML from each ZIM → merge → entries (UTF-8 plain text)
docker compose --profile catalog run --rm catalog extract-canonical --limit 5000

# 5. Audit: extracted vs entry_id, HTML entity spot-check on definitions
docker compose --profile catalog run --rm catalog audit

# 6. HTTP read (after API rebuild)
curl -s http://127.0.0.1:8000/catalog/canonical/stats | jq .
curl -s http://127.0.0.1:8000/words/heval | jq .
```

## Environment

| Variable | Purpose |
|----------|---------|
| `ZIM_PATH` | Primary archive (API default, legacy per-ZIM wordlist) |
| `ZIM_PATHS` | Comma-separated list for **sync-canonical** / **extract-canonical** |

## Tables

| Table | Role |
|-------|------|
| `canonical_lemmas` | **One row per normalized title**; `zim_sources` JSON maps each ZIM UUID → title/path |
| `wordlist_titles` | Legacy per-(lemma, zim_uuid) index (optional) |
| `entries` + child rows | Parsed plain-text lexical data |

## Text encoding

- ZIM HTML is read as **UTF-8**.
- Parser runs **`html.unescape`** + Unicode **NFC** on all extracted strings so stored JSON/SQL is not HTML-entity encoded.

## Verification checklist

- [ ] `stats`: ZIM title counts match expectations (~1M each for ku nopic/maxi)
- [ ] `stats`: `canonical_lemmas` total ≈ union of lemmas (not double per ZIM)
- [ ] `audit`: `extracted_missing_entry_id` = 0
- [ ] `audit`: `entries_with_html_entities` → 0 after full re-extract with new parser
- [ ] Sample `GET /words/{lemma}`: definitions readable, no `&nbsp;` / `&#...;`
