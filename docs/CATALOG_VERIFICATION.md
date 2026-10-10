# Catalog extract verification (skipped / failed)

After `extract-canonical --all`, some lemmas are **`skipped`** (usually no definitions/phonetics in ZIM) or **`failed`** (I/O, parse, missing article). Every row stores the reason in PostgreSQL **`last_error`**.

## Where data lives

| Layer | Location |
|--------|-----------|
| SQL | `canonical_lemmas.extract_status`, `canonical_lemmas.last_error`, `entry_id` |
| Run logs | `build/catalog/state/runs/<command>-<fp>-<timestamp>/` |
| Per batch | `batches/batch-NNNNN.jsonl` — one JSON object per skipped/failed lemma |
| Summary | `outcome-report.json` + `run-manifest.json` in the same run folder |
| Checkpoint | `build/catalog/state/checkpoints/` (resume only) |

## Docker: `Permission denied: 'build'`

If `sync-canonical` / `extract-canonical` fails creating `build/catalog/state`, prepare the bind mount (catalog UID **10001**):

```bash
mkdir -p build/catalog/state build/catalog/reports
sudo chown -R 10001:10001 build/catalog
```

Then rebuild: `docker compose --profile catalog run --rm --build catalog stats`.

## CLI commands

```bash
# Counts + category breakdown + sample titles
docker compose --profile catalog run --rm catalog stats
docker compose --profile catalog run --rm catalog audit

# Detailed skipped/failed report (Rich table + optional export)
docker compose --profile catalog run --rm catalog report --scope canonical
docker compose --profile catalog run --rm catalog report --status failed --limit 500 \
  --export build/catalog/reports/failed-canonical.json

# Retry only failed rows (skipped are usually intentional)
docker compose --profile catalog run --rm catalog \
  extract-canonical --retry-failed --resume --all --limit 10000
```

## HTTP

```bash
curl -s 'http://127.0.0.1:8000/catalog/canonical/stats' | jq .
curl -s 'http://127.0.0.1:8000/catalog/audit' | jq .
curl -s 'http://127.0.0.1:8000/catalog/outcomes?scope=canonical&status=failed&limit=100' | jq .
```

## DBeaver checks

```sql
-- Counts by status
SELECT extract_status, COUNT(*) FROM canonical_lemmas GROUP BY 1;

-- Top skip/fail reasons
SELECT extract_status, last_error, COUNT(*)
FROM canonical_lemmas
WHERE extract_status IN ('skipped', 'failed')
GROUP BY 1, 2
ORDER BY COUNT(*) DESC
LIMIT 30;

-- Inspect one lemma
SELECT title, extract_status, last_error, entry_id, extracted_at
FROM canonical_lemmas
WHERE extract_status = 'failed'
LIMIT 20;
```

## Outcome categories

| Category | Typical meaning |
|----------|-----------------|
| `no_definitions_or_phonetics` | Empty or non-lexicon page → **skipped** |
| `article_not_found_in_zim` | Title missing in configured ZIM |
| `no_zim_source_matched` | `zim_sources` out of sync with `ZIM_PATHS` |
| `parse_error` | HTML parse exception |
| `other` | See raw `last_error` |

## Acceptance checklist

1. `stats`: `pending = 0` after full `--all` run (or expected remainder documented).
2. `audit`: `extracted_missing_entry_id = 0`; note HTML entity sample if non-zero.
3. `report`: failed count matches `canonical_lemmas` `failed` aggregate; export JSON archived.
4. Run manifest path printed at end of extract; batch JSONL present for batches with skips/fails.
5. Retry failed; failed count drops or errors change with a fix.

Rebuild the catalog image after code changes: `docker compose --profile catalog run --rm --build catalog …`

---

## After a full `extract-canonical --all` run

Your run finished with **`pending_left=0`**: every lemma was classified as **extracted**, **skipped**, or **failed**. That is a complete pass; skipped/failed are not “missing export” unless you expected lexical content for those titles.

### Step 1 — Confirm SQL closure (everything accounted for)

