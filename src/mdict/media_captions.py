"""Map image URLs/paths to Wiktionary thumb captions."""

from __future__ import annotations

from pathlib import PurePosixPath

from selectolax.lexbor import LexborHTMLParser


def register_image_caption(captions: dict[str, str], src: str, caption: str) -> None:
    """Add lookup keys for one image ``src`` (full path, basename, stem)."""
    src = src.strip()
    text = caption.strip()
    if not src or not text:
        return
    captions[src] = text
    basename = src.rsplit("/", 1)[-1]
    captions[basename] = text
    stem = PurePosixPath(basename).stem
    if stem:
        captions[stem] = text


def lookup_image_caption(
    captions: dict[str, str],
    *,
    url: str | None,
    local_href: str,
) -> str | None:
    """Resolve caption for a DB media row (ZIM ``url`` vs hashed ``local_path``)."""
    candidates: list[str] = []
    if url:
        candidates.append(url.strip())
        base = url.rsplit("/", 1)[-1]
        candidates.append(base)
        candidates.append(PurePosixPath(base).stem)
    rel_base = local_href.rsplit("/", 1)[-1]
    candidates.append(rel_base)
    rel_stem = PurePosixPath(rel_base).stem
    candidates.append(rel_stem)
    if "-" in rel_stem:
        candidates.append(rel_stem.rsplit("-", 1)[0])
    for key in candidates:
        if key and key in captions:
            return captions[key]
    return None


def image_captions_from_html(html: str) -> dict[str, str]:
    """Return lookup keys (basename and full src) → caption text."""
    captions: dict[str, str] = {}
    tree = LexborHTMLParser(html)
    for thumb in tree.css("div.thumb, figure.thumb, figure"):
        cap_node = thumb.css_first(".thumbcaption") or thumb.css_first("figcaption")
        caption = cap_node.text(strip=True) if cap_node else ""
        if not caption:
            continue
        for img in thumb.css("img"):
            src = (img.attributes.get("src") or "").strip()
            if not src:
                continue
            register_image_caption(captions, src, caption)
    return captions
