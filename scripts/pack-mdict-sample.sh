#!/usr/bin/env bash
# Pack a tiny dict.txt + CSS into sample MDX/MDD under build/mdict/sample/
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

OUT="${ROOT}/build/mdict/sample"
STAGING="${OUT}/staging"
RES="${STAGING}/resources"
mkdir -p "$RES/css"

cp assets/mdict/css/wiktionary.css "$RES/css/wiktionary.css"
cp assets/mdict/templates/title.html "$STAGING/title.html"
cp assets/mdict/templates/description.html "$STAGING/description.html"

uv run python - <<'PY'
from pathlib import Path
from src.mdict.renderer import sample_brave_entry
from src.mdict.txt_writer import format_txt_link_record, format_txt_record, write_dict_txt

out = Path("build/mdict/sample/staging/dict.txt")
write_dict_txt(
    [sample_brave_entry()],
    out,
    link_aliases=[("braver", "brave")],
)
print(f"Wrote {out}")
PY

uv run python -m mdict_utils \
  --title "$STAGING/title.html" \
  --description "$STAGING/description.html" \
  -a "$STAGING/dict.txt" \
  "$OUT/sample.mdx"

uv run python -m mdict_utils \
  --title "$STAGING/title.html" \
  --description "$STAGING/description.html" \
  -a "$RES" \
  "$OUT/sample.mdd"

echo "Packed: $OUT/sample.mdx and $OUT/sample.mdd"
uv run python -m mdict_utils -m "$OUT/sample.mdx"
