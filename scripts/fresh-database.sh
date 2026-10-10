#!/usr/bin/env bash
# Backup (optional) → teardown volumes → rebuild stack. Does not run ingest/extract.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_BACKUP="${SKIP_BACKUP:-0}"
CLEAR_CATALOG_STATE="${CLEAR_CATALOG_STATE:-1}"

if [[ "${SKIP_BACKUP}" != "1" ]]; then
  "${ROOT}/scripts/backup-postgres.sh" || echo "Backup skipped or empty DB (continuing)."
fi

export CLEAR_CATALOG_STATE
"${ROOT}/scripts/stack-teardown.sh"
"${ROOT}/scripts/stack-rebuild.sh"

echo "Fresh empty database with migrations applied. Run docs/FRESH_REBUILD.md steps 3+ for data load."
