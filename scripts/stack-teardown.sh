#!/usr/bin/env bash
# Stop all compose services and remove the Postgres volume (destructive).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT}"

# Default: wipe catalog checkpoints when Postgres volume is destroyed (avoid stale resume).
CLEAR_CATALOG_STATE="${CLEAR_CATALOG_STATE:-1}"

echo "Stopping services and removing volumes (postgres_data)…"
docker compose --profile ingest --profile catalog down -v --remove-orphans

if [[ "${CLEAR_CATALOG_STATE}" == "1" ]]; then
  echo "Clearing catalog checkpoints under build/catalog/state (host)…"
  rm -rf "${ROOT}/build/catalog/state/"* 2>/dev/null || true
fi

echo "Teardown complete. Postgres data volume removed."
