#!/usr/bin/env bash
# Sahel (SIL OFL) — Arabic/Persian script UI font for MDict entries.
# https://github.com/rastikerdar/sahel-font/releases/tag/v3.4.0
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/assets/mdict/fonts/sahel"
ZIP="$(mktemp)"
trap 'rm -f "$ZIP"' EXIT
curl -fsSL -o "$ZIP" \
  "https://github.com/rastikerdar/sahel-font/releases/download/v3.4.0/sahel-font-v3.4.0.zip"
mkdir -p "$DEST"
unzip -j -o "$ZIP" \
  "Without-Latin/Sahel-WOL.woff2" \
  "Without-Latin/Sahel-Bold-WOL.woff2" \
  "Without-Latin/Sahel-SemiBold-WOL.woff2" \
  "LICENSE" \
  -d "$DEST"
mv -f "$DEST/LICENSE" "$DEST/LICENSE.sahel"
echo "Installed Sahel woff2 files under $DEST"
