"""Detect whether rendered section bodies have real content."""

from __future__ import annotations

from selectolax.lexbor import LexborHTMLParser


def non_empty_strings(values: list[str]) -> list[str]:
    return [item.strip() for item in values if item and str(item).strip()]


def html_has_visible_content(html: str) -> bool:
    if not html or not html.strip():
        return False
    tree = LexborHTMLParser(html)
    body = tree.body
    if body is None:
        return bool(html.strip())
    text = body.text(separator=" ", strip=True)
    if text:
        return True
    return any(tree.css(tag) for tag in ("img", "audio", "video", "svg", "table"))
