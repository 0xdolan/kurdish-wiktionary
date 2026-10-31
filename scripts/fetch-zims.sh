#!/usr/bin/env bash
# Download the exact ZIM files this release was built from, and check their hashes.
# Safe to rerun: finished files are checked, not downloaded again; partial ones resume.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$ROOT/zim/wiktionary"
BASE="https://download.kiwix.org/zim/wiktionary"

FILES=(
  "wiktionary_ku_all_maxi_2026-08.zim 8534326d9d89e59274d946458460cef4106dee8bd80d532dd1e4bc0e9710f03a"
  "wiktionary_ku_all_nopic_2026-06.zim 26f820ae99bc560d1b873bcf7bab295ca8d3865798eb41f0819460e8a8b5eb13"
)

mkdir -p "$DEST"
for item in "${FILES[@]}"; do
  read -r name hash <<<"$item"
  target="$DEST/$name"
  if [[ -f "$target" ]] && echo "$hash  $target" | sha256sum --check --status; then
    echo "OK, already here: $name"
    continue
  fi
  echo "Downloading $name"
  if ! curl --fail --location --continue-at - --retry 5 --output "$target" "$BASE/$name"; then
    echo "Could not download $name. Kiwix removes old dumps after a while: see" >&2
    echo "'If the exact ZIMs are gone' in docs/REPRODUCE.md." >&2
    exit 1
  fi
  if ! echo "$hash  $target" | sha256sum --check --status; then
    echo "Hash mismatch for $name. Delete the file and rerun." >&2
    exit 1
  fi
  echo "OK: $name"
done
