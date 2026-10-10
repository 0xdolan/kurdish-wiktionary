#!/usr/bin/env bash
# Remove catalog CLI checkpoints and run logs (does not touch Postgres).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rm -rf "${ROOT}/build/catalog/state/"* 2>/dev/null || true
mkdir -p "${ROOT}/build/catalog/state/checkpoints" "${ROOT}/build/catalog/reports"
echo "Cleared ${ROOT}/build/catalog/state/ (checkpoints + run logs)."
