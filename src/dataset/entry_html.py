"""Dictionary article HTML: the wiki's sections, rebuilt for narrow screens and two themes.

Pipeline for one section: remove wiki chrome, reuse the shared sanitizer (internal links become
``entry://``), then turn pronunciations into voice cards, figures into a gallery and tables into
scrollable blocks. Styling and behaviour live in assets/mdict/css/dictionary.css and
js/dictionary.js, so each of the million records stays small.
"""

from __future__ import annotations

import re
from html import escape
from urllib.parse import unquote

from selectolax.lexbor import LexborHTMLParser, LexborNode

from src.dataset.page_parser import commons_file_from_url, media_id_for, normalize_asset_path
from src.dataset.sections import POS_LABELS, SECTION_LABELS
from src.mdict.html_sanitize import sanitize_section_html

STYLESHEET_LINK = '<link rel="stylesheet" type="text/css" href="css/dictionary.css" />'
SCRIPT_TAG = '<script type="text/javascript" src="js/dictionary.js"></script>'

# Row: section_id, entry_id, ordinal, level, heading, type, pos, html
SectionRow = tuple[int, int, int, int, str, str, str | None, str]

# Long sections start closed, so a 400-language translation table doesn't bury everything else.
_CLOSED_ABOVE_ITEMS = 20
# Pages with many languages open only the first; the contents list opens the others.
_OPEN_ALL_LANGUAGES_UP_TO = 3

_DROP = ".benimune, .stubedit, .mw-editsection, .ext-phonos-attribution, .audiometa, .popup-trigger"
_RTL_TEXT = re.compile(r"[֐-ࣿיִ-﷿ﹰ-﻿]")
_IMG_SRC = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")')
_AUDIO_LINK = re.compile(
    r'<a\b[^>]*?\bhref="((?:https?:)?//upload\.wikimedia\.org/[^"]+)"[^>]*>.*?</a>', re.S
)
_FIGURE = re.compile(r"<figure\b[^>]*>(.*?)</figure>", re.S)
_ATTR_SRC = re.compile(r'\bsrc="([^"]+)"')
_FIGCAPTION = re.compile(r"<figcaption\b[^>]*>(.*?)</figcaption>", re.S)
_TABLE_TAG = re.compile(r"<(/?)table\b([^>]*)>", re.I)
# Inline colours and fixed sizes from the wiki fight both themes and small screens.
_PRESENTATION = re.compile(
    r'\s(?:style|bgcolor|align|valign|width|height|border|cellpadding|cellspacing)="[^"]*"'
)
_EMPTY_LIST = re.compile(r"<(ul|ol|dl)\b[^>]*>\s*</\1>")
_SPEAKER = re.compile(r"^LL-Q\d+[ _]\([^)]*\)-(.+?)-")
_TAG = re.compile(r"<[^>]+>")
_SECTION_CLASS = re.compile(r"[^a-z_]")


def is_rtl(text: str) -> bool:
    return bool(_RTL_TEXT.search(text))


def fold_labels(section_type: str, pos: str | None, heading: str) -> tuple[str, str]:
    """(Kurmancî shown by default, English): the wiki's own heading stays the Kurmancî label."""
    if pos:
        english = POS_LABELS.get(pos, (pos, pos))[1]
    else:
        english = SECTION_LABELS.get(section_type, (section_type, heading or section_type))[1]
    return heading or english, english


def clean_fragment(fragment: str) -> str:
    """Remove edit links and prompts, and balance tags so a section can't break the article."""
    body = LexborHTMLParser(fragment).body
    if body is None:
        return fragment
    for node in body.css(_DROP):
        node.decompose()
    for item in body.css("li, dd"):
        if not item.text(deep=True).strip() and item.css_first("img, a, table") is None:
            item.decompose()
    html = body.html
    return html.removeprefix("<body>").removesuffix("</body>") if html else ""


def _voice_label(url: str, qualifier: str, ordinal: int) -> tuple[str, str]:
    """(Name shown large, speaker shown small) for one recording."""
    file_name = commons_file_from_url(url) or unquote(url.rsplit("/", 1)[-1])
    match = _SPEAKER.match(file_name)
    speaker = match.group(1).replace("_", " ") if match else ""
    if qualifier:
        return qualifier, speaker
    if speaker:
        return speaker, ""
    return f"Deng {ordinal}", ""


