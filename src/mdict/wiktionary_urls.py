"""Live Wiktionary article URLs for MDict entry footers."""

from __future__ import annotations

from urllib.parse import quote

DEFAULT_WIKTIONARY_LANG = "ku"


def encode_mediawiki_title(title: str) -> str:
    """Path segment for ``/wiki/{title}`` (spaces → underscores, UTF-8 percent-encoding)."""
    normalized = title.strip().replace(" ", "_")
    return quote(normalized, safe="()!~*'")


def live_wiktionary_article_url(
    entry: str,
    *,
    lang: str = DEFAULT_WIKTIONARY_LANG,
) -> str:
    lang = lang.strip().lower() or DEFAULT_WIKTIONARY_LANG
    segment = encode_mediawiki_title(entry)
    return f"https://{lang}.wiktionary.org/wiki/{segment}"
