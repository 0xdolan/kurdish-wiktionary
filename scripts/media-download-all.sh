#!/usr/bin/env bash
# Download all entry_media assets from ZIM/Commons into build/media (SQL-backed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BATCH_SIZE="${MEDIA_DOWNLOAD_BATCH_SIZE:-500}"

exec uv run python -m src.lexicon media-download-all \
  --confirm \
  --all \
  --limit "$BATCH_SIZE" \
  "$@"
