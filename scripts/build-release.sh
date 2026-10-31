#!/usr/bin/env bash
# Build the whole release from the ZIM files. Stages are safe to rerun.
# Usage: ./scripts/build-release.sh [--skip-download]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

run() { uv run python -m src.dataset "$@"; }

run parse
run media-extract
if [[ "${1:-}" != "--skip-download" ]]; then
  run media-download
  run media-licences
fi
run media-audit
run export
run mdict
run quality
uv run python scripts/build_brand.py
run bundle
echo "Release ready in build/release/kaggle"
