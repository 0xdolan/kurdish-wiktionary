from src.mdict.wiktionary_urls import encode_mediawiki_title, live_wiktionary_article_url


def test_live_wiktionary_article_url_ku() -> None:
    assert live_wiktionary_article_url("heval") == "https://ku.wiktionary.org/wiki/heval"


def test_live_wiktionary_article_url_spaces() -> None:
    url = live_wiktionary_article_url("heval bûn", lang="ku")
    assert url == "https://ku.wiktionary.org/wiki/heval_b%C3%BBn"


def test_encode_mediawiki_title_preserves_unicode() -> None:
    assert encode_mediawiki_title("heval") == "heval"
