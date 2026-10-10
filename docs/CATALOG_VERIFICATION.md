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
