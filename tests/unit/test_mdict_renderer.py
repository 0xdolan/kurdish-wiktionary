from src.core.models import WiktionaryEntry
from src.mdict.renderer import render_entry_html
from src.mdict.txt_writer import format_txt_record


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


def test_format_txt_record_uses_mdict_block_syntax() -> None:
    entry = WiktionaryEntry(entry="test", definitions=["one"])
    record = format_txt_record(entry)
    assert record.startswith("test\n")
    assert record.rstrip().endswith("</>")
    assert "one" in record
