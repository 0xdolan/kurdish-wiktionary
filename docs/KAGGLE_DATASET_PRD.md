# PRD: Kaggle-Ready Kurdish Wiktionary Dataset

**Document type:** Product requirements (review before implementation)  
**Status:** Superseded by the implementation in `src/dataset/`. See [DATASET_KAGGLE_GUIDE.md](./DATASET_KAGGLE_GUIDE.md) and [DATASET_LOCAL_GUIDE.md](./DATASET_LOCAL_GUIDE.md)  
**Owner:** kurdish-wiktionary maintainers  
**Last updated:** 2026-10-11  

---

## 1. Summary

Publish a **versioned, reproducible, legally clear** snapshot of Kurdish Wiktionary (Wîkîferheng) data extracted from official Kiwix ZIM dumps—not raw wiki HTML dumps—so researchers and builders can reuse **structured lemmas**, optional **section HTML**, and optional **media** on Kaggle without running this pipeline themselves.

The dataset should feel **“Kaggle-native”**: documented schema, quality metrics, fixed provenance, and file formats that load in one line in Python/R; while remaining **faithful to upstream** (attribution, share-alike, no proprietary encumbered derivatives).

---

## 2. Problem & opportunity

### 2.1 Problem

- Ku Wiktionary is valuable for NLP, lexicography, and dictionary apps, but **ZIM + PostgreSQL + custom parsers** are a high bar for reuse.
- Ad-hoc exports (JSON dumps, MDX binaries) mix **consumer formats** with **research formats** and often omit **lineage**, **quality filters**, and **license packaging**.
- Partial extracts (missing relations, failed catalog rows, undownloaded media) are easy to ship by mistake.

### 2.2 Opportunity

- This repo already produces: normalized **`entries`** + child tables, **`entry_html`**, **`entry_media`**, catalog **extract status**, and **media download** tooling.
- A **standard dataset bundle** turns that into a repeatable product: same inputs (ZIM UUIDs + git tag) → same outputs (checksums + manifest).

### 2.3 Target users

| Persona | Primary need |
|--------|----------------|
| **NLP researcher** | Lemma-level text fields (defs, POS, examples); minimal HTML noise |
| **Lexicographer / linguist** | Etymology, pronunciations, synonyms, section structure |
| **App developer** | Stable IDs, media paths/URLs, HTML sections for rendering |
| **Educator / Kaggle learner** | Small “starter” slice + notebook that loads in pandas |

---

## 3. Goals & non-goals

### 3.1 Goals

| ID | Goal |
|----|------|
| G1 | **Reproducible build**: manifest records ZIM file names/hashes, repo commit, DB migration version, row counts, and output SHA-256. |
| G2 | **Quality tiering**: explicit inclusion rules (e.g. only `extract_status = extracted` canonical lemmas with ≥1 definition). |
| G3 | **Multi-format release**: at least **Parquet** (tabular) + **JSONL** (nested per entry) + **CSV** (flat glossary view). |
| G4 | **License bundle**: `LICENSE`, `ATTRIBUTION.md`, per-file license notes for media. |
| G5 | **Completeness report**: shipped alongside data (`quality/report.json` + human-readable `QUALITY.md`). |
| G6 | **Kaggle metadata**: title, subtitle, tags, cover image, and a **Usage** section with citation block. |
| G7 | **Version semantics**: `ku-wiktionary-YYYYMMDD` or semver `1.0.0` tied to ZIM date. |

### 3.2 Non-goals (v1 dataset)

- Replacing Kiwix or hosting live Wiktionary.
- Claiming **100%** coverage of all ~1M catalog titles (only **successfully extracted** subset is in scope unless a separate “catalog-only” table is published).
- Shipping a **production MDX/MDD** as the primary Kaggle artifact (optional secondary asset in “full” tier).
- ML train/test splits (not meaningful for a dictionary corpus).
- Removing Share-Alike obligations or re-licensing upstream content.

---

## 4. Licensing & compliance (must-read)

### 4.1 Upstream

- **Wiktionary text** (definitions, etymology, wikitext-derived content): **CC BY-SA 4.0**, as stated in the footer of every page in the 2026 ZIM dumps.
- **Wikimedia Commons media** (audio/images linked from entries): **CC BY-SA / CC BY / public domain** varies **per file**; dataset must retain **source URL** and not imply a single license for all binaries.

### 4.2 Dataset packaging requirements

