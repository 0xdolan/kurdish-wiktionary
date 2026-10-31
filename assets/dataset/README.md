# {{title}}

**Every word in the Kurdish Wiktionary, structured the way the wiki is: ready for pandas, SQL, Excel and offline dictionary apps.**

This dataset turns the {{zim_date}} snapshot of [Wîkîferheng](https://ku.wiktionary.org), the Kurdish-language Wiktionary, into clean tables, one for each kind of section an entry can have.

| | |
|---|---:|
| Pages | {{pages}} |
| Entries (page + language) | {{entries}} |
| Language codes | {{languages}} |
| Kurmancî entries | {{kurmanci_entries}} ({{kurmanci_headwords}} headwords with a definition, the rest mostly inflected forms) |
| Soranî entries | {{sorani_entries}} |
| Definitions | {{senses}} |
| Translations | {{translations}} |
| Word relations (synonyms, derived terms, ...) | {{relations}} |
| Inflected forms in tables | {{inflection_forms}} |
| Pronunciation rows (IPA, audio, syllables) | {{pronunciations}} |
| Etymologies | {{etymologies}} |
| Audio recordings included | {{audio_files}} |
| Images included | {{image_files}} |

## Start in one minute

```python
import pandas as pd

entries = pd.read_parquet("parquet/entries.parquet")
senses = pd.read_parquet("parquet/senses.parquet")

kurmanci = entries[entries.language_code == "ku"]
kurmanci.merge(senses, on="entry_id").query("title == 'heval'")[["pos", "definition"]]
```

Open `notebooks/kurdish_wiktionary_starter.ipynb` for lookups, audio playback, charts and SQL.

## How the data is organized

The wiki nests each page as **page > language > part of speech > subsection**. So does the data: `pages` > `entries` > `sections`, with a typed table for each section type.

| Wiki section | Kurmancî heading | Table |
|---|---|---|
| Part of speech, definitions | Navdêr, Lêker, Rengdêr, ... | `headwords`, `senses` |
| Examples | (inside a definition) | `examples` |
| Literary citations | Ji wêjeyê, Ji wêjeya klasîk | `quotations` |
| Pronunciation | Bilêvkirin | `pronunciations` |
| Etymology | Etîmolojî | `etymologies` |
| Translations | Werger | `translations` |
| Declension, conjugation | Tewandin | `inflection_tables`, `inflection_forms` |
| Synonyms, antonyms, derived terms, other scripts, ... | Hevmane, Dijmane, Jê, Bi alfabeyên din, ... | `relations` |
| References | Çavkanî | `reference_notes` |
| Every section, as text | all | `sections` |
| Every section, as HTML | all | `section_html` |
| Audio and images | | `media`, `media_usages` |

`DATA_DICTIONARY.md` documents every column. Join on `entry_id`. To match words **across releases**, use `entry_key` (`title|language_code`), because numeric ids are rebuilt each time.

## Formats

| Folder | Contents | Best for |
|---|---|---|
| `parquet/` | Every table, zstd-compressed | pandas, Polars, DuckDB, R |
| `csv/` | Every table except `section_html` (UTF-8 with BOM) | Quick inspection, any tool |
| `jsonl/entries.jsonl.gz` | One nested object per entry | NLP pipelines |
| `excel/` | One workbook per table, plus ready-to-read Kurmancî and Soranî dictionaries | Excel, LibreOffice. Start with `00_START_HERE_overview.xlsx` |
| `sql/wiktionary.sqlite` | The whole dataset as one file | SQL without a server |
| `sql/*.sql*` | Schema and data for PostgreSQL or SQLite | Loading into your own database |
| `mdict/` | `wiktionary.mdx`, `wiktionary.mdd`, `wiktionary.1.mdd`, `dict.txt.gz` | GoldenDict, MDict, or your own dictionary build. Light and dark themes |
| `samples/dict_sample.txt` | 200 records of the dictionary source | Seeing the format without a large download |
| `media/` | `audio.zip`, `images.zip` | Speech and image work |

Excel limits: a sheet holds about a million rows and a cell 32,767 characters. Large tables therefore span sheets and `.partNN` files, and over-long cells end with `…`. The Excel `inflection_forms` workbook leaves out bot-made inflected-form pages. Other formats are complete.

## Know the limits

- **{{auto_pct}}% of entries ({{auto_count}}) are bot-made.** The wiki marks them as generated from translation tables and warns of possible errors. Filter with `is_auto_generated == 0`. Bots may have made other pages without leaving that marker.
- **Most entries are not Kurdish.** Wîkîferheng describes words of many languages in Kurdish. Filter on `language_code` (`ku` Kurmancî, `ckb` Soranî).
- **Many entries are thin**: a one-line gloss, a stock phrase such as "Paşnavek e." (a surname), or an inflected form (`pos` ending in `_form`).
- **{{pending_count}} entries have no definition yet.** The wiki says "the meaning is not written yet" on them (`definition_pending == 1`).
- **Recordings are mostly not Kurdish.** {{audio_top}}, against {{audio_kurmanci}} for Kurmancî. Check `pronunciations` joined to `entries` before planning speech work.
- **Extraction is heuristic.** The wiki is written by hand, so expect some oddities. Unrecognized headings stay available as `section_type = 'other'`. `QUALITY.md` has the numbers.
- **Not a parallel corpus or a translation gold standard.** Definitions and translations are community-written and unreviewed.
- **Sources:** pages come from the {{zim_date}} ZIM dump. Pages found only in the older {{zim_older_date}} dump are kept with `in_latest_dump = 0`.

## Licence

- **Text:** [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), by the contributors of Wîkîferheng. You must give credit and share adaptations under the same licence.
- **Media:** licences differ per file. See `license`, `artist` and `description_url` in the `media` table. An empty `license` means none could be confirmed, so check the source before reusing that file.

See `ATTRIBUTION.md` for how to credit, and `CITATION.cff` to cite.

This is an independent community project. It is not produced or endorsed by the Wikimedia Foundation or the Wîkîferheng community. Wiktionary is a trademark of the Wikimedia Foundation.

## About earlier versions

This dataset used to hold 2023 wordlists for Kurdish, Chinese, Japanese, French and Persian. They remain available from version 1 in the version history.

## Provenance and updates

`manifest.json` records the source ZIM hashes, pipeline commit, row counts and a SHA-256 for every file. To rebuild or update: [github.com/0xdolan/wiktionary_to_mdx](https://github.com/0xdolan/wiktionary_to_mdx).

Found a problem? Open an issue there. Corrections to a word belong on [Wîkîferheng](https://ku.wiktionary.org), where everyone benefits, and reach this dataset with the next release.
