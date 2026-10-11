from src.mdict.syllabification import syllabification_from_bilevkirin_html


def test_syllabification_from_bilevkirin_li() -> None:
    html = "<ul><li>Kîtekirin: he·val</li></ul>"
    assert syllabification_from_bilevkirin_html(html) == "he·val"


def test_syllabification_skips_style_li() -> None:
    html = (
        "<ul><li><style>.x{}</style></li>"
        "<li>Kîtekirin: he·val</li></ul>"
    )
    assert syllabification_from_bilevkirin_html(html) == "he·val"