| Requirement | Implementation |
|-------------|------------------|
| Attribution | `ATTRIBUTION.md` + Kaggle description + optional `citation.bib` |
| Share-Alike | State SA applies to derived **database exports** of Wiktionary text; link to license |
| Media | Ship `media/LICENSE-NOTICE.md`: “each file’s license is on Commons”; include `source_url` column |
| Trademarks | No “official Wiktionary/Wikimedia” endorsement implied |
| PII | No contributor emails; strip if ever present in HTML |

### 4.3 This repository’s code

- Pipeline code: follow **repo LICENSE** (separate from dataset content).
- Kaggle dataset = **content** (CC BY-SA) + **documentation** + optional **scripts** (repo license).

**Legal review:** Maintainer should confirm license version against the exact ZIM `Date` metadata before first public release.

---

## 5. Product tiers (recommended)

Publish **one Kaggle Dataset** with **three downloadable folders** (or three dataset versions if size limits force split).

| Tier | Name | Approx. audience | Contents |
|------|------|------------------|----------|
| **T0** | `starter/` | Notebooks, demos | 5k–10k entries, all formats, tiny media sample |
| **T1** | `core/` | Most users | Full **structured fields** for extracted lemmas; **no** binary media (URLs only) |
| **T2** | `full/` | Apps, speech, vision | T1 + `media/` tree + `media_index.parquet` + optional `html/` sections |

**Size strategy:** If T2 exceeds Kaggle limits (~GB thresholds), publish T1 on Kaggle and T2 as **external mirror** linked from README with identical manifest checksums.

---

## 6. Inclusion & quality standard (“clean data” definition)

### 6.1 Lemma inclusion rules (default policy)

A lemma row is **eligible** for `core/` when **all** of:

1. Present in `entries` with `language_code = 'ku'` (or documented filter).
2. Linked canonical catalog row has `extract_status = 'extracted'` (if using canonical pipeline).
3. `definitions` count ≥ 1 (non-empty after normalization).
4. `entry` equals normalized display policy (no blank lemma).
5. Not flagged in `diagnostics/duplicates` export as erroneous duplicate **unless** retained with `quality_flags`.

**Optional stricter tier (`core-strict/`):**

- Synonyms/antonyms/examples present where template expects them (future: template-aware QA).
- `entry_html` present with non-empty `section_html` keys used by MDict renderer.
- All `entry_media` rows have non-null `local_path` **and** file exists on disk (T2 only).

### 6.2 Exclusion & quarantine

Ship a separate **`quarantine/`** (or `quality/excluded.jsonl`) listing:

- `extract_status = failed | skipped`
- Entries with zero definitions
- Media rows with unresolved URLs after download pass
- Entries failing HTML sanitize checks (if applied)

Consumers can opt in; default bundles stay clean.

### 6.3 Quality metrics (required in every release)

| Metric | Source |
|--------|--------|
| `entries_total` | `entries` count |
| `entries_included` | after inclusion rules |
| `entries_excluded` | quarantine count |
| `definitions_per_entry` | distribution stats |
| `with_synonyms_pct`, `with_audio_pct`, … | SQL aggregates |
| `media_rows_total`, `media_rows_with_local_path`, `media_files_present_on_disk` | `entry_media` + filesystem scan |
| `canonical_extracted_pct` | catalog join |
| `zim_uuid`, `zim_date`, `nopic_zim_sha256`, `maxi_zim_sha256` | ZIM metadata |

---

## 7. Data model & file formats

### 7.1 Canonical logical schema (one row per lemma)

**Primary key for consumers:** `(entry_normalized, language_code)` or stable `entry_id` (integer from DB—document immutability across versions).

| Field | Type | Source |
|-------|------|--------|
| `entry_id` | int | `entries.id` |
| `entry` | string | display title |
| `entry_normalized` | string | lookup key |
| `language_code` | string | default `ku` |
| `part_of_speech` | list[string] | child table |
| `definitions` | list[string] | ordered |
| `examples` | list[string] | ordered |
| `synonyms` | list[string] | |
| `antonyms` | list[string] | |
| `pronunciations` | list[string] | |
| `phonetic_transcriptions` | list[string] | |
| `derived_terms` | list[string] | |
| `etymology` | string \| null | |
| `metadata` | object | JSON (syllabification, etc.) |
| `zim_uuid` | string \| null | |
| `source_date` | string \| null | from ZIM |
| `extracted_at` | datetime | `entries.updated_at` |

### 7.2 Optional tables (separate files)

