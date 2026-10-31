#!/usr/bin/env bash
# Load the Kurdish Wiktionary SQL files into an empty PostgreSQL database.
# Usage: ./scripts/load-postgres.sh postgresql://user:pass@host:port/dbname [sql-folder] [--with-html]
set -euo pipefail

URL="${1:?Usage: load-postgres.sh <database-url> [sql-folder] [--with-html]}"
FOLDER="${2:-build/release/sql}"
OPTION="${3:-}"

psql "$URL" -v ON_ERROR_STOP=1 -q -f "$FOLDER/wiktionary_schema.sql"
gunzip -c "$FOLDER/wiktionary_data.sql.gz" | psql "$URL" -v ON_ERROR_STOP=1 -q
if [[ "$OPTION" == "--with-html" ]]; then
  gunzip -c "$FOLDER/wiktionary_section_html.sql.gz" | psql "$URL" -v ON_ERROR_STOP=1 -q
fi
psql "$URL" -c "ANALYZE" -c "SELECT COUNT(*) AS entries FROM entries"
