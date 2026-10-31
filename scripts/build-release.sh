#!/usr/bin/env bash
# Build the whole release from the ZIM files. Stages are safe to rerun.
# Usage: ./scripts/build-release.sh [--skip-download]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

run() { uv run python -m src.dataset "$@"; }

run parse
run media-extract
run verify || echo "This build differs from the published release: see docs/REPRODUCE.md."
if [[ "${1:-}" != "--skip-download" ]]; then
  run media-download
  run media-licences
fi
run media-audit
run export
run mdict
run quality
if command -v google-chrome >/dev/null && command -v libreoffice >/dev/null; then
  uv run python scripts/build_brand.py
else
  echo "Skipping images: they need Chrome and LibreOffice. The ones in the repository are used."
fi
run bundle
echo "Release ready in build/release/kaggle"
