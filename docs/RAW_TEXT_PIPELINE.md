# Raw-text catalog & extraction pipeline

**Goal:** Build a **lemma index in SQL first**, then **extract structured plain text** (no HTML) entry-by-entry. HTML/MDX remains a separate presentation layer for other projects.

## Rephrased product intent

1. **Inventory** — Scan the ZIM and persist every Wiktionary lemma title in PostgreSQL (`wordlist_titles`).
2. **Statistics** — Report totals: ZIM candidates, indexed titles, pending vs extracted vs skipped/failed, and full `entries` row counts.
3. **Sequential extract** — Walk the wordlist (or one title at a time via API), fetch HTML from ZIM only at extract time, parse to **`WiktionaryEntry` plain-text fields**, upsert `entries` + child rows, update wordlist status.
4. **Operator UX** — **Rich** CLI with progress bars for sync and extract; HTTP API mirrors stats, wordlist pages, and job progress.

## Rules (this pipeline)

| Rule | Detail |
|------|--------|
| **R1** | API/CLI **catalog** responses use **raw text** (`definitions[]`, `examples[]`, …). No HTML in JSON for catalog/extract paths. |
| **R2** | **Wordlist before bulk extract** — run `sync-wordlist` (or `POST /catalog/wordlist/sync`) before large `extract` jobs. |
| **R3** | **One ZIM title → one wordlist row** per `(title_normalized, zim_uuid)`. |
| **R4** | Extract status is tracked on the wordlist row: `pending` → `extracted` \| `skipped` \| `failed`. |
| **R5** | MDX renderer (`src/mdict/`) is **out of scope** for catalog; do not pipe catalog output through HTML export. |

## Phases

| Phase | Name | Status |
|-------|------|--------|
| **C0** | Spec + schema (`wordlist_titles`) | ✅ Done |
| **C1** | ZIM title scan + SQL sync + stats | ✅ Done |
| **C2** | Rich CLI (`python -m src.catalog`) | ✅ Done |
| **C3** | HTTP `/catalog/*` API + async jobs | ✅ Done |
| **C4** | Docker catalog profile + RUNBOOK | ✅ Done |

## Tasks (C0–C3)

- [x] **C0.1** This document + Cursor rule pointer.
- [x] **C1.1** `ZimReader.iter_article_titles()` (no HTML load).
- [x] **C1.2** Alembic `wordlist_titles` table + indexes.
- [x] **C1.3** `sync_wordlist_to_sql`, `compute_catalog_stats`.
- [x] **C2.1** CLI: `stats`, `sync-wordlist`, `extract --limit N` with Rich progress.
- [x] **C3.1** `GET /catalog/stats`, `GET /catalog/wordlist`, async `POST /catalog/wordlist/sync`, `POST /catalog/extract`, `GET /catalog/jobs/{id}`.
- [x] **C3.2** Sync helpers: `POST /catalog/wordlist/sync/wait`, `POST /catalog/extract/wait` (small batches / dev).
- [x] **C4.1** Docker `catalog` service (profile `catalog`); [RUNBOOK.md](./RUNBOOK.md) section.

## Verification

```bash
uv sync
uv run alembic upgrade head
uv run python -m src.catalog stats
uv run python -m src.catalog sync-wordlist
uv run python -m src.catalog extract --limit 200
curl -s http://127.0.0.1:8000/catalog/stats | jq .
curl -s 'http://127.0.0.1:8000/catalog/wordlist?limit=5' | jq .
curl -s -X POST http://127.0.0.1:8000/catalog/wordlist/sync | jq .
curl -s -X POST http://127.0.0.1:8000/catalog/extract -H 'Content-Type: application/json' -d '{"limit":50}' | jq .
```

## Related docs

- [PROJECT_SPEC.md](./PROJECT_SPEC.md) — core API (`/words`) remains hybrid ZIM/SQL lookup.
- [MDX_MDD_GUIDE.md](./MDX_MDD_GUIDE.md) — HTML/MDict export (downstream, optional).
