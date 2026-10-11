from collections.abc import Iterable
from pathlib import Path

from src.core.models import WiktionaryEntry
from src.mdict.constants import ENTRY_SCRIPT_TAG, STYLESHEET_LINK
from src.mdict.renderer import render_entry_html

MDICT_RECORD_END = "</>"


def _sanitize_headword(headword: str) -> str:
    return headword.replace("\n", " ").replace("\r", " ").strip()


def format_txt_link_record(alias: str, target: str) -> str:
    """Redirect lookup: searching `alias` opens the article for `target`.

    MDict block syntax (GoldenDict forum / mdict-utils):

        bravery
        @@@LINK=brave
        </>
    """
    alias_line = _sanitize_headword(alias)
    target_line = _sanitize_headword(target)
    return f"{alias_line}\n@@@LINK={target_line}\n{MDICT_RECORD_END}\n"


def format_txt_record(entry: WiktionaryEntry) -> str:
    """MDict source txt: headword line, HTML body, closing `</>`.

    Pattern (UTF-8):

        {headword}
        <link rel="stylesheet" … href="css/wiktionary.css" />
        <article class="wikt-entry">…</article>
        </>
    """
    fragment = render_entry_html(entry)
    html_body = f"{STYLESHEET_LINK}\n{fragment}\n{ENTRY_SCRIPT_TAG}"
    headword = _sanitize_headword(entry.entry)
    return f"{headword}\n{html_body}\n{MDICT_RECORD_END}\n"


def write_dict_txt(
    entries: Iterable[WiktionaryEntry],
    output_path: Path,
    *,
    link_aliases: Iterable[tuple[str, str]] | None = None,
) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for entry in entries:
            handle.write(format_txt_record(entry))
            count += 1
        if link_aliases is not None:
            for alias, target in link_aliases:
                handle.write(format_txt_link_record(alias, target))
                count += 1
    return count


def format_txt_line(entry: WiktionaryEntry) -> str:
    """Backward-compatible alias used in unit tests (first line is headword)."""
    record = format_txt_record(entry)
    return record.split("\n", maxsplit=1)[0] + "\n"
