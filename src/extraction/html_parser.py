import re
from typing import Any

from selectolax.lexbor import LexborHTMLParser, LexborNode

from src.core.models import WiktionaryEntry
from src.extraction.text_clean import decode_plain_text

LAYOUT_VERSION = "ku-mw-2026-v4"

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
_SYNONYM_KEYWORDS = ("beranber", "hevwate", "hevmane", "synonym")
_ANTONYM_KEYWORDS = ("berberev", "dijmane", "zîv", "ziv", "antonym")
_DERIVED_KEYWORDS = ("jê", "jêder", "derived")
_PRONUNCIATION_HEADINGS = ("bilêvkirin", "bilevkirin", "telaffuz")
_INFLECTION_KEYWORDS = ("tewandin", "inflection")
_STUB_DEFINITION = re.compile(
    r"^Nimûneyekê lê zêde bike|^Nimûneyekê lê zêde bike\s*\[",
    re.IGNORECASE,
)

_INLINE_SYNONYM = re.compile(
    r"(?i)\b(?:hevmane|beranber(?:ek)?|hevwate)\s*:\s*([^.\n\[]+)",
)
_INLINE_ANTONYM = re.compile(
    r"(?i)\b(?:berberev|dijmane|zîv|ziv)\s*:\s*([^.\n\[]+)",
)
_NIMUNE_TRAIL = re.compile(r"\s*Nimûneyekê.*$", re.IGNORECASE)
_EDIT_STUB_LEMMA = re.compile(r"biguhêre|biguhere", re.IGNORECASE)


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
        from_span = _clean_text(span)
        if from_span:
            return from_span
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


def _is_stub_definition(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) <= 1:
        return True
    if _STUB_DEFINITION.match(stripped):
        return True
    return stripped in {"[ biguhêre ]", "biguhêre"}


def _clean_definition(text: str) -> str:
    cleaned = _NIMUNE_TRAIL.sub("", text).strip()
    cleaned = re.sub(r"\s*\[.*?\]\s*$", "", cleaned).strip()
    return decode_plain_text(cleaned)


def _collect_list_items(root: LexborNode) -> list[str]:
    items: list[str] = []
    for li in root.css("li"):
        text = _clean_definition(_clean_text(li))
        if text and not _is_stub_definition(text):
            items.append(text)
    return items


def _sanitize_relation_lemma(value: str) -> str | None:
    token = value.strip()
    if len(token) < 2:
        return None
    if token.startswith("[") or _EDIT_STUB_LEMMA.search(token):
        return None
    return token


