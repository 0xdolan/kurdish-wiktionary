# MDict assets

| Path | Purpose |
|------|---------|
| `css/wiktionary.css` | Shared entry stylesheet (packed into MDD) |
| `img/volume-up.png` | Pronunciation speaker button icon (MDD) |
| `fonts/sahel/` | [Sahel v3.4.0](https://github.com/rastikerdar/sahel-font) (Arabic-script / RTL text) |
| `preview/heval.html` | Real SQL preview (Kurdish **heval**, audio + images) |
| `preview/brave.html` | English demo (`--demo`) |
| `preview/media/` | Media copied from `build/media/` for offline preview |
| `samples/sample.dict.txt` | Minimal dict.txt snippet (article + `@@@LINK`) |
| `templates/` | `title.html` / `description.html` for mdict-utils pack |

Documentation: [docs/MDX_ENTRY_FORMAT.md](../../docs/MDX_ENTRY_FORMAT.md).

```bash
uv run python scripts/render-mdict-preview.py
./scripts/pack-mdict-sample.sh
```
