"""Normalize extract skip/fail messages into stable categories for reports."""

from __future__ import annotations


def categorize_outcome_message(message: str | None) -> str:
    if not message:
        return "unknown"
    lower = message.casefold()
    if "no definitions" in lower or "no definitions or phonetics" in lower:
        return "no_definitions_or_phonetics"
    if "article not found" in lower:
        return "article_not_found_in_zim"
    if "no zim source matched" in lower:
        return "no_zim_source_matched"
    if "parse" in lower or "html" in lower:
        return "parse_error"
    return "other"


def outcome_retry_hint(category: str, status: str) -> str:
    if status == "failed":
        return "Retry with: catalog extract-canonical --retry-failed --resume --all"
    if category == "no_definitions_or_phonetics":
        return "Expected for empty/stub Wiktionary pages; usually do not retry."
    if category == "article_not_found_in_zim":
        return "Check zim_sources on canonical_lemmas; may need sync-canonical refresh."
    return "Inspect last_error in SQL or export jsonl."
