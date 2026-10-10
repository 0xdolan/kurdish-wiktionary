#!/usr/bin/env bash
# Rebuild images and start postgres + api (Alembic runs on api start).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

echo "Building api, worker, and catalog images…"
docker compose --profile ingest --profile catalog build --pull

mkdir -p "${ROOT}/build/catalog/state" "${ROOT}/build/catalog/reports"
if command -v id >/dev/null && id -u catalog >/dev/null 2>&1; then
  chown -R 10001:10001 "${ROOT}/build/catalog" 2>/dev/null || true
fi

echo "Starting postgres + api…"
docker compose up -d postgres
for _ in $(seq 1 60); do
  if docker compose exec -T postgres pg_isready -U wiktionary -d wiktionary >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

docker compose up -d --build api

echo "Waiting for API health…"
for _ in $(seq 1 60); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    curl -s http://127.0.0.1:8000/health | head -c 400
    echo
    echo "Stack ready."
    exit 0
  fi
  sleep 2
done

echo "API did not become healthy in time; check: docker compose logs api" >&2
exit 1
