#!/usr/bin/env bash
# Upload build/release/kaggle as a new version of the existing Kaggle dataset, then apply its
# metadata (title, description, licence, tags). Earlier versions stay available.
# Usage: ./scripts/publish-kaggle.sh "version message"
# Needs a Kaggle token in ~/.kaggle/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FOLDER="$ROOT/build/release/kaggle"
MESSAGE="${1:?Give a version message}"

[[ -f "$FOLDER/dataset-metadata.json" ]] || { echo "Run: uv run python -m src.dataset bundle" >&2; exit 1; }

# -t keeps Parquet and Excel as they are (Kaggle converts tabular files to CSV otherwise).
# -r zip uploads folders, which are skipped by default.
# --with six: the Kaggle CLI imports it without declaring it as a dependency.
uvx --with six kaggle datasets version -p "$FOLDER" -t -r zip -m "$MESSAGE"
ID="$(uv run python -c "import json,sys; print(json.load(open(sys.argv[1]))['id'])" "$FOLDER/dataset-metadata.json")"
uvx --with six kaggle datasets metadata --update -p "$FOLDER" "$ID"
