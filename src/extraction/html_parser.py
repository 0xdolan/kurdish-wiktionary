from typing import Any

from selectolax.lexbor import LexborHTMLParser, LexborNode

from src.core.models import WiktionaryEntry
from src.extraction.text_clean import decode_plain_text

LAYOUT_VERSION = "ku-mw-2026-v1"

_POS_HEADINGS = frozenset(
    {
        "navdêr",
        "navder",
        "peyv",
        "rengdêr",
        "rengder",
        "rehendêr",
        "tewr",
        "jêgir",
        "cerdevk",
        "cerdevkî",
        "cerdevki",
        "komek",
        "demjimar",
        "reh",
        "alîk",
        "alîkdar",
        "alikdar",
        "gotin",
        "devok",
        "jêker",
    }
)

_ETYMOLOGY_KEYWORDS = ("etimoloj", "kok", "jêder")
_SYNONYM_KEYWORDS = ("beranber", "hevwate", "synonym")
_ANTONYM_KEYWORDS = ("berberev", "zîv", "ziv", "antonym")
_DERIVED_KEYWORDS = ("jê", "jêder", "derived")
_PRONUNCIATION_HEADINGS = ("bilêvkirin", "bilevkirin", "telaffuz")


def _clean_text(node: LexborNode | None) -> str:
    if node is None:
        return ""
    text = node.text(separator=" ", strip=True)
    return decode_plain_text(text)


def _heading_label(node: LexborNode) -> str:
    h = node.tag
    if h not in {"h2", "h3", "h4"}:
        return ""
    span = node.css_first("span")
    if span is not None:
        return _clean_text(span)
    return _clean_text(node)


def _normalize_heading(value: str) -> str:
    return value.casefold().replace("î", "i").replace("ê", "e").replace("û", "u").replace("ş", "s")


def _collect_list_items(root: LexborNode) -> list[str]:
    items: list[str] = []
    for li in root.css("li"):
        text = _clean_text(li)
        if text and len(text) > 1:
            items.append(text)
    return items


def _extract_ipa(tree: LexborHTMLParser) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for node in tree.css("span.IPA"):
        text = _clean_text(node)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _extract_pronunciations(tree: LexborHTMLParser) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for node in tree.css("a"):
        href = node.attributes.get("href", "")
        if not href:
            continue
        lower = href.lower()
        is_audio = any(ext in lower for ext in (".mp3", ".ogg", ".wav", ".opus"))
        if is_audio and href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def _extract_examples(tree: LexborHTMLParser) -> list[str]:
    examples: list[str] = []
    for node in tree.css(".benimune, .example, blockquote"):
        text = _clean_text(node)
        if text and "Nimûneyekê lê zêde bike" not in text:
            examples.append(text)
    return examples


def _section_bucket(heading: str) -> str:
    norm = _normalize_heading(heading)
    if any(k in norm for k in _PRONUNCIATION_HEADINGS):
        return "pronunciation"
    if any(k in norm for k in _ETYMOLOGY_KEYWORDS):
        return "etymology"
    if any(k in norm for k in _SYNONYM_KEYWORDS):
        return "synonyms"
    if any(k in norm for k in _ANTONYM_KEYWORDS):
        return "antonyms"
    if norm in _POS_HEADINGS or any(norm.startswith(pos) for pos in _POS_HEADINGS):
        return "pos"
    if any(k in norm for k in _DERIVED_KEYWORDS) and norm in {"jê", "je"}:
        return "derived"
    if norm.startswith("navd") or norm.startswith("peyv"):
        return "pos"
    return "definitions"


def parse_wiktionary_html(
    entry: str,
    html: str,
    *,
    metadata_base: dict[str, Any] | None = None,
) -> WiktionaryEntry:
    tree = LexborHTMLParser(html)
    root = tree.css_first(".mw-parser-output") or tree.body

    part_of_speech: list[str] = []
    definitions: list[str] = []
    etymology: str | None = None

    if root is not None:
        for heading in root.css("h2, h3, h4"):
            label = _heading_label(heading)
            if not label:
                continue
            bucket = _section_bucket(label)
            if bucket == "pos" and label not in part_of_speech:
                part_of_speech.append(label)

        for heading in root.css("h3"):
            label = _heading_label(heading)
            if not label or etymology is not None:
                continue
            if _section_bucket(label) != "etymology":
                continue
            sibling = heading.next
            chunks: list[str] = []
            while sibling is not None and sibling.tag not in {"h2", "h3", "h4"}:
                if sibling.tag in {"p", "dl"}:
                    text = _clean_text(sibling)
                    if text:
                        chunks.append(text)
                sibling = sibling.next
            if chunks:
                etymology = " ".join(chunks)

        for ol in root.css("ol"):
            definitions.extend(_collect_list_items(ol))

    phonetic_transcriptions = _extract_ipa(tree)
    pronunciations = _extract_pronunciations(tree)
    examples = _extract_examples(tree)

    if not definitions and root is not None:
        for ol in root.css("ol"):
            definitions.extend(_collect_list_items(ol))

    seen_def: set[str] = set()
    unique_definitions: list[str] = []
    for d in definitions:
        if d not in seen_def:
            seen_def.add(d)
            unique_definitions.append(d)

    metadata = dict(metadata_base or {})
    metadata.setdefault("layout_version", LAYOUT_VERSION)

    return WiktionaryEntry(
        entry=decode_plain_text(entry),
        part_of_speech=part_of_speech,
        definitions=unique_definitions,
        phonetic_transcriptions=phonetic_transcriptions,
        pronunciations=pronunciations,
        examples=examples,
        synonyms=[],
        antonyms=[],
        etymology=etymology,
        derived_terms=[],
        metadata=metadata,
    )
