"""Map extracted section HTML media URLs to local MDict preview hrefs."""

from __future__ import annotations

from src.mdict.illustration_media import media_path_fingerprint


def build_media_href_lookup(media_items: list[dict]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for item in media_items:
        if not isinstance(item, dict):
            continue
        if item.get("kind") not in {"audio", "image"}:
            continue
        href = str(item.get("href", "")).strip()
        if not href:
            continue
        _register_lookup_keys(lookup, href, href)
        source_url = str(item.get("source_url") or "").strip()
        if source_url:
            _register_lookup_keys(lookup, source_url, href)
    return lookup


def _register_lookup_keys(lookup: dict[str, str], key_path: str, href: str) -> None:
    base = key_path.rsplit("/", maxsplit=1)[-1]
    lookup[base] = href
    lookup[media_path_fingerprint(key_path)] = href
    if "." in base:
        lookup[base.rsplit(".", maxsplit=1)[0]] = href


def resolve_media_href(file_ref: str, lookup: dict[str, str]) -> str | None:
    base = file_ref.rsplit("/", maxsplit=1)[-1]
    for candidate in (base, media_path_fingerprint(file_ref), file_ref):
        hit = lookup.get(candidate)
        if hit:
            return hit
    return None
