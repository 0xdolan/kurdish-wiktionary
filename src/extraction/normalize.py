import unicodedata


def normalize_entry_key(entry: str) -> str:
    """Normalize lemma for lookup/upsert keys (NFC, trimmed)."""
    return unicodedata.normalize("NFC", entry.strip())


def is_wiktionary_article_title(title: str) -> bool:
    if not title or ":" in title:
        return False
    lowered = title.lower()
    skip_prefixes = (
        "mediawiki:",
        "help:",
        "template:",
        "category:",
        "file:",
        "image:",
        "user:",
        "talk:",
        "special:",
        "module:",
    )
    return not any(lowered.startswith(prefix) for prefix in skip_prefixes)
