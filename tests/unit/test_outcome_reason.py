from src.catalog.outcome_reason import categorize_outcome_message


def test_categorize_no_definitions() -> None:
    msg = "No definitions or phonetics"
    assert categorize_outcome_message(msg) == "no_definitions_or_phonetics"


def test_categorize_article_missing() -> None:
    assert categorize_outcome_message("Article not found in ZIM") == "article_not_found_in_zim"


def test_outcome_retry_hint_for_failed() -> None:
    from src.catalog.outcome_reason import outcome_retry_hint

    hint = outcome_retry_hint("parse_error", "failed")
    assert "retry-failed" in hint.lower()