| File | Format | Description |
|------|--------|-------------|
| `lemmas.parquet` | Parquet | One row per lemma; list columns or JSON string per policy |
| `lemmas.jsonl` | JSONL | One `WiktionaryEntry`-compatible object per line |
| `glossary.csv` | CSV | Flat: `entry`, `pos`, `definition_1`, … (first def only for wide CSV) |
| `media.parquet` | Parquet | `entry_id`, `kind`, `url`, `local_path`, `bytes`, `source_url` |
| `html_sections.jsonl` | JSONL | `entry_id`, `section_key`, `html_fragment` (sanitized) |
| `catalog_status.parquet` | Parquet | All canonical/wordlist rows + `extract_status`, `last_error` |
| `quality/report.json` | JSON | Metrics in §6.3 |
| `manifest.json` | JSON | Build provenance (§8) |

**Format choices:**

- Prefer **Parquet** for Kaggle + pandas/polars; ** ZSTD** compression.
- **JSONL** for nested/list-heavy consumption; UTF-8, no ASCII escaping of Kurdish text.
- Avoid PostgreSQL custom dumps as the *only* format (poor Kaggle UX).

### 7.3 Media layout (T2)

Mirror repo export layout (document in README):

```text
media/{entry_normalized}/{kind}/{filename-stem}-{url-hash10}.{ext}
```

`media_index.parquet` maps `entry_id` → relative path → original Wikimedia URL.

---

## 8. Provenance manifest (required)

Every release includes **`manifest.json`** at bundle root:

```json
{
  "dataset_version": "1.0.0",
  "dataset_slug": "ku-wiktionary-structured",
  "build_timestamp_utc": "2026-10-11T12:00:00Z",
  "git_commit": "<sha>",
  "pipeline_repo": "https://github.com/0xdolan/kurdish-wiktionary",
  "zim": {
    "nopic": {"path": "...", "sha256": "...", "uuid": "...", "date": "..."},
    "maxi": {"path": "...", "sha256": "...", "uuid": "...", "date": "..."}
  },
  "database": {
    "alembic_head": "20261010_0005",
    "postgres_version": "16"
  },
  "tier": "core",
  "inclusion_policy": "default-v1",
  "row_counts": {},
  "file_checksums": {"lemmas.parquet": "sha256:..."}
}
```

Consumers can verify integrity without trusting Kaggle alone.

---

## 9. Build pipeline (operator workflow)

### 9.1 Preconditions

1. Fresh or known-good PostgreSQL populated via catalog extract + lexicon extract path documented in [RUNBOOK.md](./RUNBOOK.md).
2. Media pass complete: `media_rows_missing_local_path = 0` (T2) per [LEXICON_API.md](./LEXICON_API.md).
3. Local CI green: `./scripts/ci-local.sh`.

### 9.2 Proposed CLI (to implement)

```bash
# Dry run: counts + quality report only
uv run python -m src.dataset export --tier core --dry-run

# Write bundle
uv run python -m src.dataset export \
  --tier core \
  --output-dir build/dataset/ku-wiktionary-1.0.0 \
  --inclusion-policy default-v1

# Optional: include html + media
uv run python -m src.dataset export --tier full --output-dir ...
```

**Implementation note (current repo gap):** Today, `GET /lexicon/export` emits simplified JSON/txt without HTML/media/manifest. This PRD assumes a dedicated **`src/dataset/`** packager that reads SQL holistically (reuse `WiktionaryEntry`, `entry_html`, `entry_media`, catalog models).

### 9.3 Validation gates (fail build if)

| Gate | Condition |
|------|-----------|
| QG-1 | `entries_included` ≥ documented minimum for release (or explicit “preview” flag) |
| QG-2 | No duplicate `(entry_normalized, language_code)` in export |
| QG-3 | UTF-8 validation on all text files |
| QG-4 | `manifest.json` checksums match files on disk |
| QG-5 | T2: ≥ 99% media index paths exist (configurable threshold) |
| QG-6 | Random sample N entries re-parse from ZIM matches stored defs (optional spot-check job) |

---

## 10. Kaggle publication checklist

### 10.1 Dataset page copy

| Section | Content |
|---------|---------|
| **Title** | `Kurdish Wiktionary (ku) — Structured Lexicon from Kiwix ZIM` |
| **Subtitle** | Version, ZIM date, entry count |
| **Description** | 2–3 paragraphs + bullet list of fields |
| **License** | CC BY-SA 4.0 for text; media varies per file |
| **Tags** | `nlp`, `dictionary`, `kurdish`, `wiktionary`, `lexical-resource` |
| **Citation** | BibTeX block |

### 10.2 Files uploaded