```bash
docker compose --profile catalog run --rm catalog stats
docker compose --profile catalog run --rm catalog audit
```

```sql
SELECT extract_status, COUNT(*) FROM canonical_lemmas GROUP BY 1 ORDER BY 1;
-- extracted + skipped + failed + pending should equal total; pending must be 0

SELECT COUNT(*) FROM entries;
-- Should match audit "Entry rows" and roughly canonical extracted count
```

API spot checks (SQL backend):

```bash
curl -s 'http://127.0.0.1:8000/words?limit=3' -H 'X-Data-Source: sql' | jq .
curl -s 'http://127.0.0.1:8000/catalog/canonical/stats' | jq .
```

Optional MDX smoke (subset):

```bash
docker compose exec api python -m src.mdict.export \
  --data-source sql --output-dir /app/build/mdict --limit 500
```

### Step 2 — Archive outcome evidence

```bash
RUN=build/catalog/state/runs/extract-canonical-a1c510103624-20261010T072424Z   # from your log

docker compose --profile catalog run --rm catalog report --scope canonical \
  --export build/catalog/reports/outcome-summary.json

docker compose --profile catalog run --rm catalog export-outcomes \
  --scope canonical --status both \
  --output build/catalog/reports/all-skipped-failed.jsonl

docker compose --profile catalog run --rm catalog export-outcomes \
  --scope canonical --status failed \
  --output build/catalog/reports/failed-only.jsonl
```

Per-batch detail from the run (only batches that had skips/fails):

```bash
cat "$RUN"/batches/batch-*.jsonl | head
```

### Step 3 — Triage plan (skipped vs failed)

| Priority | Status | Typical action |
|----------|--------|----------------|
| P0 | **failed** (13) | Fix root cause → `--retry-failed` |
| P1 | **skipped** `parse_error` / `other` | Inspect HTML; parser fix → manual re-extract or future full re-run |
| P2 | **skipped** `no_definitions_or_phonetics` (~2k) | Spot-check 10–20; often empty Wiktionary pages — **accept** |
| P3 | **skipped** `article_not_found_in_zim` | Often ZIM metadata (`Creator`, `fulltext/xapian`, …) from pre-fix sync; SQL below |

**Clear the 13 persistent “failed” metadata rows** (after upgrading catalog code):

```sql
UPDATE canonical_lemmas
SET extract_status = 'skipped',
    last_error = 'Non-HTML or internal ZIM entry (not a Wiktionary article)'
WHERE extract_status = 'failed'
  AND last_error LIKE '%Article not found in ZIM%';
```

Future `sync-canonical` runs omit these titles (`iter_article_titles` requires `text/html`).

```bash
docker compose --profile catalog run --rm catalog report --scope canonical --status failed
docker compose --profile catalog run --rm catalog report --scope canonical --status skipped --limit 200
```

Group failures in SQL:

```sql
SELECT last_error, COUNT(*)
FROM canonical_lemmas
WHERE extract_status = 'failed'
GROUP BY 1;

SELECT last_error, COUNT(*)
FROM canonical_lemmas
WHERE extract_status = 'skipped'
GROUP BY 1
ORDER BY COUNT(*) DESC
LIMIT 20;
```

### Step 4 — Retry failed only (after any parser/ZIM fix)

```bash
docker compose --profile catalog run --rm --build catalog \
  extract-canonical --retry-failed --resume --all --limit 10000
```

Re-run **Step 1–2** until `failed` is 0 or each remaining error is documented as acceptable.

### Step 5 — When to re-run the full corpus

Only if you change the HTML parser materially or need to refresh all plain-text fields:

- New parser version → consider full `extract-canonical --all --no-resume` (long).
- For a handful of lemmas after a parser fix, use lexicon preview/extract or targeted SQL updates instead of a full re-scan when possible.

See [CANONICAL_WORDLIST.md](./CANONICAL_WORDLIST.md) and [LEXICON_API.md](./LEXICON_API.md) for per-lemma debugging.
