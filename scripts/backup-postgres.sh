#!/usr/bin/env bash
# Logical backup of the wiktionary Postgres database (custom-format pg_dump).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${ROOT}/backups/postgres"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/wiktionary_${STAMP}.dump"
SQL_OUT="${BACKUP_DIR}/wiktionary_${STAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"
cd "${ROOT}"

if ! docker compose ps postgres --status running -q 2>/dev/null | grep -q .; then
  echo "Starting postgres for backup…"
  docker compose up -d postgres
  for _ in $(seq 1 30); do
    if docker compose exec -T postgres pg_isready -U wiktionary -d wiktionary >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

echo "Writing ${OUT}"
docker compose exec -T postgres pg_dump -U wiktionary -d wiktionary -Fc >"${OUT}"

echo "Writing ${SQL_OUT} (plain SQL, gzipped)"
docker compose exec -T postgres pg_dump -U wiktionary -d wiktionary --no-owner --no-acl | gzip -9 >"${SQL_OUT}"

ls -lh "${OUT}" "${SQL_OUT}"
echo "Backup complete."