- Entire version folder zipped **or** folder upload per Kaggle UI
- **`README.md`** (Kaggle renders this): quickstart code, schema, tier explanation
- **`DATASET_CARD.md`**: extended datasheet (see §11)
- Optional **`notebook/`**: official EDA kernel linked as “Suggested notebook”

### 10.3 Companion kernel (highly recommended)

Minimal notebook:

1. Load `manifest.json` + `lemmas.parquet`
2. Show sample entry with Kurdish text
3. Join `media.parquet` for audio example
4. Plot POS distribution / definition length histogram
5. Link back to pipeline repo for updates

---

## 11. Documentation standard (datasheet)

Follow the spirit of [Dataset Nutrition Labels / datasheets for datasets](https://arxiv.org/abs/1803.09010). Ship **`DATASET_CARD.md`** with:

1. **Motivation** — why this snapshot exists  
2. **Composition** — what’s in / out  
3. **Collection process** — ZIM → parser → SQL → export  
4. **Preprocessing** — normalization, dedupe, HTML sanitize  
5. **Uses** — intended and **misuse** (not parallel corpus, not MT gold)  
6. **Distribution** — tiers, updates, versioning  
7. **Maintenance** — contact, issue tracker, refresh cadence  

---

## 12. Versioning & updates

| Event | Version bump |
|-------|----------------|
| New ZIM dump ingested | **Minor** (e.g. 1.0 → 1.1) or date suffix |
| Schema column added (backward compatible) | **Minor** |
| Inclusion policy or primary key change | **Major** |
| Bugfix export only | **Patch** |

Maintain **`CHANGELOG.md`** in the dataset bundle and GitHub release notes.

**Kaggle:** publish new dataset version; keep old version available; link deprecation in README.

---

## 13. Success metrics

| Metric | Target (first release) |
|--------|-------------------------|
| Time to first plot in notebook | < 5 minutes |
| User-reported license clarity | No ambiguous “public domain” claims |
| Reproducibility | Independent rebuild from manifest + ZIM within documented tolerance |
| Quality transparency | 100% of exclusions explainable via `quarantine.jsonl` reason codes |

---

## 14. Implementation phases (engineering)

| Phase | Deliverable | Depends on |
|-------|-------------|------------|
| **P0** | This PRD approved | — |
| **P1** | `quality/report.json` generator (SQL + media scan) | existing DB |
| **P2** | `src.dataset export --tier core` → Parquet + JSONL + manifest | P1 |
| **P3** | Quarantine export + inclusion policies as code | P2 |
| **P4** | T2 media index + optional html bundle | media-download complete |
| **P5** | Kaggle README + notebook + first upload | P2–P4 |
| **P6** | CI job: export starter tier on release tag | P2 |

---

## 15. Open questions (decisions needed before P2)

1. **Primary key for external users:** expose stable `entry_id` only, or commit to `(entry_normalized, ku)` forever?  
2. **HTML in Kaggle:** ship sanitized fragments vs full `html_full` (size/privacy/templates)?  
3. **Catalog table:** publish full ~1M title list with status as separate “catalog” dataset?  
4. **Kaggle identity:** personal vs org account; co-branding with Kurdish language community?  
5. **Refresh cadence:** quarterly with new ZIM, or ad hoc?  

---

## 16. Acceptance criteria (PRD sign-off)

- [ ] Legal: license text approved for target ZIM date  
- [ ] Tier T0/T1/T2 defined and size estimated from current DB  
- [ ] Inclusion policy `default-v1` written as executable spec (YAML/JSON)  
- [ ] Manifest + checksum scheme agreed  
- [ ] Kaggle README outline approved  
- [ ] Decision on implementation owner and P1 start date  

---

## Appendix A — Reference commands (today’s repo)

```bash
# Corpus completeness (media)
uv run python -m src.lexicon media-download-all

# Sample structured export (API; limited — not final Kaggle bundle)
curl -s 'http://127.0.0.1:8000/lexicon/export?format=json&limit=1000' -o sample.json

# Preview one lemma with media
uv run python scripts/render-mdict-preview.py --from-db --entry heval
```

## Appendix B — Related internal docs

- [PROJECT_SPEC.md](./PROJECT_SPEC.md) — pipeline architecture  
- [LEXICON_API.md](./LEXICON_API.md) — extract, media, diagnostics  
- [RAW_TEXT_PIPELINE.md](./RAW_TEXT_PIPELINE.md) — catalog / plain-text path  
- [MDX_ENTRY_FORMAT.md](./MDX_ENTRY_FORMAT.md) — HTML section keys (renderer contract)  
