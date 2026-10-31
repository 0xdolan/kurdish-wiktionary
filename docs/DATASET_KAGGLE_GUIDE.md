# Kurdish Wiktionary dataset: Kaggle guide

For people publishing the dataset and for people using it on Kaggle.

## Publish

### 1. Build and check

```bash
./scripts/build-release.sh
uv run python -m src.dataset media-audit
```

Before uploading, read `build/release/quality/QUALITY.md`. Then confirm:

- [ ] Audio missing is at a level you accept, and the README's numbers match
- [ ] `build/release/kaggle/dataset-metadata.json` has the id `zeroxdolan/wiktionary-wordlists`
- [ ] You have checked the name and logo against the [Wikimedia trademark policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_Trademark_Policy). Ask trademarks@wikimedia.org if unsure
- [ ] The slug and title are the ones you want. Kaggle URLs are hard to change later
- [ ] Unknown-licence media is acceptable to you, or removed (see "Media licences" below)

### 2. Kaggle token

Create one on Kaggle under **Settings > API** if `~/.kaggle/` doesn't already have it. Don't commit it.

### 3. Upload

The release updates the existing dataset [zeroxdolan/wiktionary-wordlists](https://www.kaggle.com/datasets/zeroxdolan/wiktionary-wordlists).

```bash
./scripts/publish-kaggle.sh "Kurdish Wiktionary 1.0.0: full structured release"
```

This uploads a new version, then applies the title, description, licence, tags and cover from `dataset-metadata.json`. The flags it uses matter:

| Flag | Why |
|---|---|
| `-t` | Keeps Parquet and Excel as they are. Without it, Kaggle converts tabular files to CSV |
| `-r zip` | Uploads the folders. Without it, folders are skipped and only top-level files go up |

Earlier versions stay in the version history, because the script doesn't use `--delete-old-versions`. Large uploads can take hours and may need retrying.

### 4. Finish on the Kaggle page

Check the result on Kaggle, then:

| Item | What to do |
|---|---|
| URL | The API can't change it. To rename `wiktionary-wordlists`, use the dataset's settings page, then update `DATASET_SLUG` in `src/dataset/bundle.py` and `KAGGLE_URL` in `scripts/build_brand.py` |
| Cover image | Sent with the metadata. If it doesn't appear, upload `assets/brand/export/kaggle-cover-dark.png` by hand |
| Notebook | Create a notebook, add this dataset, import `assets/kaggle/kurdish_wiktionary_starter.ipynb`, run it and save a version |

### 5. Later versions

```bash
./scripts/finish-release.sh
./scripts/publish-kaggle.sh "Update to the 2027-01 dump"
```

Update `DATASET_VERSION` and `assets/dataset/CHANGELOG.md` first. Keep column names stable: people's notebooks depend on them.

## Use on Kaggle

Add the dataset to a notebook. Files appear under `/kaggle/input/wiktionary-wordlists/`. Folders uploaded as archives may be unpacked with slightly different nesting, so search rather than hard-coding paths:

```python
import glob
import pandas as pd

find = lambda name: glob.glob(f"/kaggle/input/**/{name}", recursive=True)[0]

entries = pd.read_parquet(find("entries.parquet"))
senses = pd.read_parquet(find("senses.parquet"))
```

### Save memory

The biggest tables won't fit comfortably in a small notebook. Read only the columns you need, or filter while reading:

```python
senses = pd.read_parquet(find("senses.parquet"), columns=["entry_id", "pos", "definition"])

import pyarrow.parquet as pq
kurmanci = pq.read_table(find("entries.parquet"), filters=[("language_code", "=", "ku")]).to_pandas()
```

DuckDB can query Parquet directly without loading it, if you `pip install duckdb`:

```python
import duckdb
duckdb.sql(f"""
    SELECT e.title, s.definition
    FROM '{find("senses.parquet")}' s JOIN '{find("entries.parquet")}' e USING (entry_id)
    WHERE e.language_code = 'ckb' LIMIT 10
""").df()
```

### Query SQLite

```python
import sqlite3
database = find("wiktionary.sqlite")
conn = sqlite3.connect(f"file:{database}?mode=ro", uri=True)  # /kaggle/input is read-only
pd.read_sql_query("SELECT language_code, COUNT(*) AS n FROM entries GROUP BY 1 ORDER BY n DESC LIMIT 10", conn)
```

### Play audio

```python
import tempfile, zipfile
from IPython.display import Audio

media = pd.read_parquet(find("media.parquet"))
clip = media[(media.kind == "audio") & (media.status == "present")].iloc[0]
with zipfile.ZipFile(find("audio.zip")) as bundle:
    path = bundle.extract(clip.local_path, tempfile.mkdtemp())
Audio(path)
```

### Ideas to build

- A Kurmancî spell checker or lemmatizer from `inflection_forms`
- Kurmancî to Soranî, or Kurdish to English, word lists from `translations`
- Pronunciation models from `pronunciations` and `audio.zip` (mostly English, German and French; Kurmancî is a small share)
- A study of Kurmancî literary vocabulary by century from `quotations`
- A Kurdish WordNet seed from `relations`

For any model, start with `is_auto_generated == 0 and definition_pending == 0`, and read `QUALITY.md`.

## Media licences

Text is one licence (CC BY-SA 4.0). Media is per file, so the dataset licence field can't cover it, and the README says so. Three things to check before making the dataset public:

1. Audio from Commons has licence and author per file, matched by file name. Every recording has one. Most are CC BY-SA or CC0.
2. ZIM images have hashed names, so the pipeline matches them by page and original dimensions (`license_match = 'by_dimensions'`). These are likely right but not certain.
3. Files with an empty `license` have no confirmed licence: about 540 small files (hieroglyphs, icons, 87 illustrations). If you want a strictly clean release, exclude them from `images.zip` and the `.mdd`.
4. The first audit found no non-commercial, no-derivatives or fair-use licences. It did find 2 euro banknote photos under European Central Bank reproduction rules (`Euro-Banknoten.jpg`, `Euro_Banknotes.jpg`), which you may want to exclude. Recheck `QUALITY.md`, which lists every licence, for each new dump.

This guide isn't legal advice. If the release matters commercially, have someone qualified review it.

## Troubleshooting

| Problem | Fix |
|---|---|
| `401` from the CLI | Create a new token, and check `~/.kaggle/kaggle.json` permissions |
| Parquet files arrive as CSV | You uploaded without `-t` |
| Only top-level files appear | You uploaded without `-r zip` |
| Slug rejected | Slugs need 6 to 50 characters: lowercase letters, digits and hyphens |
| Notebook runs out of memory | Use `columns=`, filters or DuckDB, as above |
