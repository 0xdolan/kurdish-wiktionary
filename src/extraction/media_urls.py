import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser

_AUDIO_EXT = (".mp3", ".ogg", ".wav", ".opus", ".oga", ".flac")
_IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")


def _media_kind(url: str) -> str:
    lower = url.lower().split("?", 1)[0]
    if any(lower.endswith(ext) for ext in _AUDIO_EXT):
        return "audio"
    if any(lower.endswith(ext) for ext in _IMAGE_EXT):
        return "image"
    if "Special:FilePath" in url or "/wiki/File:" in url:
        return "image"
    return "other"


def _normalize_media_url(href: str) -> str:
    href = href.strip()
    if href.startswith("//"):
        return f"https:{href}"
    return href


def extract_media_from_html(html: str) -> list[dict[str, Any]]:
    tree = LexborHTMLParser(html)
    seen: set[str] = set()
    items: list[dict[str, Any]] = []

    for node in tree.css("a, audio, video, source, img"):
        candidates: list[str] = []
        tag = node.tag
        if tag == "img":
            src = node.attributes.get("src", "")
            if src:
                candidates.append(src)
        else:
            href = node.attributes.get("href") or node.attributes.get("src", "")
            if href:
                candidates.append(href)

        for raw in candidates:
            url = _normalize_media_url(raw)
            if not url or url.startswith("#"):
                continue
            if url in seen:
                continue
            seen.add(url)
            kind = _media_kind(url)
            wikimedia = re.search(r"upload\.wikimedia|/wikipedia/commons", url, re.I)
            if kind == "other" and not wikimedia:
                continue
            items.append(
                {
                    "url": url,
                    "kind": kind,
                    "zim_relative": url.startswith("/") and not url.startswith("//"),
                }
            )

    return items