def voice_card(url: str, qualifier: str, ordinal: int, local_paths: dict[str, str]) -> str:
    """A recording: ``sound://`` works without JavaScript, the script adds play and pause."""
    if url.startswith("//"):
        url = f"https:{url}"
    name, speaker = _voice_label(url, qualifier, ordinal)
    local = local_paths.get(media_id_for(url))
    sub = f'<span class="wk-voice-sub">{escape(speaker)}</span>' if speaker else ""
    label = escape(f"Guhdar bike: {name}", quote=True)
    if local:
        path = escape(local, quote=True)
        target = f'href="sound://{path}" data-audio="{path}"'
        classes = "wk-voice"
    else:
        target = f'href="{escape(url, quote=True)}"'
        classes = "wk-voice wk-voice--web"
    return (
        f'<a class="{classes}" {target} aria-label="{label}">'
        '<span class="wk-play" aria-hidden="true"></span><span class="wk-voice-text">'
        f'<span class="wk-voice-name">{escape(name)}</span>{sub}</span></a>'
    )


def rewrite_media(fragment: str, local_paths: dict[str, str]) -> str:
    """Point images at the MDD and turn stray audio links into voice cards."""

    def image(match: re.Match[str]) -> str:
        path = normalize_asset_path(match.group(2))
        local = local_paths.get(media_id_for(path)) if path else None
        return f"{match.group(1)}{local or match.group(2)}{match.group(3)}"

    def audio(match: re.Match[str]) -> str:
        return voice_card(match.group(1), "", 1, local_paths)

    return _AUDIO_LINK.sub(audio, _IMG_SRC.sub(image, fragment))


def _node_text(node: LexborNode) -> str:
    return " ".join(node.text(deep=True).replace("\xa0", " ").split())


def _own_html(node: LexborNode) -> str:
    return "".join(child.html or "" for child in node.iter(include_text=True))


def _split_label(html: str) -> tuple[str, str, str]:
    """Split at the first colon in the text, never one inside a tag such as ``entry://``."""
    depth = 0
    for index, character in enumerate(html):
        if character == "<":
            depth += 1
        elif character == ">":
            depth -= 1
        elif character == ":" and depth == 0:
            return html[:index], ":", html[index + 1 :]
    return html, "", ""


def render_pronunciation(fragment: str, local_paths: dict[str, str]) -> str | None:
    """IPA chips, voice cards and labelled rows. ``None`` when the section isn't a list."""
    body = LexborHTMLParser(fragment).body
    items = body.css("li") if body is not None else []
    if not items:
        return None
    transcriptions: list[str] = []
    voices: list[str] = []
    rows: list[str] = []
    for item in items:
        labels = [_node_text(n) for n in item.css(".label-content, .qualifier-content")]
        qualifier = ", ".join(label for label in labels if label)
        links = item.css('a[href*="upload.wikimedia.org"]')
        ipas = item.css(".IPA")
        for link in links:
            voices.append(
                voice_card(
                    link.attributes.get("href") or "",
                    qualifier,
                    len(voices) + 1,
                    local_paths,
                )
            )
        for ipa in ipas:
            note = f'<span class="wk-chip-note">{escape(qualifier)}</span>' if qualifier else ""
            transcriptions.append(f'<span class="wk-ipa">{escape(_node_text(ipa))}{note}</span>')
        if links or ipas:
            continue
        inner = _own_html(item).strip()
        label, separator, value = _split_label(inner)
        if separator and len(_TAG.sub("", label)) < 40 and _TAG.sub("", value).strip():
            rows.append(
                f'<div class="wk-pron-row"><span class="wk-pron-label">{label}</span>'
                f'<span class="wk-pron-value">{value.strip().removeprefix("&nbsp;")}</span></div>'
            )
        elif inner:
            rows.append(
                f'<div class="wk-pron-row"><span class="wk-pron-value">{inner}</span></div>'
            )
    parts = []
    if transcriptions:
        parts.append(f'<div class="wk-ipas">{"".join(transcriptions)}</div>')
    if voices:
        parts.append(f'<div class="wk-voices">{"".join(voices)}</div>')
    if rows:
        parts.append(f'<div class="wk-pron-rows">{"".join(rows)}</div>')
    return f'<div class="wk-pron">{"".join(parts)}</div>' if parts else None


def extract_gallery(fragment: str) -> tuple[str, str]:
    """Pull figures out of the text flow: floats overlap citations and tables on small screens."""
    figures: list[str] = []

    def collect(match: re.Match[str]) -> str:
        inner = match.group(1)
        source = _ATTR_SRC.search(inner)
        if source is None:
            return match.group(0)
        caption_match = _FIGCAPTION.search(inner)
        caption = caption_match.group(1).strip() if caption_match else ""
        alt = escape(_TAG.sub("", caption), quote=True)
        figures.append(
            f'<figure class="wk-fig"><img src="{source.group(1)}" alt="{alt}" loading="lazy" />'
            + (f"<figcaption>{caption}</figcaption>" if caption else "")
            + "</figure>"
        )
        return ""

    remaining = _FIGURE.sub(collect, fragment)
    if not figures:
        return fragment, ""
    many = " wk-gallery--many" if len(figures) > 1 else ""
    return remaining, f'<div class="wk-gallery{many}">{"".join(figures)}</div>'


