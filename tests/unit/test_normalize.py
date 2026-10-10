from src.extraction.normalize import is_wiktionary_article_title, normalize_entry_key


def test_normalize_entry_key_nfc_and_trim() -> None:
    assert normalize_entry_key("  heval  ") == "heval"


def test_is_wiktionary_article_title_skips_namespaces() -> None:
    assert is_wiktionary_article_title("heval") is True
    assert is_wiktionary_article_title("Category:Foo") is False
    assert is_wiktionary_article_title("File:Audio.opus") is False
    assert is_wiktionary_article_title("fulltext/xapian") is False
    assert is_wiktionary_article_title("") is False
