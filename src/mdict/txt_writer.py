from collections.abc import Iterable
from pathlib import Path

from src.core.models import WiktionaryEntry
from src.mdict.renderer import render_entry_html


def format_txt_record(entry: WiktionaryEntry) -> str:
    """MDict source txt: headword line, HTML body lines, closing `</>`."""
    fragment = render_entry_html(entry)
    html_body = f"<html><head><meta charset='utf-8'/></head><body>{fragment}</body></html>"
    headword = entry.entry.replace("\n", " ").replace("\r", " ")
    return f"{headword}\n{html_body}\n</>\n"


def write_dict_txt(entries: Iterable[WiktionaryEntry], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for entry in entries:
            handle.write(format_txt_record(entry))
            count += 1
    return count


def format_txt_line(entry: WiktionaryEntry) -> str:
    """Backward-compatible alias used in unit tests (first line is headword)."""
    record = format_txt_record(entry)
    return record.split("\n", maxsplit=1)[0] + "\n"
