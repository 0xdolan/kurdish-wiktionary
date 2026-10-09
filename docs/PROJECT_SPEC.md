# Kurdish Wiktionary Pipeline — Engineering Specification

**Document version:** 1.1  
**Last updated:** 2026-10-09  
**Repository target layout:** `wiktionary_pipeline/` (may live at repo root or as the primary package tree)  
**Primary data source:** Kiwix ZIM archives `wiktionary_ku_*.zim` (MediaWiki dump of `ku.wiktionary.org` / Wîkîferheng)

---

## 1. Executive summary

Build a production-grade system that **extracts**, **normalizes**, **persists**, and **serves** Kurdish Wiktionary lexical entries from Kiwix `.zim` files. The solution comprises:

1. An **offline/async extraction pipeline** that parses ZIM HTML into a stable, nullable JSON schema and **upserts** into PostgreSQL.
2. A **hybrid read layer** (Strategy pattern) that answers identical API responses from either **live ZIM** or **PostgreSQL**.
3. A **FastAPI** service with health checks, pagination, structured errors, CORS, and rate limiting.
4. **Docker Compose** for local and deployable stacks (API + worker + PostgreSQL).
5. **CI/CD**, **strict typing**, **linting**, and **tests** targeting ≥90% coverage path.
6. **MDX/MDD export** via **[mdict-utils](https://pypi.org/project/mdict-utils/)** — pack/unpack, API-driven build and extract jobs, operator documentation ([MDX_MDD_GUIDE.md](./MDX_MDD_GUIDE.md)).
7. **Raw-text catalog** — lemma wordlist in SQL, sequential plain-text extraction (no HTML in JSON); see [RAW_TEXT_PIPELINE.md](./RAW_TEXT_PIPELINE.md).

The Wiktionary HTML layout is not fixed over time; parsers must be **structural and defensive**, inferring a baseline schema from representative pages while defaulting missing sections to empty collections or `null`.

---

## 2. Goals and non-goals

### 2.1 Goals

| ID | Goal |
|----|------|
| G1 | Idempotent ingestion: re-running extraction on a new `wiktionary_ku_*.zim` upserts by natural key without duplicate rows. |
| G2 | Single canonical response shape for all read paths (ZIM and SQL). |
| G3 | Runtime-selectable data source via config and optional `X-Data-Source: zim \| sql` header. |
| G4 | Async I/O throughout hot paths (DB, optional thread pool for libzim). |
| G5 | Observable operations: structured logging, health diagnostics, RFC 7807-style JSON errors. |
| G6 | Reproducible environments via `uv` lockfiles and container images. |
| G7 | Build and extract **MDict 2.0** `.mdx` / `.mdd` pairs from SQL or ZIM using `mdict-utils`; document format and usage for operators. |
| G8 | Maintain a SQL-backed **lemma catalog** (~1M titles) and extract **plain-text** entries independently of MDX/HTML export. |

### 2.2 Non-goals (v1)

- Separate Kiwix ZIM files per Kurdish variety (`ckb`, `kmr`); only `wiktionary_ku_*` exists on public mirrors. Variety may be captured later in `metadata` if detectable in page content.
- Public write API for Wiktionary lemma editing (MDX **build/extract** jobs are allowed).
- Full-text search parity with Kiwix Xapian index (optional follow-up: `pg_trgm` / dedicated search service).
- Writing **MDict 3.0** binaries (read v3 with `mdict-utils`; pack targets v2.0).

---

## 3. Technical stack (mandatory)

| Layer | Choice | Notes |
|-------|--------|--------|
| Package / env | **uv** | Lockfile, workspaces, venv sync |
| API | **FastAPI** | Async routes, router modules, lifespan hooks |
| DB | **PostgreSQL 16+** | Async SQLAlchemy 2.0, Alembic migrations |
| ZIM | **libzim** (primary) | CPU-bound reads; wrap in `asyncio.to_thread` where needed |
| HTML | **selectolax** (primary), **BeautifulSoup4** (fallback / tests) | Prefer speed; BS4 for edge-case fixtures |
| MDX / MDD | **[mdict-utils](https://pypi.org/project/mdict-utils/)** ≥1.3.14 | CLI `mdict` for pack/unpack; wrap in `asyncio.create_subprocess_exec` |
| Config | **Pydantic v2** `BaseSettings` | Secrets from env; no secrets in repo |
| Containers | Multi-stage **Dockerfiles** + **docker-compose.yml** | `api`, `worker`, `catalog`, `postgres` |
| Quality | **pytest** + **pytest-asyncio**, **mypy** (strict), **ruff** | **pytest-cov** toward 90%+ |

---

## 4. Repository layout

```
wiktionary_pipeline/
├── .github/workflows/          # CI: ruff, mypy, pytest, docker build
├── docker/
│   ├── api.Dockerfile
│   └── worker.Dockerfile
├── migrations/                 # Alembic
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── core/                   # Domain models, exceptions, security helpers
│   ├── extraction/             # ZIM iteration, HTML parsers, ingest jobs
│   ├── mdict/                  # MDX render, staging, mdict-utils wrapper
│   ├── repository/             # ZimRepository, SqlRepository, factory
│   └── api/                    # FastAPI app, routers, schemas, deps
│       └── routers/mdx.py      # Build / extract / meta / lookup
├── assets/mdict/templates/     # title.html, description.html defaults
├── tests/
│   ├── conftest.py
│   ├── unit/
│   └── integration/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## 5. Canonical entry schema (API + extraction output)

All parsers and serializers MUST conform to this **nullable, unified** model (Pydantic v2):

| Field | Type | Semantics |
|-------|------|-----------|
| `entry` | `str` | Primary lemma (required when record is valid) |
| `part_of_speech` | `list[str]` \| `str` | Normalized to `list[str]` at API boundary preferred |
| `definitions` | `list[str]` | Glosses / meanings |
| `phonetic_transcriptions` | `list[str]` | IPA, transliteration blocks |
| `pronunciations` | `list[str]` | Audio URLs/paths or pronunciation symbols |
| `examples` | `list[str]` | Usage examples |
| `synonyms` | `list[str]` | |
| `antonyms` | `list[str]` | |
| `etymology` | `str \| null` | |
| `derived_terms` | `list[str]` | |
| `metadata` | `dict[str, Any]` | ZIM UUID, scraper date, `layout_version`, source path, optional language tags |

**Empty vs missing:** Omitted HTML sections → empty lists; unknown optional blocks → `null` for scalars.

---

## 6. Domain rules

### 6.1 Natural key and idempotence

- **Primary identity:** `(entry_normalized, language_code)` where `language_code` defaults to `ku` for this corpus unless extracted per-section (future: `kmr`, `ckb` from content).
- **Normalization:** Unicode NFC, strip whitespace; case-folding policy documented in `core/normalize.py` (Wiktionary titles are case-sensitive — preserve display form, normalize for lookup).
- **Upsert:** On re-ingest from a newer ZIM, update scalar fields and **replace** child collections transactionally (definitions, examples, etc.) keyed by parent entry id.

### 6.2 Hybrid repository contract

```python
# Conceptual protocol (name in code: WiktionaryRepositoryProto)
async def get_entry(word: str) -> WiktionaryEntry | None: ...
async def list_entries(limit: int, offset: int) -> tuple[list[WiktionaryEntry], int]: ...
async def health_detail() -> RepositoryHealth: ...
```

Implementations:

- **ZimRepository** — opens configured path, resolves title → HTML, parses on demand.
- **SqlRepository** — indexed SQL queries, eager or joined loads for child rows.

**Selection order:** Request header `X-Data-Source` (if valid) overrides `Settings.default_data_source`.

---

## 7. Database design (PostgreSQL)

### 7.1 Normalized tables (illustrative)

- `entries` — id (PK), entry, entry_normalized, language_code, etymology, metadata (JSONB), zim_uuid, source_date, updated_at
- `entry_definitions`, `entry_examples`, `entry_synonyms`, `entry_antonyms`, `entry_pronunciations`, `entry_phonetics`, `entry_derived_terms`, `entry_parts_of_speech` — FK → `entries.id` ON DELETE CASCADE, ordinal column for stable ordering

### 7.2 Indexing

- B-tree on `(entry_normalized, language_code)` UNIQUE
- B-tree on `entry_normalized` for prefix search
- Optional `pg_trgm` GIN on `entry` / `entry_normalized` for fuzzy search (Phase 3 deliverable)

### 7.3 Migrations

- Alembic revision chain from empty DB to v1 schema
- Seed optional: small fixture entries for integration tests only (not production dump)

---

## 8. Extraction pipeline (Phase 1)

### 8.1 Inputs

- CLI / worker command: `--zim-path /path/to/wiktionary_ku_*.zim`
- Optional: `--batch-size`, `--max-entries` (dev), `--dry-run`

### 8.2 Processing flow

1. Open ZIM; read metadata (Date, UUID, Source).
2. Iterate article entries (skip namespaces ≠ Main / Wiktionary content).
3. For each HTML page: detect layout version heuristically (store in `metadata.layout_version`).
4. Parse to `WiktionaryEntry` pydantic model.
5. Upsert in batches inside transactions.
6. Emit metrics: processed, skipped, failed (with sample error log).

### 8.3 HTML parsing strategy

- Discover baseline selectors from **sample corpus** (high-density entries: multi-POS, etymology, audio).
- Use MediaWiki patterns: `.mw-parser-output`, section headings (`h2`–`h4`), definition lists, `{lang}` sections where present.
- Unit tests MUST include **frozen HTML fixtures** for variant layouts.

---

## 9. HTTP API (Phase 4 + Phase 7 + Phase 8)

### 9.1 Wiktionary read API (Phase 4)

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/health` | `{ status, zim: { path, readable, uuid }, db: { connected, latency_ms } }` |
| GET | `/words` | Query: `limit`, `offset`; returns `{ items, total, limit, offset }` |
| GET | `/words/{word}` | Single entry or 404 |

### 9.2 MDX / MDD API (Phase 7)

See [MDX_MDD_GUIDE.md](./MDX_MDD_GUIDE.md) for format background and CLI equivalents.

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/mdx/about` | Documentation payload: what MDX/MDD are, pipeline overview, reference links |
| GET | `/mdx/meta` | Dictionary metadata (`mdict -m`) for path under `MDX_WORK_DIR` |
| GET | `/mdx/keys` | Paginated headword list |
| GET | `/mdx/lookup/{headword}` | HTML definition for one key |
| POST | `/mdx/extract` | Async job: unpack `.mdx` / optional `.mdd` to staging |
| GET | `/mdx/extract/{job_id}` | Job status and output paths |
| POST | `/mdx/build` | Async job: `WiktionaryEntry` → `dict.txt` + resources → pack `.mdx`/`.mdd` |
| GET | `/mdx/build/{job_id}` | Progress and error samples |
| GET | `/mdx/build/{job_id}/download` | Zip of artifacts + `manifest.json` |

Build requests accept `data_source` (`sql` \| `zim`), `include_media`, optional `limit` (dev), and title/description overrides.

### 9.3 Raw-text catalog API (Phase 8)

See [RAW_TEXT_PIPELINE.md](./RAW_TEXT_PIPELINE.md). Responses use the canonical entry schema (plain text fields only).

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/catalog/stats` | ZIM title count, wordlist totals by status, `entries` row count |
| GET | `/catalog/wordlist` | Paginated wordlist rows; optional `status` filter |
| POST | `/catalog/wordlist/sync` | **202** — async job: scan ZIM titles → upsert `wordlist_titles` |
| POST | `/catalog/wordlist/sync/wait` | Synchronous sync (dev; may timeout on full corpus) |
| POST | `/catalog/extract` | **202** — async job: parse pending titles → upsert `entries` |
| POST | `/catalog/extract/wait` | Synchronous extract for small `limit` |
| GET | `/catalog/jobs/{job_id}` | Job progress for catalog sync/extract |

CLI equivalent: `python -m src.catalog` (`stats`, `sync-wordlist`, `extract`).

**Cross-cutting:**

- CORS from settings
- Rate limiting (e.g. token bucket per IP; configurable)
- Global exception handlers → JSON `{ type, title, status, detail, instance }`

---

## 10. Security and operations

- No authentication in v1 (document extension point for API keys behind reverse proxy).
- ZIM path must be read-only mount in containers.
- DB credentials via env only.
- Worker and API share image layers but separate entrypoints.

---

## 11. Testing strategy (Phase 5)

| Layer | Scope |
|-------|--------|
| Unit | HTML parser edge cases; normalization; repository mocks |
| Integration | Testcontainers PostgreSQL; optional small real ZIM slice or mocked libzim |
| MDX | Tiny fixture dict round-trip pack/unpack; API build job with `limit=10` |
| API | httpx `AsyncClient` against FastAPI app |

**Coverage:** `pytest-cov` with `--cov=src --cov-report=term-missing`; fail CI under threshold once baseline established (staged: 70% → 90%).

---

## 12. Configuration (environment variables)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async PostgreSQL URL (`postgresql+asyncpg://...`) |
| `ZIM_PATH` | Absolute path to active `.zim` |
| `DEFAULT_DATA_SOURCE` | `zim` or `sql` |
| `CORS_ORIGINS` | Comma-separated |
| `RATE_LIMIT_RPM` | Requests per minute per client |
| `LOG_LEVEL` | e.g. `INFO` |
| `MDX_WORK_DIR` | Staging and job output for MDX/MDD (default `./build/mdict`) |
| `MDX_DEFAULT_TITLE` | Default dictionary title HTML |
| `MDX_BUILD_MAX_CONCURRENT` | Concurrent pack jobs (default `1`) |
| `MDX_INCLUDE_MEDIA` | Default include MDD when assets available |

---

## 13. MDX/MDD export (Phase 7 summary)

1. **Render** canonical entries to UTF-8 `dict.txt` (`headword\thtml`).
2. **Stage** shared CSS/audio/images under `resources/` for MDD (from ZIM maxi or linked URLs stripped to relative paths).
3. **Pack** with `mdict-utils`: `--title`, `--description`, `-a dict.txt` → `.mdx`; `-a resources/` → `.mdd`.
4. **Verify** with `mdict -m`, `-k`, sample lookup before publishing.

Implementation modules: `src/mdict/renderer.py`, `txt_writer.py`, `pack.py` (subprocess wrapper), `jobs.py` (async job state), `src/api/routers/mdx.py`.

---

## 14. Acceptance criteria (release-ready)

1. `uv sync` installs locked deps; `ruff check`, `mypy src`, `pytest` pass in CI.
2. `docker compose up` brings API + Postgres; health returns green when ZIM mounted and DB migrated.
3. Ingest of configured ZIM completes with upsert semantics verified by double-run test.
4. `/words/{word}` returns identical schema for `X-Data-Source: zim` and `sql` for sampled entries.
5. Documentation: README runbook + this spec + [MDX_MDD_GUIDE.md](./MDX_MDD_GUIDE.md) + implementation plan with phase status.
6. MDX: POST `/mdx/build` produces valid `.mdx`/`.mdd`; GET `/mdx/about` documents format; round-trip test passes on fixture dictionary.

---

## 15. References

- Kiwix Wiktionary ZIM index: https://ftp.fau.de/kiwix/zim/wiktionary/
- Local data: `zim/wiktionary_ku_*.zim` (legacy `ku` wiki; contains mixed Kurdish content)
- Wiktionary Kurdish language codes: `ckb`, `kmr`, etc. (for future filtering, not separate ZIMs)
- **mdict-utils:** https://pypi.org/project/mdict-utils/ · https://github.com/liuyug/mdict-utils
- **MDict format analysis:** https://bitbucket.org/xwang/mdict-analysis/src/master/
- **MDict writer reference:** https://github.com/zhansliu/writemdict
