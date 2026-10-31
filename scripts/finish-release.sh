#!/usr/bin/env bash
# Finish a release after media-extract: resume the download, then rebuild every output.
# Safe to rerun at any time. Nothing is uploaded.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if pgrep -f "src.dataset media-download" >/dev/null; then
  echo "A media download is already running. Wait for it to finish, or stop it, then rerun this." >&2
  exit 1
fi

run() { uv run python -m src.dataset "$@"; }

run media-download
run media-licences
run media-audit
run export
run mdict
run quality
# Before the bundle: the Kaggle cover shows the final numbers.
uv run python scripts/build_brand.py
run bundle
echo "Release ready in build/release/kaggle. Check build/release/quality/QUALITY.md before uploading."
