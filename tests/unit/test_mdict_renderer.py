from src.core.models import WiktionaryEntry
from src.mdict.constants import STYLESHEET_LINK
from src.mdict.renderer import render_cross_reference, render_entry_html, sample_brave_entry
from src.mdict.txt_writer import format_txt_link_record, format_txt_record


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
            "mdict_media": [
                {"kind": "audio", "href": "heval/audio/x.mp3", "label": "Speaker"},
                {"kind": "image", "href": "heval/image/x.jpg", "label": "photo"},
            ]
        },
    )
    html = render_entry_html(entry)
    assert "wikt-audio-btn" in html
    assert 'data-audio-src="heval/audio/x.mp3"' in html
    assert "wikt-thumb-grid" in html
