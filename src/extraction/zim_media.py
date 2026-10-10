"""Resolve media hrefs from Wiktionary HTML to ZIM paths or remote URLs."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import PurePosixPath
from urllib.parse import unquote, urlparse

_WIKI_FILE = re.compile(r"/wiki/(?:File|Dosya):(.+)", re.I)
_SPECIAL_FILE = re.compile(r"Special:FilePath/(.+)", re.I)


def _basename_from_url(url: str) -> str:
    path = urlparse(url).path
    name = PurePosixPath(unquote(path)).name
    return name or "asset.bin"


def local_media_relative_path(*, entry_normalized: str, kind: str, url: str) -> str:
    """Stable path under media_export_dir: ``{lemma}/{kind}/{filename}``."""
    base = _basename_from_url(url)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    stem = PurePosixPath(base).stem
    suffix = PurePosixPath(base).suffix or ".bin"
    filename = f"{stem}-{digest}{suffix}"
    return str(PurePosixPath(entry_normalized) / kind / filename)


def zim_path_candidates(article_zim_path: str, href: str) -> list[str]:
    """Build likely ZIM entry paths for a link found in article HTML."""
    href = href.strip()
    if not href or href.startswith("#"):
        return []
    if href.startswith("http://") or href.startswith("https://") or href.startswith("//"):
        return []

    article_dir = PurePosixPath(article_zim_path).parent
    raw = href.lstrip("/")
    candidates: list[str] = []

    joined = (article_dir / href).as_posix()
    candidates.append(joined)
    candidates.append(raw)
    if raw.startswith("_assets_/") or raw.startswith("./_assets_/"):
        asset = raw.removeprefix("./")
        candidates.append(asset)
    _zim_prefixes = ("I/", "J/", "C/", "M/", "A/", "B/", "W/", "X/", "Y/", "Z/", "_assets_/")
    if not raw.startswith(_zim_prefixes):
        candidates.append(f"I/{raw}")
        candidates.append(f"C/{raw}")

    wiki_match = _WIKI_FILE.search(href)
    if wiki_match:
        file_title = unquote(wiki_match.group(1)).replace(" ", "_")
        candidates.append(f"I/{file_title}")

    special_match = _SPECIAL_FILE.search(href)
    if special_match:
        file_title = unquote(special_match.group(1)).replace(" ", "_")
        candidates.append(f"I/{file_title}")

    seen: set[str] = set()
    ordered: list[str] = []
    for path in candidates:
        normalized = PurePosixPath(path).as_posix()
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)
    return ordered


def resolve_media_href(
    *,
    article_zim_path: str,
    href: str,
    has_zim_path: Callable[[str], bool],
) -> dict[str, str]:
    """
    Return download metadata: ``source`` is ``zim`` or ``remote``; ``fetch_url`` or ``zim_path``.
    """
    href = href.strip()
    if href.startswith("//"):
        remote = f"https:{href}"
        return {
            "source": "remote",
            "fetch_url": remote,
            "url": remote,
        }
    if href.startswith("http://") or href.startswith("https://"):
        return {"source": "remote", "fetch_url": href, "url": href}

    for candidate in zim_path_candidates(article_zim_path, href):
        if has_zim_path(candidate):
            return {
                "source": "zim",
                "zim_path": candidate,
                "url": href,
            }

    return {
        "source": "unresolved",
        "url": href,
        "hint": "Try maxi ZIM or Wikimedia URL; no matching ZIM entry for href",
    }
