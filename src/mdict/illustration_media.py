"""Images for the Wêne fold: wiki illustration assets only (not Werger/Tewandin clutter)."""

from __future__ import annotations

from src.extraction.media_urls import extract_media_from_html

_ILLUSTRATION_KEYS = frozenset({"wêne", "wene"})
# ku.wiktionary often places the lede thumb under Navdêr (no separate Wêne heading).
_LEDE_ILLUSTRATION_SECTIONS = frozenset({"navder", "bilevkirin"})


def _normalize_section_key(key: str) -> str:
    return (
        key.casefold()
        .replace("î", "i")
        .replace("ê", "e")
        .replace("û", "u")
        .replace("ş", "s")
    )


def illustration_section_html(section_html: dict[str, str]) -> str:
    for key, fragment in section_html.items():
        if key in _ILLUSTRATION_KEYS or _normalize_section_key(key) == "wene":
            return fragment
    return ""


def media_path_fingerprint(path: str) -> str:
    """Match ZIM ``_assets_/…/file.ext`` to exported ``file-digest.ext``."""
    base = path.rsplit("/", 1)[-1]
    stem = base.rsplit(".", 1)[0] if "." in base else base
    if "-" in stem:
        suffix = stem.rsplit("-", 1)[-1]
        if len(suffix) <= 16 and all(c in "0123456789abcdef" for c in suffix.casefold()):
            stem = stem.rsplit("-", 1)[0]
    return stem.casefold()


def _fingerprints_from_html(html: str) -> set[str]:
    out: set[str] = set()
    for item in extract_media_from_html(html):
        if item.get("kind") == "image":
            out.add(media_path_fingerprint(str(item.get("url", ""))))
    return out


def illustration_media_fingerprints(section_html: dict[str, str]) -> set[str]:
    dedicated = illustration_section_html(section_html)
    if dedicated.strip():
        return _fingerprints_from_html(dedicated)
    out: set[str] = set()
    for key, fragment in section_html.items():
        norm = _normalize_section_key(key)
        if norm in _LEDE_ILLUSTRATION_SECTIONS:
            out |= _fingerprints_from_html(fragment)
    return out
