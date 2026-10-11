from src.mdict.html_sanitize import sanitize_section_html


def test_sanitize_strips_embedded_style_and_uncollapses_inflection() -> None:
    html = """
    <div class="inflection-table-wrapper inflection-table-collapsed" style="width: fit-content">
    <style>.mw-parser-output { color: red; }</style>
    <table class="inflection-table"><caption>Title</caption>
    <tbody><tr><th>Navkî</th><td>heval</td></tr></tbody></table>
    </div>
    """
    out = sanitize_section_html(html)
    assert "<style" not in out
    assert "inflection-table-collapsed" not in out
    assert "wikt-inflection-wrap" in out
    assert "wikt-inflection-table" in out
    assert "heval" in out


def test_prepare_translations_strips_columns_and_tpos() -> None:
    html = """
    <div class="NavFrame werger-content">
    <div class="NavHead"><i></i></div>
    <div class="NavContent">
    <div style="column-width: 26em;">
    <div class="translations"><ul><li><span class="trad-de">Almanî</span>:
    <a href="Freund#Almanî" title="Freund">Freund</a>
    <span class="tpos"><a href="https://de.wiktionary.org/wiki/Freund" class="extiw external">→ de</a></span>
    </li></ul></div></div></div></div>
    """
    out = sanitize_section_html(html)
    assert "column-width" not in out
    assert "wikt-translations" in out
    assert "wikt-translations-frame" in out
    assert "tpos" not in out
    assert "NavHead" not in out


def test_rewrite_wiktionary_links_entry_scheme() -> None:
    html = '<a href="dost#Kurmancî" title="dost">dost</a>'
    out = sanitize_section_html(html)
    assert 'href="entry://dost"' in out
    assert "wikt-xref" in out


def test_prepare_derived_terms_grid() -> None:
    html = (
        '<div class="list-switcher-wrapper"><div class="term-list columns-bg">'
        "<ul><li><span class=\"ib-content qualifier-content\">lêker</span> "
        '<span class="Latn"><a href="heval_bûn" title="heval bûn">heval bûn</a></span></li></ul></div></div>'
    )
    out = sanitize_section_html(html)
    assert "wikt-derived-wrap" in out
    assert "wikt-derived-list" in out
    assert "wikt-chip-list" in out
    assert "wikt-derived-item" in out
    assert 'data-pos="lêker"' in out
    assert "wikt-derived-pos" in out
    assert "qualifier-content" not in out


def test_prepare_alt_script_list() -> None:
    html = (
        '<ul><li><span class="Latn"><a title="kurdî-erebî">k</a></span>: '
        '<span class="Arab ku-Arab"><a title="هه‌ڤال">x</a></span></li></ul>'
    )
    out = sanitize_section_html(html)
    assert "wikt-alt-script-list" in out
    assert "wikt-chip-list" not in out


def test_prepare_citation_block() -> None:
    html = (
        '<ul><li><div class="citation-whole"><span class="cited-source">Author, '
        '<cite><a class="extiw external" href="https://x.org">Mem û Zîn</a></cite>:</span>'
        '<dl><dd><span class="e-quotation">Quote <b>heval</b></span></dd></dl></div></li></ul>'
    )
    out = sanitize_section_html(html)
    assert "wikt-citation" in out
    assert "extiw" not in out
    assert "Mem û Zîn" in out


def test_prepare_etymology_tags_paragraph() -> None:
    html = '<body><p>Ji *<a href="ham" title="ham">ham</a>- "hev-"</p></body>'
    out = sanitize_section_html(html)
    assert 'class="wikt-etymology"' in out
    assert "<body>" not in out


def test_prepare_term_link_lists_adds_chip_class() -> None:
    html = "<body><ul><li><span class=\"Latn\" lang=\"ku\"><a href=\"x\" title=\"lêzim\">lêzim</a></span></li></ul></body>"
    out = sanitize_section_html(html)
    assert "wikt-chip-list" in out
    assert "<head>" not in out


def test_mark_arabic_script_spans_adds_rtl_class() -> None:
    html = '<ul><li><span class="Arab ku-Arab" lang="ku"><a href="x">هه‌ڤال</a></span></li></ul>'
    out = sanitize_section_html(html)
    assert "wikt-script-arabic" in out
    assert 'dir="rtl"' in out
