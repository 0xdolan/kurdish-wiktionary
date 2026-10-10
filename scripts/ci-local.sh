#!/usr/bin/env bash
# Local CI — must match .github/workflows/ci.yml (quality + Docker builds).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "==> ci-local: uv sync --frozen"
uv sync --frozen

echo "==> ci-local: ruff"
uv run ruff check src tests

echo "==> ci-local: mypy"
uv run python -m mypy src

echo "==> ci-local: pytest + coverage (fail_under from pyproject.toml)"
uv run python -m pytest --cov=src --cov-report=term-missing --cov-report=xml -v

echo "==> ci-local: docker build (api, worker, catalog)"
docker build -f docker/api.Dockerfile -t wiktionary-api:ci-local .
docker build -f docker/worker.Dockerfile -t wiktionary-worker:ci-local .
docker build -f docker/catalog.Dockerfile -t wiktionary-catalog:ci-local .

echo "ci-local: ALL PASSED"