def wrap_tables(fragment: str) -> str:
    """Scrollable wrapper for data tables; layout tables (holding tables) stack on phones."""
    tags = list(_TABLE_TAG.finditer(fragment))
    if not tags:
        return fragment
    out: list[str] = []
    position = 0
    depth = 0
    start_index = 0
    for index, tag in enumerate(tags):
        closing = tag.group(1) == "/"
        if not closing:
            if depth == 0:
                start_index = index
            depth += 1
            continue
        depth -= 1
        if depth != 0:
            continue
        opening = tags[start_index]
        whole = fragment[opening.start() : tag.end()]
        out.append(fragment[position : opening.start()])
        position = tag.end()
        if "audiotable" in opening.group(2):
            out.append(whole)
        elif index - start_index > 1:
            # More tags between the outer pair: a table that lays out other tables.
            out.append(f'<div class="wk-layout">{wrap_inner_tables(whole)}</div>')
        else:
            out.append(f'<div class="wk-table">{whole}</div>')
    out.append(fragment[position:])
    return "".join(out)


def wrap_inner_tables(whole: str) -> str:
    """Wrap the leaf tables inside a layout table."""
    end = whole.rfind("</table>")
    first_close = whole.find(">") + 1
    inner = whole[first_close:end]
    return whole[:first_close] + wrap_tables(inner) + whole[end:]


def render_section_body(kind: str, fragment: str, local_paths: dict[str, str]) -> str:
    html = sanitize_section_html(clean_fragment(fragment))
    html = _EMPTY_LIST.sub("", html)
    if kind == "pronunciation":
        pronunciation = render_pronunciation(html, local_paths)
        if pronunciation is not None:
            return pronunciation
    html = _PRESENTATION.sub("", rewrite_media(html, local_paths))
    html, gallery = extract_gallery(html)
    html = wrap_tables(html)
    if not gallery:
        return html
    return f'<div class="wk-with-media"><div class="wk-text">{html}</div>{gallery}</div>'


def _section(section_id: int, kind: str, pos: str | None, heading: str, body: str) -> str:
    ku, en = fold_labels(kind, pos, heading)
    count = body.count("<li") if kind == "translations" else 0
    closed = count > _CLOSED_ABOVE_ITEMS
    badge = f'<span class="wk-count">{count}</span>' if count else ""
    css = _SECTION_CLASS.sub("", kind)
    return (
        f'<details class="wk-sec wk-sec--{css}"{"" if closed else " open"} id="wk-{section_id}">'
        f'<summary><span class="wk-sec-ku">{escape(ku)}</span>'
        f'<span class="wk-sec-en">{escape(en)}</span>{badge}</summary>'
        f'<div class="wk-sec-body">{body}</div></details>'
    )


def render_article(
    title: str,
    url: str,
    sections: list[SectionRow],
    languages: dict[int, tuple[str | None, str]],
    local_paths: dict[str, str],
) -> str:
    by_entry: dict[int, list[SectionRow]] = {}
    for row in sections:
        by_entry.setdefault(row[1], []).append(row)
    blocks: list[str] = []
    named_languages = sum(1 for entry_id in by_entry if languages.get(entry_id, (None, ""))[0])
    open_all = named_languages <= _OPEN_ALL_LANGUAGES_UP_TO
    for entry_id, rows in by_entry.items():
        inner: list[str] = []
        for section_id, _, _, _, heading, kind, pos, fragment in rows:
            if kind == "language":
                continue
            body = render_section_body(kind, fragment, local_paths)
            if not LexborHTMLParser(body).text(strip=True) and "<img" not in body:
                continue
            if not heading:  # Text before the first heading (hatnotes) has no heading to show.
                inner.append(f'<div class="wk-lead">{body}</div>')
                continue
            inner.append(_section(section_id, kind, pos, heading, body))
        if not inner:
            continue
        name, code = languages.get(entry_id, (None, "und"))
        if not name:
            blocks.extend(inner)
            continue
        opened = " open" if open_all or not blocks else ""
        blocks.append(
            f'<details class="wk-lang"{opened} id="wk-{entry_id}"><summary>'
            f'<span class="wk-lang-name">{escape(name)}</span>'
            f'<span class="wk-code">{escape(code)}</span></summary>'
            f'<div class="wk-lang-body">{"".join(inner)}</div></details>'
        )
    word = escape(title)
    direction = ' dir="rtl"' if is_rtl(title) else ""
    return (
        '<article class="wk"><header class="wk-head">'
        f'<h1 class="wk-word"{direction}>{word}</h1><div class="wk-tools"></div></header>'
        '<nav class="wk-nav" aria-label="Naverok"></nav><div class="wk-main">'
        f'{"".join(blocks)}<footer class="wk-foot">'
        f'<a href="{escape(url, quote=True)}">Wîkîferheng</a>'
        " · CC BY-SA 4.0</footer></div></article>"
    )
