# MDict entry format (dict.txt rules)

**Goal:** One reusable HTML pattern for every extracted `WiktionaryEntry`, serialized as UTF-8 `dict.txt`, packed to `.mdx` + `.mdd` via **mdict-utils** — no separate frontend build.

**Visual reference (real SQL data):** [`assets/mdict/preview/heval.html`](../assets/mdict/preview/heval.html) — lemma **heval** with definitions, Wikimedia audio, and ZIM images.

```bash
# 1) Download media (needs Postgres + ZIM on disk)
export DATABASE_URL='postgresql+asyncpg://wiktionary:wiktionary@127.0.0.1:5434/wiktionary'
export ZIM_PATHS='zim/wiktionary/wiktionary_ku_all_nopic_2026-06.zim,zim/wiktionary/wiktionary_ku_all_maxi_2026-08.zim'
uv run python -m src.lexicon media-download heval --confirm

# 2) Regenerate preview HTML + copy media into assets/mdict/preview/media/
uv run python scripts/render-mdict-preview.py --from-db --entry heval
```

English demo only: `uv run python scripts/render-mdict-preview.py --demo` → `assets/mdict/preview/brave.html`.

**Pipeline overview:** [MDX_MDD_GUIDE.md](./MDX_MDD_GUIDE.md).

---

## Rephrased product spec

| Requirement | Implementation |
|-------------|----------------|
| Search key is the **lemma** (what users type in MDict / BlueDict / GoldenDict) | First line of each record = headword (NFC, no embedded newlines) |
| Article body is **HTML** (not a Node app) | `src/mdict/renderer.py` → fragment; shared CSS in MDD |
| Show the **headword again** in the view (lookup does not repeat the key) | `<h1 class="wikt-headword">…</h1>` inside the article |
| Definitions, IPA, POS, examples, synonyms, antonyms, etymology, derived, conjugation | Renderer sections; conjugation from `metadata.conjugation` or `metadata.conjugation_html` |
| Cross-links to other lemmas | `<a href="entry://{headword}">label</a>` |
| Same lemma, duplicate key (variant title) | `@@@LINK=canonical_headword` record |
| UTF-8 end-to-end | `write_dict_txt(..., encoding="utf-8")` |
| Pack | `uv run python -m src.mdict.export` or `mdict --title … -a dict.txt out.mdx` |

---

## Record grammar

Each dictionary **record** is a block in `dict.txt`:

```text
{HEADWORD}
{HTML lines — typically stylesheet link + <article>…</article>}
</>
```

- **`HEADWORD`:** Index key. Must match Wiktionary title / `WiktionaryEntry.entry` (normalized for search).
- **`</>`:** End-of-record marker on its own line (MDict / mdict-utils convention).
- **Blank lines:** Avoid extra blank lines inside HTML unless intentional; one record after another.

### Full article (normal entry)

```text
brave
<link rel="stylesheet" type="text/css" href="css/wiktionary.css" />
<article class="wikt-entry">…</article>
</>
```

Stylesheet path is **relative to MDD root**. The exporter copies `assets/mdict/css/wiktionary.css` → `staging/resources/css/wiktionary.css` and packs MDD beside MDX.

**CSS rule:** first line of the `.css` file must be blank (MDict builder quirk) — already set in repo CSS.

### Redirect / alias (`@@@LINK`)

When two keys should show the same article (inflected form, spelling variant, duplicate title):

```text
braver
@@@LINK=brave
</>
```

Lookup **`braver`** opens the article stored under **`brave`**. No HTML body.

Python helper: `format_txt_link_record("braver", "brave")` in `src/mdict/txt_writer.py`.

Optional batch append: `write_dict_txt(entries, path, link_aliases=[("braver", "brave"), …])`.

### In-article cross-reference

Display text can differ from target headword:

```html
<a class="wikt-xref" href="entry://courageous">courageous</a>
```

Helper: `render_cross_reference("courageous", "courageous")`.

### Media (MDD)

| Asset | HTML pattern |
|-------|----------------|
| Image | `<img src="img/example.png" alt="…" />` |
| Audio | `<audio controls src="audio/word.opus"></audio>` or MDict `sound://` where supported |

Paths must exist under the MDD resource tree staged by `stage_resource_tree()`.

---

## Code map

| Piece | Path |
|-------|------|
| HTML template | `src/mdict/renderer.py` |
| dict.txt serialization | `src/mdict/txt_writer.py` |
| Stylesheet (MDD) | `assets/mdict/css/wiktionary.css` |
| Preview (browser) | `assets/mdict/preview/brave.html` |
| Sample txt | `assets/mdict/samples/sample.dict.txt` |
| Pack orchestration | `src/mdict/export.py`, `src/mdict/pack.py` |
| CLI export | `uv run python -m src.mdict.export --data-source sql --limit 1000` |
| Sample pack script | `scripts/pack-mdict-sample.sh` |

---

## Operator workflow

1. **Preview design** — `uv run python scripts/render-mdict-preview.py` → open `assets/mdict/preview/brave.html`.
2. **Export SQL → dict.txt** — `uv run python -m src.mdict.export --data-source sql --output-dir build/mdict --limit 50000`.
3. **Verify staging** — `build/mdict/staging/dict.txt` (UTF-8), `build/mdict/staging/resources/css/wiktionary.css`.
4. **Smoke pack sample** — `./scripts/pack-mdict-sample.sh` → `build/mdict/sample/sample.mdx`.
5. **Full corpus** — raise `--limit` or add pagination; keep MDX + MDD basenames aligned (e.g. `wikiferheng.mdx` / `wikiferheng.mdd`).

---

## Renderer inputs (`WiktionaryEntry`)

| Field | Section |
|-------|---------|
| `entry` | Headword + `<h1>` |
| `part_of_speech` | POS badges |
| `phonetic_transcriptions`, `pronunciations` | IPA / pronunciation chips |
| `definitions` | Numbered list |
| `examples` | Quoted blocks |
| `synonyms`, `antonyms`, `derived_terms` | `entry://` chip links |
| `etymology` | Etymology panel |
| `metadata.conjugation` | Table (list of rows) |
| `metadata.conjugation_html` | Raw HTML table (trusted pipeline HTML only) |

Future parser fields (inflection tables, Kurdish morphology) can map into `metadata` without changing MDict block syntax.

---

## Compatibility notes

- **MDict 2.0** write path via mdict-utils (see MDX_MDD_GUIDE).
- **WebView / IE legacy:** Prefer widely supported CSS; test in target MDict build. Avoid CSS that depends on a Node build step.
- **GoldenDict:** Same `entry://` and `</>` conventions; forum reference: [Creating Mdict dictionaries](https://goldendict.org/forum/viewtopic.php?f=4&t=6980) (Wayback captures available).

---

## Acceptance checklist

- [ ] Preview HTML matches exported fragment for the same `WiktionaryEntry`
- [ ] Every record: line 1 = headword, last line = `</>`, UTF-8
- [ ] Stylesheet link present in each full article
- [ ] MDD contains `css/wiktionary.css` with leading blank line
- [ ] `mdict -m` / `mdict -k` succeed on packed sample
- [ ] `@@@LINK` records resolve in MDict/GoldenDict smoke test
