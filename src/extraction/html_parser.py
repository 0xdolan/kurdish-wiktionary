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


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _collect_list_items(root: LexborNode) -> list[str]:
    items: list[str] = []
    for li in root.css("li"):
        text = _clean_text(li)
        if text and len(text) > 1:
            items.append(text)
    return items


def _collect_wiktionary_links(root: LexborNode) -> list[str]:
    lemmas: list[str] = []
    for anchor in root.css("a"):
        title = anchor.attributes.get("title", "")
        text = _clean_text(anchor)
        candidate = title.strip() if title else text
        if candidate and not candidate.startswith("Category:"):
            lemmas.append(candidate)
    return lemmas


def _node_html_fragment(node: LexborNode) -> str:
    return node.html or ""


def _content_after_heading(heading: LexborNode) -> tuple[list[str], str]:
    text_items: list[str] = []
    html_chunks: list[str] = []
    sibling = heading.next
    while sibling is not None and sibling.tag not in {"h2", "h3", "h4"}:
        html_chunks.append(_node_html_fragment(sibling))
        if sibling.tag in {"ul", "ol", "dl", "p"}:
            text_items.extend(_collect_list_items(sibling))
            if sibling.tag == "p":
                paragraph = _clean_text(sibling)
                if paragraph:
                    text_items.append(paragraph)
            text_items.extend(_collect_wiktionary_links(sibling))
        sibling = sibling.next
    return text_items, "".join(html_chunks)


def _gather_section_fields(root: LexborNode) -> tuple[dict[str, list[str]], dict[str, str]]:
    buckets: dict[str, list[str]] = {
        "synonyms": [],
        "antonyms": [],
        "derived_terms": [],
    }
    section_html: dict[str, str] = {}

    for heading in root.css("h2, h3, h4"):
        label = _heading_label(heading)
        if not label:
            continue
        bucket = _section_bucket(label)
        if bucket not in buckets:
            continue
        items, html_frag = _content_after_heading(heading)
        buckets[bucket].extend(items)
        key = _normalize_heading(label)
        if html_frag:
            section_html[key] = html_frag

    for key in buckets:
        buckets[key] = _unique_strings(buckets[key])
    return buckets, section_html


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
    return "other"


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
    synonyms: list[str] = []
    antonyms: list[str] = []
    derived_terms: list[str] = []
    section_html: dict[str, str] = {}
    etymology: str | None = None

    if root is not None:
        section_fields, section_html = _gather_section_fields(root)
        synonyms = section_fields["synonyms"]
        antonyms = section_fields["antonyms"]
        derived_terms = section_fields["derived_terms"]

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

    unique_definitions = _unique_strings(definitions)

    metadata = dict(metadata_base or {})
    metadata.setdefault("layout_version", LAYOUT_VERSION)
    if section_html:
        metadata["section_html"] = section_html

    return WiktionaryEntry(
        entry=decode_plain_text(entry),
        part_of_speech=_unique_strings(part_of_speech),
        definitions=unique_definitions,
        phonetic_transcriptions=_unique_strings(phonetic_transcriptions),
        pronunciations=_unique_strings(pronunciations),
        examples=_unique_strings(examples),
        synonyms=synonyms,
        antonyms=antonyms,
        etymology=etymology,
        derived_terms=derived_terms,
        metadata=metadata,
    )
