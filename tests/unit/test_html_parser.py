from src.extraction.html_parser import parse_wiktionary_html

MINIMAL_KU = """
<div class="mw-parser-output" lang="ku" dir="ltr">
  <div class="mw-heading mw-heading2"><h2 id="Kurmancî"><span>Kurmancî</span></h2></div>
  <div class="mw-heading mw-heading3"><h3 id="Bilêvkirin"><span>Bilêvkirin</span></h3></div>
  <ul><li>IPA: <span class="IPA">/heval/</span></li></ul>
  <div class="mw-heading mw-heading3"><h3 id="Navdêr"><span>Navdêr</span></h3></div>
  <ol><li>Hevalê min.</li><li>Partner.</li></ol>
  <span class="benimune">Ez hevala xwe dibînim.</span>
</div>
"""

EMPTY_SECTIONS = """
<div class="mw-parser-output"><p>Redirect-only stub.</p></div>
"""

MESSY_HTML = """
<div class="mw-parser-output">
  <h3><span>Peyv</span></h3>
  <ol><li>  </li><li>Valid sense.</li></ol>
  <a href="https://upload.wikimedia.org/foo.wav">audio</a>
</div>
"""


def test_parse_minimal_kurdish_entry() -> None:
    entry = parse_wiktionary_html("heval", MINIMAL_KU, metadata_base={"source": "test"})
    assert entry.entry == "heval"
    assert "Navdêr" in entry.part_of_speech
    assert any("Hevalê min" in d for d in entry.definitions)
    assert entry.phonetic_transcriptions == ["/heval/"]
    assert entry.examples
    assert entry.metadata["layout_version"] == "ku-mw-2026-v4"


def test_parse_empty_sections_returns_model() -> None:
    entry = parse_wiktionary_html("empty", EMPTY_SECTIONS)
    assert entry.entry == "empty"
    assert entry.definitions == []
    assert entry.etymology is None


def test_parse_messy_html_filters_blank_definitions() -> None:
    entry = parse_wiktionary_html("peyv", MESSY_HTML)
    assert entry.definitions == ["Valid sense."]
    assert entry.pronunciations[0].endswith(".wav")


SYNONYM_SECTION = """
<div class="mw-parser-output">
  <h3><span>Beranber</span></h3>
  <ul><li><a href="/wiki/heval" title="heval">heval</a></li><li>dost</li></ul>
  <h3><span>Navdêr</span></h3>
  <ol><li>friend</li></ol>
</div>
"""


def test_parse_synonym_and_antonym_sections() -> None:
    entry = parse_wiktionary_html("test", SYNONYM_SECTION)
    assert "heval" in entry.synonyms or "dost" in entry.synonyms
    assert entry.definitions == ["friend"]
    assert entry.metadata.get("section_html")


HEVAL_INLINE_SYNONYM = """
<div class="mw-parser-output">
  <h3><span>Navdêr</span></h3>
  <ol>
    <li>Keç û kurên ji hev hez dikin. Hevmane: yar Nimûneyekê lê zêde bike</li>
  </ol>
</div>
"""


def test_parse_inline_hevmane_synonym() -> None:
    entry = parse_wiktionary_html("heval", HEVAL_INLINE_SYNONYM)
    assert "yar" in entry.synonyms


HEVAL_MW_HEADING_SECTIONS = """
<div class="mw-parser-output">
  <div class="mw-heading mw-heading4"><h4 id="Hevmane">Hevmane</h4></div>
  <ul>
    <li><a href="birader#Kurmancî" title="birader">birader</a></li>
    <li><a href="dost#Kurmancî" title="dost">dost</a></li>
  </ul>
  <div class="mw-heading mw-heading4"><h4 id="Dijmane">Dijmane</h4></div>
  <ul><li><a href="dijmin#Kurmancî" title="dijmin">dijmin</a></li></ul>
</div>
"""


def test_parse_mw_heading_h4_hevmane_dijmane_sections() -> None:
    entry = parse_wiktionary_html("heval", HEVAL_MW_HEADING_SECTIONS)
    assert "birader" in entry.synonyms
    assert "dost" in entry.synonyms
    assert "dijmin" in entry.antonyms
    assert "hevmane" in (entry.metadata.get("section_html") or {})


HEVAL_DEFINITION_WITH_LINKS = """
<div class="mw-parser-output">
  <ol>
    <li><a href="keç" title="keç">Keç</a> û <a href="kur" title="kur">kurên</a> ji hev hez dikin.
    <dl><dd><span class="nyms Hevmane"><span class="defdate">Hevmane:</span>
      <a href="yar#Kurmancî" title="yar">yar</a></span></dd></dl>
    <ul><li><span class="benimune">Nimûneyekê lê zêde bike
      <span class="stubedit"><a class="external text" href="https://ku.wiktionary.org/w/index.php?title=heval&amp;action=edit">
      <span>[ biguhêre ]</span></a></span></span></li></ul>
    </li>
  </ol>
  <div class="mw-heading mw-heading4"><h4 id="Hevmane">Hevmane</h4></div>
  <ul><li><a title="dost">dost</a></li></ul>
</div>
"""


def test_parse_synonyms_exclude_definition_links_and_edit_stub() -> None:
    entry = parse_wiktionary_html("heval", HEVAL_DEFINITION_WITH_LINKS)
    assert entry.synonyms == ["dost", "yar"]


EMPTY_SPAN_HEADING = """
<div class="mw-parser-output">
  <div class="mw-heading mw-heading3"><h3 id="Navdêr"><span id="mw-ce"></span>Navdêr</h3></div>
  <ol><li>Hevalê min.</li></ol>
  <div class="mw-heading mw-heading4"><h4 id="Etîmolojî"><span></span>Etîmolojî</h4></div>
  <p>Ji <a href="heval#Kurmancî" title="heval">heval</a>.</p>
  <div class="mw-heading mw-heading4"><h4 id="Tewandin"><span></span>Tewandin</h4></div>
  <div class="inflection-table"><table><tr><td>heval</td></tr></table></div>
  <div class="mw-heading mw-heading4"><h4 id="Jê"><span></span>Jê</h4></div>
  <ul><li><a href="hevaltî" title="hevaltî">hevaltî</a></li></ul>
</div>
"""


def test_parse_empty_span_heading_and_h4_sections() -> None:
    entry = parse_wiktionary_html("heval", EMPTY_SPAN_HEADING)
    assert "Navdêr" in entry.part_of_speech
    assert entry.etymology and "heval" in entry.etymology
    assert "hevaltî" in entry.derived_terms
    section_html = entry.metadata.get("section_html") or {}
    assert "tewandin" in section_html
    assert "etimoloji" in section_html


def test_parse_decodes_html_entities_in_definitions() -> None:
    html = """
    <div class="mw-parser-output">
      <ol><li>W&#238;k&#238;ferheng &amp; heval</li></ol>
    </div>
    """
    entry = parse_wiktionary_html("test", html)
    assert entry.definitions == ["Wîkîferheng & heval"]
