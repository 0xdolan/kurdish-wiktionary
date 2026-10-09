# wikitionary_to_mdx

Kurdish Wiktionary (Wîkîferheng) pipeline: Kiwix **ZIM** ingest, PostgreSQL storage, FastAPI query API, and **MDX/MDD** dictionary export via [mdict-utils](https://pypi.org/project/mdict-utils/).

## Documentation

| Document | Contents |
|----------|----------|
| [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) | Architecture, stack, API contract, acceptance criteria |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Phased tasks (0–7), verification commands, resume checklist |
| [docs/MDX_MDD_GUIDE.md](docs/MDX_MDD_GUIDE.md) | **What MDX/MDD are**, how to build/extract, CLI + planned HTTP API |

## Data

Place Kiwix files under `zim/` (e.g. `wiktionary_ku_all_nopic_2026-06.zim`). See [Kiwix wiktionary index](https://ftp.fau.de/kiwix/zim/wiktionary/).

## MDX quick reference

```bash
uv add mdict-utils

# After export staging exists (Phase 7):
mdict --title title.html --description description.html -a dict.txt wikiferheng.mdx
mdict --title title.html --description description.html -a resources/ wikiferheng.mdd
mdict -m wikiferheng.mdx
mdict -x wikiferheng.mdx -d ./extracted
```

Full steps: [docs/MDX_MDD_GUIDE.md](docs/MDX_MDD_GUIDE.md).

## Status

Implementation phases are **not started** — see [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) progress snapshot.
