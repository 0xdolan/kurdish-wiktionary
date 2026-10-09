# wikitionary_to_mdx

Kurdish Wiktionary (Wîkîferheng) pipeline: Kiwix **ZIM** ingest, PostgreSQL storage, FastAPI query API, and **MDX/MDD** dictionary export via [mdict-utils](https://pypi.org/project/mdict-utils/).

## Documentation

| Document | Contents |
|----------|----------|
| [docs/FITFLOW.md](docs/FITFLOW.md) | **Git workflow** — branch, commit, pull, push, PR (FitFlow) |
| [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) | Architecture, stack, API contract, acceptance criteria |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Phased tasks (0–7), verification commands, resume checklist |
| [docs/MDX_MDD_GUIDE.md](docs/MDX_MDD_GUIDE.md) | **What MDX/MDD are**, how to build/extract, CLI + planned HTTP API |
| [docs/PERFORMANCE.md](docs/PERFORMANCE.md) | Expected latency smoke targets (ZIM vs SQL) |

Agents: follow [.cursor/rules/fitflow-git.mdc](.cursor/rules/fitflow-git.mdc) for all git operations.

## Data

Place Kiwix files under `zim/` (e.g. `wiktionary_ku_all_nopic_2026-06.zim`). See [Kiwix wiktionary index](https://ftp.fau.de/kiwix/zim/wiktionary/).

## MDX quick reference

```bash
uv add mdict-utils

# After export staging exists (Phase 7):
mdict --title title.html --description description.html -a dict.txt wikiferheng.mdx
mdict --title title.html --description description.html -a resources/ wikiferheng.mdd
mdict -m wikiferheng.mdx
mdict -x wikiferheng.mdx -d ./extracted
```

Full steps: [docs/MDX_MDD_GUIDE.md](docs/MDX_MDD_GUIDE.md).

## Development (Phase 0+)

```bash
cd /home/dolan/Documents/wikitionary_to_mdx
uv sync
uv run uvicorn src.api.app:app --reload --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/health | jq .

uv run ruff check src tests
uv run mypy src
uv run pytest
uv run pytest --cov=src --cov-report=term-missing
```

CI runs ruff, mypy, pytest (with Testcontainers Postgres integration), and builds `docker/api.Dockerfile` on push/PR.

Copy [`.env.example`](.env.example) to `.env` to override `ZIM_PATH`, database URL, and related settings.

### PostgreSQL ingest (Phase 3+)

```bash
docker compose up -d postgres
uv run alembic upgrade head
uv run python -m src.extraction --zim-path zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim --ingest --max-entries 500
curl -s -H 'X-Data-Source: sql' http://127.0.0.1:8000/words/heval | jq .
```

## Status

**Phase 0** (foundation) complete when verification above passes — see [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
