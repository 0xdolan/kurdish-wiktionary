from src.extraction.text_clean import contains_html_entities, decode_plain_text


def test_decode_html_entities_to_utf8() -> None:
    assert decode_plain_text("dolar&nbsp;") == "dolar"
    assert decode_plain_text("W&#238;k&#238;") == "Wîkî"
    assert decode_plain_text("  a   b  ") == "a b"


def test_contains_html_entities() -> None:
    assert contains_html_entities("foo &amp; bar")
    assert not contains_html_entities("plain Kürtî text")
