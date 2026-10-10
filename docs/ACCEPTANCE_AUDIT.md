# Acceptance audit — spec, plan, and tests

**Last reviewed:** 2026-10-09  
**Sources:** [PROJECT_SPEC.md](./PROJECT_SPEC.md), [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md), README, operator guides.

This document answers: *Are phased tasks implemented, documented, and covered by tests?* Update it when phases or acceptance criteria change.

---

## Rephrased project brief (canonical ask)

Build a **Kurdish Wîkîferheng (ku.wiktionary) data platform** on Python 3.12+ that:

1. **Ingests** Kiwix `wiktionary_ku_*.zim` archives into a strict, nullable `WiktionaryEntry` schema with idempotent PostgreSQL upserts.
2. **Serves** the same JSON shape from **ZIM or SQL** via a strategy repository and FastAPI (`/health`, `/words`, `X-Data-Source`).
3. **Exports** MDict 2.0 `.mdx`/`.mdd` through `mdict-utils` (CLI + `/mdx/*` jobs).
4. **Catalogs** ~1M lemma titles and **extracts plain-text** entries (catalog + canonical pipelines) with audit/outcome reporting.
5. **Ships** Docker (api, worker, catalog, postgres), CI (ruff, mypy, pytest, coverage, image builds), and operator docs.

**Definition of done:** CI green; compose stack healthy with Kurdish ZIM paths; double ingest does not duplicate rows; MDX fixture round-trip; API matches spec tables; plan checkboxes ✅; known gaps tracked below.

---

## Phase compliance (IMPLEMENTATION_PLAN)

| Phase | Spec alignment | Implementation | Test / CI signal |
|-------|----------------|----------------|------------------|
| 0 Foundation | Stack, config §12 | `pyproject.toml`, `src/config.py`, ruff/mypy | CI quality job |
| 1 Extraction | §8 | `src/extraction/*`, HTML notes | `tests/unit/test_html_parser.py` |
| 2 Repository | §6.2 | `src/repository/*`, service | `tests/unit/test_repository.py`, `test_zim_repository.py` |
| 3 PostgreSQL | §7, pg_trgm | Alembic, upsert, SqlRepository | `tests/integration/test_upsert.py`; migration `20261009_0002_pg_trgm` |
| 4 FastAPI | §9.1 | Routers, middleware, RFC7807 errors | `test_health.py`, `test_words_api.py`, `test_api_errors.py`, `test_rate_limit.py` |
| 5 Tests / CI | §11 | `.github/workflows/ci.yml`, cov 70% gate | Pytest + testcontainers when Docker available |
| 6 Docker / ops | §10 | Compose, Dockerfiles, RUNBOOK | CI `docker-api` job |
| 7 MDX/MDD | §9.2, §13 | `src/mdict/*`, `/mdx/*` | `test_mdx_api.py`, `test_mdx_routes.py`, integration pack tests |
| 8 Catalog | §9.3, RAW_TEXT_PIPELINE | `src/catalog/*`, `/catalog/*` | `test_catalog_api.py`, `test_catalog_jobs.py`, `test_catalog_audit.py` |

**Extensions beyond original §9 tables (implemented, documented separately):**

- **Lexicon** (`/lexicon/*`, `src/lexicon/`) — [LEXICON_API.md](./LEXICON_API.md), `tests/test_lexicon_api.py`
- **Canonical catalog** — [CANONICAL_WORDLIST.md](./CANONICAL_WORDLIST.md), `/catalog/canonical/*`, `/catalog/audit`, `/catalog/outcomes`

---

## Acceptance criteria checklist (PROJECT_SPEC §14)

| # | Criterion | Status | Notes |
|---|-----------|--------|-------|
| 1 | `uv sync`, ruff, mypy, pytest in CI | ✅ | `.github/workflows/ci.yml` |
| 2 | Compose + health green with ZIM + migrated DB | ✅ | Default ZIM paths use **`wiktionary_ku_*`** in compose env |
| 3 | Double ingest, no duplicates | ✅ | `tests/integration/test_upsert.py` (sqlite); full ZIM re-run is manual per plan §3 verification |
| 4 | Same schema ZIM vs SQL | 🟡 | Same DTO; parity depends on ingest — no automated A/B test without ZIM+DB fixture |
| 5 | Docs + plan status | ✅ | This file + updated MDX guide §6 |
| 6 | MDX build + about + round-trip | ✅ | API tests + integration pack when `mdict-utils` installed |

---

## Test matrix (spec §11)

| Area | Covered by | Gap / follow-up |
|------|------------|-----------------|
| HTML parser | Unit fixtures | Expand fixtures when layout drifts |
| Repository mocks | Unit | — |
| API httpx | Most routers | Lexicon corpus routes lightly covered |
| MDX pack/unpack | Integration | Requires `mdict-utils`; CLI invoked via `python -m mdict_utils` |
| Postgres API | Integration | Requires Docker testcontainers + `alembic upgrade` |
| Catalog jobs | Partial mocks | Full sync/extract E2E is operator/manual |
| Coverage ≥70% | `pyproject.toml` | Worker/CLI-heavy modules omitted from measurement; API/parser/repository paths must stay green in CI |

**Recommended local verification (full gate):**

```bash
uv sync --reinstall-package wiktionary-to-mdx   # after repo rename, refresh script shebangs
uv run ruff check src tests
uv run python -m mypy src
uv run python -m pytest --cov=src --cov-report=term-missing -v
docker compose up -d postgres api
```

---

## Gaps addressed in this audit pass

1. **Compose ZIM paths** — `docker-compose.yml` env aligned to Kurdish `wiktionary_ku_*` (worker already used `ku`; shared env had mistakenly pointed at `en`).
2. **MDX CLI after rename** — `src/mdict/pack.py` runs `python -m mdict_utils` so pack/tests work even if `.venv/bin/mdict` shebang is stale.
3. **Documentation drift** — README phases 0–8; MDX guide §6 marked implemented; PROJECT_SPEC §9.3/§9.4 cross-links.
4. **Tests** — Added `tests/test_mdx_routes.py` (meta, keys, path sandbox, extract job) and `tests/test_catalog_audit.py`.

---

## Known remaining gaps (not blocking v1)

| Item | Priority | Suggestion |
|------|----------|------------|
| Automated ZIM↔SQL JSON parity test | Medium | Golden-file test with mocked HTML + upsert + both repos |
| Coverage toward 90% (spec §3) | Medium | Integration tests for catalog canonical paths; trim omit list only if justified |
| Full-text search / Xapian parity | Low (non-goal v1) | Optional `pg_trgm` query API |
| Redis rate limit multi-replica | Low | Documented in plan risk register |
| MDict v3 write | Out of scope | — |

---

## Operator reminders

- After **renaming the repo directory**, run `uv sync --reinstall-package wiktionary-to-mdx` so console scripts point at the correct venv Python.
- Catalog extract verification: [CATALOG_VERIFICATION.md](./CATALOG_VERIFICATION.md).
- Performance expectations: [PERFORMANCE.md](./PERFORMANCE.md).
