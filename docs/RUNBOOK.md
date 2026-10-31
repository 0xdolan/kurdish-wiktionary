# Operations runbook

Day-two operations for the Kurdish Wiktionary API stack.

## Stack components

| Service | Role |
|---------|------|
| `postgres` | Primary store for ingested entries |
| `api` | FastAPI (`GET /health`, `/words`, …) |
| `worker` | One-shot ZIM → Postgres ingest (Compose profile `ingest`) |
| `catalog` | Wordlist sync + raw-text extract CLI (Compose profile `catalog`) |

ZIM files are **bind-mounted** from `./zim` (not baked into images). See [README](../README.md) for download paths.

## Start / stop

```bash
# Database + API (migrations run on api container start)
docker compose up -d postgres api

# Ingest sample (500 entries) into Postgres
docker compose --profile ingest run --rm worker

# Stop everything
docker compose down
```

## Health checks

```bash
curl -s http://127.0.0.1:8000/health | jq .
```

- `status: ok` — ZIM file readable **and** Postgres reachable.
- `status: degraded` — API still responds; inspect `zim.readable` and `db.connected`.

## Ingest (full or capped)

```bash
docker compose --profile ingest run --rm worker \
  --zim-path /app/zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim \
  --ingest --max-entries 10000
```

Omit `--max-entries` for a full pass (long-running; scale worker replicas or run on a batch host).

## Backups and fresh rebuild

Postgres data lives in the Docker volume `postgres_data`.

**Backup + wipe + rebuild + full ZIM reload:** follow **[FRESH_REBUILD.md](./FRESH_REBUILD.md)** (scripts under `scripts/`).

Quick backup:

```bash
./scripts/backup-postgres.sh
```

Manual dump:

```bash
docker compose exec postgres pg_dump -U wiktionary -d wiktionary -Fc > backup.dump
```

Restore on a fresh volume with `pg_restore` (test on a non-production clone first).

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|----------------|--------|
| API `db.connected: false` | Postgres not ready or wrong `DATABASE_URL` | `docker compose ps`, check logs; use host URL only when API runs outside Compose |
| `ZIM file not found` in worker | Missing bind mount or wrong path | Ensure `./zim/wiktionary/...zim` exists on the host; match `ZIM_PATH` / `--zim-path` |
| Migrations fail on start | Old volume schema | `docker compose down -v` (destroys data) or manual Alembic repair |
| Slow `GET /words` on ZIM | Full-archive scan | Use `X-Data-Source: sql` after ingest; see [PERFORMANCE.md](./PERFORMANCE.md) |
| Rate limit 429 | Default 120 RPM | Raise `RATE_LIMIT_RPM` in `.env` for local dev |
| `Documents/wikitionary_to_mdx/` reappears (root-owned, only `zim/`) | Old Compose project **`wikitionary-to-mdx`** still running from the misspelled path | See [Legacy typo folder cleanup](#legacy-typo-folder-cleanup) |

### Legacy typo folder cleanup

An earlier repo rename left a Docker Compose project named **`wikitionary-to-mdx`** (typo). Its API container bind-mounts `./zim` from that path; Docker creates the host directory as **root**, so the empty folder keeps coming back.

Always run Compose from the real tree:

```bash
cd kurdish-wiktionary
docker compose up -d postgres api
```

Remove the old stack and folder (one-time):

```bash
docker rm -f wikitionary-to-mdx-api-1 wikitionary-to-mdx-postgres-1 2>/dev/null || true
docker volume rm wikitionary-to-mdx_postgres_data   # optional: orphan DB volume from typo project
sudo rm -rf ~/old-checkout-of-this-repo
```

Confirm only the correct project remains: `docker ps -a --filter name=wiktionary-to-mdx` should list **`wiktionary-to-mdx-*`**, not `wikitionary-to-mdx-*`.

## Raw-text catalog (wordlist → SQL)

Index ~1M lemma titles, then extract plain-text entries (no HTML in API JSON):

```bash
# CLI (Rich progress bars)
docker compose --profile catalog run --rm catalog stats
docker compose --profile catalog run --rm catalog sync-wordlist
docker compose --profile catalog run --rm catalog extract --limit 1000

# HTTP (async jobs)
curl -s -X POST http://127.0.0.1:8000/catalog/wordlist/sync | jq .
curl -s http://127.0.0.1:8000/catalog/jobs/JOB_ID | jq .
curl -s -X POST http://127.0.0.1:8000/catalog/extract \
  -H 'Content-Type: application/json' -d '{"limit":500}' | jq .
curl -s http://127.0.0.1:8000/catalog/stats | jq .
```

Details: [RAW_TEXT_PIPELINE.md](./RAW_TEXT_PIPELINE.md).

## MDX export

Build and extract flows are documented in [MDX_MDD_GUIDE.md](./MDX_MDD_GUIDE.md) (Phase 7 automation adds HTTP routes).
