#!/bin/sh
set -e
cd /app
if ! alembic upgrade head; then
  echo "Alembic failed. Rebuild the catalog image: docker compose --profile catalog build catalog" >&2
  exit 1
fi
exec python -m src.catalog "$@"
