# Fresh database rebuild — backup, reset, full ZIM → SQL (A→Z)

## Rephrased operator goal

**Before wiping anything, take a restorable PostgreSQL backup. Tear down the Compose stack and delete the `postgres_data` volume so the database is empty. Rebuild all application images, apply migrations on a new Postgres instance, then reload real lexical data from local Kurdish Wiktionary ZIM files using the current canonical pipeline (`sync-canonical` → `extract-canonical --all`), verify with stats/audit, and use the API with `X-Data-Source: sql`.**

---

## Prerequisites

- ZIM files on the host (not in git):

  - `zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim`
  - `zim/wiktionary/wiktionary_ku_all_maxi_2026-08.zim` (optional but used by `ZIM_PATHS` for canonical merge)

- Docker Compose v2, enough disk for Postgres (~tens of GB for full extract).

- Catalog write dir (UID **10001** inside container):

```bash
mkdir -p build/catalog/state build/catalog/reports
sudo chown -R 10001:10001 build/catalog   # or: chmod -R a+rwX build/catalog
```

---

## Phase A — Backup current SQL (optional but recommended)

```bash
cd /home/dolan/Documents/wiktionary_to_mdx
chmod +x scripts/*.sh
./scripts/backup-postgres.sh
```

Artifacts (gitignored):

- `backups/postgres/wiktionary_YYYYMMDD_HHMMSS.dump` — restore with `pg_restore`
- `backups/postgres/wiktionary_YYYYMMDD_HHMMSS.sql.gz` — plain SQL

**Restore example** (on a running postgres service):

```bash
docker compose up -d postgres
gunzip -c backups/postgres/wiktionary_*.sql.gz | docker compose exec -T postgres \
  psql -U wiktionary -d wiktionary
# or: pg_restore -U wiktionary -d wiktionary < backups/postgres/wiktionary_*.dump
```

---

## Phase B — Remove Postgres + containers + volume

```bash
./scripts/stack-teardown.sh
# Also wipe catalog checkpoints for a truly clean re-extract:
CLEAR_CATALOG_STATE=1 ./scripts/stack-teardown.sh
```

Or one shot (backup + teardown + rebuild empty DB):

```bash
./scripts/fresh-database.sh
# Skip backup if volume already empty:
SKIP_BACKUP=1 ./scripts/fresh-database.sh
```

---

## Phase C — Rebuild images and start empty stack

```bash
./scripts/stack-rebuild.sh
```

This builds **api**, **worker** (`ingest` profile), and **catalog** (`catalog` profile), starts **postgres** + **api**, and runs **Alembic migrations** via the API entrypoint.

Verify:

```bash
curl -s http://127.0.0.1:8000/health | jq .
docker compose ps
```

---

## Phase D — Index lemmas (canonical wordlist)

Scans all paths in `ZIM_PATHS` and fills `canonical_lemmas`:

```bash
docker compose --profile catalog run --rm --build catalog sync-canonical
docker compose --profile catalog run --rm catalog stats
```

---

## Phase E — Full extract (real data into `entries`)

**This is long-running (~1M lemmas; use tmux/screen).**

```bash
# After a fresh Postgres volume: start clean (do NOT pass --resume)
docker compose --profile catalog run --rm --build catalog \
  extract-canonical --all --limit 10000 --no-resume

# After interrupt/Ctrl+C on the same database: continue
docker compose --profile catalog run --rm --build catalog \
  extract-canonical --all --limit 10000 --resume
```

Stale checkpoints on disk are **auto-discarded** when SQL progress no longer matches, but always use **`--no-resume`** right after `./scripts/fresh-database.sh` or `stack-teardown`.

Flags:

| Flag | Meaning |
|------|---------|
| `--all` | Process entire canonical wordlist |
| `--limit 10000` | Batch size per run (repeat until stats show pending ≈ 0) |
| `--resume` | Continue from checkpoint (same database) |
| `--no-resume` | Ignore/delete checkpoint (required after fresh DB rebuild) |
| `--retry-failed` | Re-queue rows in `failed` status only |

Monitor:

```bash
docker compose --profile catalog run --rm catalog stats
docker compose --profile catalog run --rm catalog audit
docker compose --profile catalog run --rm catalog report --scope canonical --export build/catalog/reports/outcomes.json
```

---

## Phase F — Optional legacy paths

**Direct ZIM ingest (hybrid `/words` SQL path, separate from catalog batching):**

```bash
docker compose --profile ingest run --rm --build worker \
  --zim-path /app/zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim \
  --ingest
# Dev cap: add --max-entries 5000
```

**Legacy wordlist pipeline** (per-ZIM `wordlist_titles`):

```bash
docker compose --profile catalog run --rm catalog sync-wordlist
docker compose --profile catalog run --rm catalog extract --all
```

For this project, **canonical extract (Phase D–E)** is the primary “full real data” path after recent parser changes.

---

## Phase G — Verify API

```bash
curl -s http://127.0.0.1:8000/catalog/canonical/stats | jq .
curl -s -H 'X-Data-Source: sql' http://127.0.0.1:8000/words/heval | jq .
curl -s 'http://127.0.0.1:8000/words?limit=5' -H 'X-Data-Source: sql' | jq .
```

---

## Phase H — Optional MDX export (downstream)

```bash
docker compose exec api python -m src.mdict.export --data-source sql --output-dir /app/build/mdict --limit 100
# Full export: omit --limit (run as batch job)
```

See [MDX_MDD_GUIDE.md](./MDX_MDD_GUIDE.md).

---

## One-page cheat sheet (copy/paste)

```bash
cd /home/dolan/Documents/wiktionary_to_mdx
chmod +x scripts/*.sh
mkdir -p build/catalog/state build/catalog/reports backups/postgres
sudo chown -R 10001:10001 build/catalog 2>/dev/null || chmod -R a+rwX build/catalog

./scripts/backup-postgres.sh
CLEAR_CATALOG_STATE=1 ./scripts/stack-teardown.sh
./scripts/stack-rebuild.sh

docker compose --profile catalog run --rm --build catalog sync-canonical
docker compose --profile catalog run --rm --build catalog extract-canonical --all --limit 10000 --no-resume

docker compose --profile catalog run --rm catalog stats
docker compose --profile catalog run --rm catalog audit
curl -s -H 'X-Data-Source: sql' http://127.0.0.1:8000/words/heval | jq .
```

---

## Related

- [RUNBOOK.md](./RUNBOOK.md) — day-two ops
- [CANONICAL_WORDLIST.md](./CANONICAL_WORDLIST.md) — dual-ZIM canonical workflow
- [CATALOG_VERIFICATION.md](./CATALOG_VERIFICATION.md) — skipped/failed handling
