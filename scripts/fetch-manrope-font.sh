#!/usr/bin/env bash
# Manrope (OFL) — Latin UI font for MDict entries.
# https://fonts.google.com/specimen/Manrope
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/assets/mdict/fonts/manrope"
VER="5.2.6"
BASE="https://cdn.jsdelivr.net/npm/@fontsource/manrope@${VER}/files"
mkdir -p "$DEST"
for w in 400 500 600 700; do
  curl -fsSL -o "$DEST/manrope-latin-${w}.woff2" \
    "$BASE/manrope-latin-${w}-normal.woff2"
  curl -fsSL -o "$DEST/manrope-latin-ext-${w}.woff2" \
    "$BASE/manrope-latin-ext-${w}-normal.woff2"
done
curl -fsSL -o "$DEST/OFL.txt" \
  "https://raw.githubusercontent.com/google/fonts/main/ofl/manrope/OFL.txt"
echo "Installed Manrope woff2 files under $DEST"
