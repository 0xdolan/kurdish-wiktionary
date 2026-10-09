# Wîkîferheng HTML layout notes (Phase 1.2)

**Corpus:** `zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim`  
**Sample lemmas:** `heval`, `roj`, `bira`, `water`, `کورد`

## Top-level structure

- Content lives in `.mw-parser-output` (`lang="ku"`, often `dir="ltr"`).
- Language variety blocks use **`h2`** with label in `span` (e.g. **Kurmancî**, **Soranî**, **Afrîkansî**).
- Subsections use **`h3`** / **`h4`** (pronunciation, POS, etymology, derived forms).

## Fields mapped by the parser (`layout_version: ku-mw-2026-v1`)

| Field | DOM hints |
|-------|-----------|
| `part_of_speech` | `h3`/`h4` labels such as **Navdêr**, **Peyv**, **Rengdêr** |
| `definitions` | Items in `ol > li` under the article body |
| `phonetic_transcriptions` | `span.IPA` |
| `pronunciations` | Links to `.mp3`, `.wav`, `.ogg`, `.opus` (incl. Phonos buttons) |
| `examples` | `.benimune`, `blockquote`, `.example` (stub “add example” lines filtered) |
| `etymology` | First `h3` whose title matches etymology keywords; following `p` / `dl` text |
| `synonyms` / `antonyms` / `derived_terms` | Reserved for section headings (Beranber, Zîv, Jê); extend as corpus grows |

## Variation / gaps

- Many pages are **multi-language** (several `h2` blocks); v1 parser **merges** lists across the page.
- Redirect pages and MediaWiki namespaces are **skipped** at ZIM iteration (`:` in title).
- Entries with only templates and no `ol`/IPA may be counted as **skipped** in the pipeline.
- Kurdish section titles use diacritics; matching uses normalized heading keys in code.

## When layout changes

1. Add a frozen HTML fixture under `tests/fixtures/html/`.
2. Bump `LAYOUT_VERSION` in `src/extraction/html_parser.py`.
3. Document the delta in this file.
