from src.core.models import WiktionaryEntry
from src.mdict.constants import STYLESHEET_LINK
from src.mdict.renderer import render_cross_reference, render_entry_html, sample_brave_entry
from src.mdict.txt_writer import format_txt_link_record, format_txt_record


def test_sections_are_collapsible_details() -> None:
    entry = WiktionaryEntry(
        entry="heval",
        definitions=["friend"],
        examples=["Hi"],
    )
    html = render_entry_html(entry)
    assert '<details class="wikt-fold"' in html
    assert "<summary class=" in html
    assert "wikt-fold-body" in html
    assert 'id="wikt-sec-navder"' in html
    assert "wikt-entry-layout" in html
    assert "wikt-toc-list" in html
    assert "wikt-lang-toggle" in html


def test_render_entry_includes_definitions() -> None:
    entry = WiktionaryEntry(
        entry="heval",
        definitions=["friend"],
        part_of_speech=["noun"],
    )
    html = render_entry_html(entry)
    assert "heval" in html
    assert "friend" in html
    assert "wikt-definitions" in html
    assert "wikt-headword" in html


def test_render_cross_reference_uses_entry_scheme() -> None:
    link = render_cross_reference("see heval", "heval")
    assert 'href="entry://heval"' in link
    assert "see heval" in link


def test_format_txt_record_uses_mdict_block_syntax() -> None:
    entry = WiktionaryEntry(entry="test", definitions=["one"])
    record = format_txt_record(entry)
    assert record.startswith("test\n")
    assert record.rstrip().endswith("</>")
    assert STYLESHEET_LINK in record
    assert "one" in record
    assert "<html>" not in record


def test_format_txt_link_record() -> None:
    record = format_txt_link_record("braver", "brave")
    assert record == "braver\n@@@LINK=brave\n</>\n"


def test_sample_brave_renders_synonyms() -> None:
    html = render_entry_html(sample_brave_entry())
    assert "courageous" in html
    assert "entry://courageous" in html


def test_render_pronunciation_includes_syllabification() -> None:
    entry = WiktionaryEntry(
        entry="heval",
        phonetic_transcriptions=["/hɛˈvɑːl/"],
        metadata={"syllabification": "he·val"},
    )
    html = render_entry_html(entry)
    assert "wikt-kitekrin-row" in html
    assert "he·val" in html
    assert "Kîtekirin" in html


def test_render_ipa_skips_audio_urls() -> None:
    entry = WiktionaryEntry(
        entry="heval",
        phonetic_transcriptions=["/hɛˈvɑːl/"],
        pronunciations=[
            "https://upload.wikimedia.org/wikipedia/commons/foo.mp3",
        ],
    )
    html = render_entry_html(entry)
    assert "/hɛˈvɑːl/" in html
    assert "wikimedia" not in html


def test_render_entry_includes_media_from_metadata() -> None:
    entry = WiktionaryEntry(
        entry="heval",
        definitions=["friend"],
        metadata={
            "section_html": {
                "wêne": '<figure class="thumb"><img src="./_assets_/x.jpg" alt="" /></figure>',
            },
            "mdict_media": [
                {"kind": "audio", "href": "heval/audio/x.mp3", "label": "Speaker"},
                {"kind": "image", "href": "heval/image/x-ab12cd34.jpg", "label": "photo"},
            ],
        },
    )
    html = render_entry_html(entry)
    assert "wikt-audio-btn" in html
    assert 'data-audio-src="heval/audio/x.mp3"' in html
    assert "wikt-thumb-grid" in html


def test_werger_section_links_downloaded_hiero_images() -> None:
    werger = (
        '<ul><li><span class="trad-egy">Misrî</span>: '
        '<table class="mw-hiero-table"><tr><td>'
        '<img src="./_assets_/9ae9a9c4e10735879dfb80eb97080019/hiero_Aa1.png" alt="x" />'
        "</td></tr></table></li></ul>"
    )
    entry = WiktionaryEntry(
        entry="heval",
        definitions=["friend"],
        metadata={
            "section_html": {"werger": werger},
            "mdict_media": [
                {
                    "kind": "image",
                    "href": "media/heval/image/hiero_Aa1-b0078bd565.png",
                    "source_url": "./_assets_/9ae9a9c4e10735879dfb80eb97080019/hiero_Aa1.png",
                }
            ],
        },
    )
    html = render_entry_html(entry)
    assert "_assets_" not in html
    assert "media/heval/image/hiero_Aa1-b0078bd565.png" in html


def test_live_wiktionary_section_after_content() -> None:
    entry = WiktionaryEntry(
        entry="heval",
        definitions=["friend"],
        metadata={"zim_source": "ku.wiktionary.org"},
    )
    html = render_entry_html(entry)
    assert 'data-section-key="li wiktionary"' in html
    assert 'id="wikt-sec-li-wiktionary"' in html
    assert 'href="https://ku.wiktionary.org/wiki/heval"' in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    werger_pos = html.find('data-section-key="werger"')
    live_pos = html.find('data-section-key="li wiktionary"')
    if werger_pos >= 0:
        assert live_pos > werger_pos


def test_wene_omitted_without_illustration_section() -> None:
    entry = WiktionaryEntry(
        entry="heval",
        definitions=["friend"],
        metadata={
            "mdict_media": [
                {"kind": "image", "href": "heval/image/photo-ab12cd34.jpg", "label": "photo"},
            ],
        },
    )
    html = render_entry_html(entry)
    assert "wikt-thumb-grid" not in html
    assert 'data-section-key="wêne"' not in html
