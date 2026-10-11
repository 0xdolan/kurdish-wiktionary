"""Syllabification (Kîtekirin) from Bilêvkirin section HTML or entry metadata."""

from __future__ import annotations

import re

from selectolax.lexbor import LexborHTMLParser

_KITEKRIN_PREFIX = re.compile(r"^kîtekirin\s*:\s*", re.IGNORECASE)


def syllabification_from_bilevkirin_html(html: str) -> str | None:
    if not html.strip():
        return None
    tree = LexborHTMLParser(html)
    for li in tree.css("li"):
        outer = li.html or ""
        if "mw-parser-output" in outer or "<style" in outer.lower():
            continue
        text = li.text(separator=" ", strip=True)
        if not text or len(text) > 120:
            continue
        if not _KITEKRIN_PREFIX.match(text):
            if "kîtekirin" not in text.casefold():
                continue
            if ":" not in text:
                continue
        _, _, value = text.partition(":")
        value = value.strip()
        if value:
            return value
    return None
