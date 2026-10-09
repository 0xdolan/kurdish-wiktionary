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
    assert entry.metadata["layout_version"] == "ku-mw-2026-v1"


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


def test_parse_decodes_html_entities_in_definitions() -> None:
    html = """
    <div class="mw-parser-output">
      <ol><li>W&#238;k&#238;ferheng &amp; heval</li></ol>
    </div>
    """
    entry = parse_wiktionary_html("test", html)
    assert entry.definitions == ["Wîkîferheng & heval"]
