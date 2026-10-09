from dataclasses import dataclass, field
from typing import Any

from src.core.models import WiktionaryEntry
from src.extraction.html_parser import parse_wiktionary_html
from src.extraction.media_urls import extract_media_from_html


@dataclass(slots=True)
class ParsedPage:
    entry: WiktionaryEntry
    html_full: str
    section_html: dict[str, str] = field(default_factory=dict)
    media: list[dict[str, Any]] = field(default_factory=list)


def parse_wiktionary_page(
    title: str,
    html: str,
    *,
    metadata_base: dict[str, Any] | None = None,
) -> ParsedPage:
    entry = parse_wiktionary_html(title, html, metadata_base=metadata_base)
    section_html = dict(entry.metadata.get("section_html", {}))
    media = extract_media_from_html(html)
    return ParsedPage(
        entry=entry,
        html_full=html,
        section_html=section_html,
        media=media,
    )