def _filter_relation_lemmas(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        token = _sanitize_relation_lemma(value)
        if token:
            cleaned.append(token)
    return _unique_strings(cleaned)


def _collect_wiktionary_links(root: LexborNode) -> list[str]:
    lemmas: list[str] = []
    for anchor in root.css("a"):
        classes = anchor.attributes.get("class") or ""
        if "external" in classes:
            continue
        href = anchor.attributes.get("href") or ""
        if "action=edit" in href:
            continue
        title = anchor.attributes.get("title", "")
        text = _clean_text(anchor)
        candidate = title.strip() if title else text
        if candidate and not candidate.startswith("Category:"):
            lemma = _sanitize_relation_lemma(candidate)
            if lemma:
                lemmas.append(lemma)
    return lemmas


def _node_html_fragment(node: LexborNode) -> str:
    return node.html or ""


def _is_mw_heading_wrapper(node: LexborNode | None) -> bool:
    if node is None or node.tag != "div":
        return False
    classes = node.attributes.get("class") or ""
    return "mw-heading" in classes


def _heading_walk_start(heading: LexborNode) -> LexborNode:
    """MediaWiki ZIM HTML wraps ``h3``/``h4`` in ``div.mw-heading``; content follows the wrapper."""
    parent = heading.parent
    if parent is not None and _is_mw_heading_wrapper(parent):
        return parent
    return heading


def _next_sibling_node(node: LexborNode | None) -> LexborNode | None:
    sibling = node.next if node is not None else None
    while sibling is not None and sibling.tag == "-text":
        sibling = sibling.next
    return sibling


def _is_section_boundary(node: LexborNode) -> bool:
    if node.tag in {"h2", "h3", "h4"}:
        return True
    return _is_mw_heading_wrapper(node)


def _content_after_heading(heading: LexborNode) -> tuple[list[str], str]:
    text_items: list[str] = []
    html_chunks: list[str] = []
    sibling = _next_sibling_node(_heading_walk_start(heading))
    while sibling is not None and not _is_section_boundary(sibling):
        html_chunks.append(_node_html_fragment(sibling))
        if sibling.tag in {"ul", "ol", "dl"}:
            text_items.extend(_collect_wiktionary_links(sibling))
        elif sibling.tag == "p":
            paragraph = _clean_text(sibling)
            if paragraph:
                text_items.append(paragraph)
            text_items.extend(_collect_wiktionary_links(sibling))
        elif sibling.tag == "div" and sibling.css_first("ul, ol"):
            text_items.extend(_collect_wiktionary_links(sibling))
        sibling = _next_sibling_node(sibling)
    return text_items, "".join(html_chunks)


def _clean_relation_fragment(raw: str) -> str:
    text = _NIMUNE_TRAIL.sub("", raw).strip()
    text = re.sub(r"\s*\[.*?\]\s*$", "", text).strip()
    return decode_plain_text(text)


def _split_relation_values(raw: str) -> list[str]:
    chunk = _clean_relation_fragment(raw)
    if not chunk:
        return []
    parts = re.split(r"[,;]|\s+û\s+|\s+and\s+", chunk)
    out: list[str] = []
    for part in parts:
        token = part.strip()
        if token and len(token) > 1:
            out.append(token)
    return out


def _extract_inline_relations(root: LexborNode) -> tuple[list[str], list[str]]:
    """Kurdish Wiktionary often uses inline labels (e.g. ``Hevmane: yar``) in ``<li>``."""
    synonyms: list[str] = []
    antonyms: list[str] = []
    for node in root.css("li, p, dd, dt"):
        text = _clean_text(node)
        if not text:
            continue
        for match in _INLINE_SYNONYM.finditer(text):
            synonyms.extend(_split_relation_values(match.group(1)))
        for match in _INLINE_ANTONYM.finditer(text):
            antonyms.extend(_split_relation_values(match.group(1)))
        if node.tag in {"dd", "dt", "p"}:
            lower = text.casefold()
            if any(label in lower for label in ("hevmane:", "beranber:", "hevwate:")):
                synonyms.extend(_collect_wiktionary_links(node))
            if any(label in lower for label in ("berberev:", "dijmane:", "zîv:", "ziv:")):
                antonyms.extend(_collect_wiktionary_links(node))
    for node in root.css("span.nyms, span.Hevmane, span.Dijmane"):
        classes = (node.attributes.get("class") or "").casefold()
        links = _collect_wiktionary_links(node)
        if "hevmane" in classes or "beranber" in classes:
            synonyms.extend(links)
        if "dijmane" in classes or "berberev" in classes:
            antonyms.extend(links)
    return _unique_strings(synonyms), _unique_strings(antonyms)


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
        if bucket not in buckets and bucket not in ("etymology", "inflection"):
            continue
        items, html_frag = _content_after_heading(heading)
        if bucket in buckets:
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
    for node in tree.css(
        ".benimune, .example, blockquote, .h-usage-example, .e-example, .e-quotation"
    ):
        text = _clean_text(node)
        if text and not _is_stub_definition(text) and "Nimûneyekê lê zêde bike" not in text:
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
    if norm in {"jê", "je"}:
        return "derived_terms"
    if any(k in norm for k in _INFLECTION_KEYWORDS):
        return "inflection"
    if norm.startswith("navd") or norm.startswith("peyv"):
        return "pos"
    return "other"


def _extract_etymology_text(heading: LexborNode) -> str:
    chunks: list[str] = []
    sibling = _next_sibling_node(_heading_walk_start(heading))
    while sibling is not None and not _is_section_boundary(sibling):
        if sibling.tag in {"p", "dl"}:
            text = _clean_text(sibling)
            if text:
                chunks.append(text)
        sibling = _next_sibling_node(sibling)
    return " ".join(chunks)


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
        inline_synonyms, inline_antonyms = _extract_inline_relations(root)
        synonyms = _filter_relation_lemmas(section_fields["synonyms"] + inline_synonyms)
        antonyms = _filter_relation_lemmas(section_fields["antonyms"] + inline_antonyms)
        derived_terms = section_fields["derived_terms"]

        for heading in root.css("h2, h3, h4"):
            label = _heading_label(heading)
            if not label:
                continue
            bucket = _section_bucket(label)
            if bucket == "pos" and label not in part_of_speech:
                part_of_speech.append(label)

        for heading in root.css("h2, h3, h4"):
            if etymology is not None:
                break
            label = _heading_label(heading)
            if not label or _section_bucket(label) != "etymology":
                continue
            text = _extract_etymology_text(heading)
            if text:
                etymology = text

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
