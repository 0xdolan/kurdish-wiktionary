# DBeaver — connect to project PostgreSQL

The Compose stack exposes Postgres on **localhost** (default port **5434**, env `POSTGRES_HOST_PORT`) mapping to container **5432**. Containers (`api`, `catalog`) still use `postgres:5432` on the Docker network.

If **5434** is busy, set in `.env`: `POSTGRES_HOST_PORT=5435` and use that port in DBeaver.

## 1. Start the database

```bash
docker compose up -d postgres
```

If you changed `docker-compose.yml` ports, recreate the service once:

```bash
docker compose up -d postgres
```

## 2. New connection in DBeaver

1. **Database** → **New Database Connection** → **PostgreSQL** → **Next**
2. **Main** tab:

   | Field | Value |
   |-------|--------|
   | Host | `127.0.0.1` |
   | Port | `5434` (or your `POSTGRES_HOST_PORT`) |
   | Database | `wiktionary` |
   | Username | `wiktionary` |
   | Password | `wiktionary` |

3. **Test Connection** → download drivers if prompted → **Finish**

Use **127.0.0.1**, not `localhost`, if your system resolves `localhost` to IPv6 only and the bind is IPv4.

## 3. Tables to browse

| Table | What you see |
|-------|----------------|
| `canonical_lemmas` | Wordlist + `extract_status`, `entry_id`, `zim_sources` (JSON) |
| `entries` | Lemma headword + metadata |
| `entry_definitions` | Plain-text glosses (`value`) |
| `entry_examples`, `entry_phonetics`, … | Other parsed fields |
| `wordlist_titles` | Legacy per-ZIM index (optional) |

**Suggested SQL (SQL Editor):**

```sql
SELECT c.title, c.extract_status, e.entry,
       (SELECT string_agg(d.value, E'\n' ORDER BY d.ordinal)
        FROM entry_definitions d WHERE d.entry_id = e.id) AS definitions
FROM canonical_lemmas c
LEFT JOIN entries e ON e.id = c.entry_id
WHERE c.extract_status = 'extracted'
ORDER BY c.extracted_at DESC NULLS LAST
LIMIT 50;
```

## 4. Local `uv` / Alembic on the host

Point `.env` at the same URL as `.env.example`:

```bash
DATABASE_URL=postgresql+asyncpg://wiktionary:wiktionary@127.0.0.1:5434/wiktionary
```

Then:

```bash
uv run alembic current
uv run python -m src.catalog stats
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Connection refused | `docker compose ps` — is `postgres` up? |
| Password failed | User/password/db must all be `wiktionary` (see `docker-compose.yml`) |
| Port in use | Set `POSTGRES_HOST_PORT=5435` in `.env`, `docker compose up -d postgres`, use that port in DBeaver |
| Empty `canonical_lemmas` | Run `docker compose --profile catalog run --rm --build catalog sync-canonical` |
