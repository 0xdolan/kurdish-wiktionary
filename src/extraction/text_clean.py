import html
import re
import unicodedata

_ENTITY_RE = re.compile(r"&(?:#x?[0-9a-fA-F]+|[a-zA-Z]+);")


def decode_plain_text(value: str) -> str:
    """Decode HTML entities and normalize Unicode for stored plain text."""
    if not value:
        return ""
    text = html.unescape(value)
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\ufeff", "").replace("\u200b", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def contains_html_entities(value: str) -> bool:
    return bool(_ENTITY_RE.search(value))
