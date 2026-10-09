# wikitionary_to_mdx

Kurdish Wiktionary (Wîkîferheng) pipeline: Kiwix **ZIM** ingest, PostgreSQL storage, FastAPI query API, and **MDX/MDD** dictionary export via [mdict-utils](https://pypi.org/project/mdict-utils/).

## Documentation

| Document | Contents |
|----------|----------|
| [docs/FITFLOW.md](docs/FITFLOW.md) | **Git workflow** — branch, commit, pull, push, PR (FitFlow) |
| [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) | Architecture, stack, API contract, acceptance criteria |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Phased tasks (0–7), verification commands, resume checklist |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | **Docker stack**, ingest jobs, backups, troubleshooting |
| [docs/MDX_MDD_GUIDE.md](docs/MDX_MDD_GUIDE.md) | **What MDX/MDD are**, how to build/extract, CLI + planned HTTP API |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Expected latency smoke targets (ZIM vs SQL) |

Agents: follow [.cursor/rules/fitflow-git.mdc](.cursor/rules/fitflow-git.mdc) for all git operations.

## Data

Place Kiwix files under `zim/` (e.g. `zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim`). See [Kiwix wiktionary index](https://ftp.fau.de/kiwix/zim/wiktionary/).

## Quickstart (Docker)

Requires a ZIM under `./zim` and Docker with Compose v2.

```bash
cp .env.example .env   # optional overrides
docker compose up -d postgres api
curl -s http://127.0.0.1:8000/health | jq .

# Sample ingest (500 entries)
docker compose --profile ingest run --rm worker

curl -s -H 'X-Data-Source: sql' http://127.0.0.1:8000/words/heval | jq .
curl -s -H 'X-Data-Source: zim' http://127.0.0.1:8000/words/heval | jq .
```

The API container runs **Alembic migrations** on startup. Operator details: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## API examples

```bash
# List (prefer SQL after ingest; ZIM list scans the archive)
curl -s 'http://127.0.0.1:8000/words?limit=5&offset=0' -H 'X-Data-Source: sql' | jq .

# Single entry
curl -s http://127.0.0.1:8000/words/heval -H 'X-Data-Source: sql' | jq .

# OpenAPI
open http://127.0.0.1:8000/docs
```

Use header `X-Data-Source: zim|sql` to override `DEFAULT_DATA_SOURCE` from `.env`.

## MDX / MDDict export

Export via CLI or HTTP — full glossary in **[docs/MDX_MDD_GUIDE.md](docs/MDX_MDD_GUIDE.md)**.

```bash
uv run python -m src.mdict.export --data-source sql --output-dir build/mdict --limit 100
mdict -m build/mdict/wikiferheng.mdx

curl -s http://127.0.0.1:8000/mdx/about | jq .
curl -s -X POST http://127.0.0.1:8000/mdx/build -H 'Content-Type: application/json' \
  -d '{"data_source":"zim","limit":10}' | jq .
```

## Local development (uv)

```bash
uv sync
uv run uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000

uv run ruff check src tests
uv run mypy src
uv run pytest
uv run pytest --cov=src --cov-report=term-missing
```

Copy [`.env.example`](.env.example) to `.env` for `ZIM_PATH`, `DATABASE_URL`, and related settings.

### PostgreSQL ingest (host Python)

```bash
docker compose up -d postgres
uv run alembic upgrade head
uv run python -m src.extraction \
  --zim-path zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim \
  --ingest --max-entries 500
```

CI runs ruff, mypy, pytest (Testcontainers Postgres), and builds `docker/api.Dockerfile` on push/PR.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Health `degraded` | Check ZIM path on disk and Postgres (`docker compose logs postgres api`) |
| `404` on SQL lookup | Run ingest or worker profile; confirm entry exists in ZIM |
| Port 5432 in use | Stop local Postgres or change Compose port mapping |
| Slow word list on ZIM | Use SQL backend after ingest ([PERFORMANCE.md](docs/PERFORMANCE.md)) |

More: [docs/RUNBOOK.md](docs/RUNBOOK.md).

## Status

Phases **0–7** from [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) are implemented (ingest, API, Docker stack, MDX/MDD export).
