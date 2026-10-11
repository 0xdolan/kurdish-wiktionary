from src.mdict.section_content import html_has_visible_content, non_empty_strings


def test_non_empty_strings() -> None:
    assert non_empty_strings(["a", " ", "", "b"]) == ["a", "b"]


def test_html_has_visible_content_text() -> None:
    assert html_has_visible_content("<p>hello</p>") is True
    assert html_has_visible_content("<p>  </p>") is False


def test_html_has_visible_content_media() -> None:
    assert html_has_visible_content('<img src="x.png" alt="" />') is True
