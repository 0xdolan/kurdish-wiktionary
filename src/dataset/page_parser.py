"""Parse one ZIM article into release tables, following the wiki's own layout.

A Wîkîferheng page is flat HTML with headings marking the hierarchy::

    h2 language -> h3 part of speech / pronunciation -> h4 subsection (translations, ...)

The parser slices the page at headings, keeps every section (type ``other`` when unknown) and then
extracts typed rows per section type. Rows are plain tuples ordered as in ``schema.TABLES``.
"""

from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urlparse

from selectolax.lexbor import LexborHTMLParser, LexborNode

from src.dataset.sections import RELATION_TYPES, classify_heading

ID_SPACE = 100_000
_NOPIC_PAGE_OFFSET = 10_000_000

_HEADING = re.compile(
    r'(?:<div class="mw-heading[^"]*">\s*)?<h([2-5])\b([^>]*)>(.*?)</h\1>(?:\s*</div>)?',
    re.S,
)
_LANG_SPAN = re.compile(r'class="besazimani"[^>]*\bid="([^"]+)"')
_ANCHOR = re.compile(r'\bid="([^"]*)"')
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_STYLE = re.compile(r"<style\b.*?</style>", re.S)
_NOISE_ATTR = re.compile(
    r'\s(?:data-ooui|data-mw-[a-z-]+|data-nosnippet|typeof|decoding|loading|tabindex)="[^"]*"'
)
_OOUI_CLASS = re.compile(r'\sclass="[^"]*oo-ui-[^"]*"')
_ORIGIN_FOOTER = re.compile(r'title="Last edited on ([0-9-]+)"[^>]*oldid=(\d+)')
_AUTO_SOURCE = re.compile(r'data-template-info="[^"]*".*?title="([^"]+)"', re.S)
_SOFT_REDIRECT = re.compile(r"^\s*Binêre\s+(.+?)\s*\.?\s*$", re.S)
_YEAR = re.compile(r"~?\b(\d{3,4})\b")
_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".tif", ".tiff")
_LIST_TAGS = frozenset({"ul", "ol", "dl"})
# Block ends and line breaks must separate words once markup is stripped.
_BLOCK_END = re.compile(r"(<br\s*/?>|</(?:div|li|dd|dt|p|td|th|tr|caption|figcaption)>)", re.I)

CONJUGATION_PREFIX = "Tewandin:"
CONJUGATION_LANGUAGE = ("Kurmancî", "ku")


def page_id_for(entry_index: int, *, from_nopic: bool) -> int:
    """Deterministic ids from ZIM order, so parallel workers need no coordination."""
    return entry_index + 1 + (_NOPIC_PAGE_OFFSET if from_nopic else 0)


def media_id_for(identity: str) -> str:
    return hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16]


def clean_text(value: str) -> str:
    return _WS.sub(" ", value.replace("\xa0", " ")).strip()


def strip_markup(fragment: str) -> str:
    return clean_text(html_lib.unescape(_TAG.sub("", fragment)))


def clean_section_html(fragment: str) -> str:
    """Drop per-page CSS and MediaWiki widget state; content and links are untouched."""
    text = _STYLE.sub("", fragment)
    text = _NOISE_ATTR.sub("", text)
    return _OOUI_CLASS.sub("", text).strip()


def link_target(href: str | None) -> str | None:
    """Article title for an internal link (``l%C3%AAzim#Kurmanc%C3%AE`` -> ``lêzim``)."""
    if not href or href.startswith(("http://", "https://", "//", "#", "./_", "../_")):
        return None
    path = unquote(href.split("#", 1)[0]).replace("_", " ").strip()
    while path.startswith("../") or path.startswith("./"):
        path = path.split("/", 1)[1]
    return path or None


def normalize_asset_path(src: str) -> str | None:
    """ZIM path of an ``img src`` (``./_assets_/x.png``, ``../_assets_/x.png``)."""
    path = src.split("?", 1)[0]
    while path.startswith("../") or path.startswith("./"):
        path = path.split("/", 1)[1]
    if path.startswith(("http://", "https://", "//", "data:")):
        return None
    return unquote(path) or None


def commons_file_from_url(url: str) -> str | None:
    """``.../transcoded/a/aa/X.wav/X.wav.mp3`` and ``.../a/aa/X.wav`` both give ``X.wav``."""
    parts = [p for p in urlparse(url).path.split("/") if p]
    if "commons" not in parts:
        return None
    rest = parts[parts.index("commons") + 1 :]
    if rest[:1] in (["transcoded"], ["thumb"]):
        rest = rest[1:]
    if len(rest) < 3:
        return None
    return unquote(rest[2])


def _classes(node: LexborNode) -> set[str]:
    return set((node.attributes.get("class") or "").split())


def _own_nodes(node: LexborNode, skip: frozenset[str] = _LIST_TAGS) -> Iterator[LexborNode]:
    """Descendants of ``node`` without entering nested lists."""
    for child in node.iter():
        if child.tag in skip:
            continue
        yield child
        yield from _own_nodes(child, skip)


def _own_text(node: LexborNode, *, skip_classes: frozenset[str] = frozenset()) -> str:
    """Text of ``node`` without nested lists (or elements carrying ``skip_classes``)."""
    parts: list[str] = []
    for child in node.iter(include_text=True):
        if child.tag == "-text":
            parts.append(child.text_content or "")
        elif child.tag in _LIST_TAGS or _classes(child) & skip_classes:
            continue
        elif child.tag == "br":
            parts.append(" ")
        else:
            parts.append(_own_text(child, skip_classes=skip_classes))
    return "".join(parts)


def _text(node: LexborNode | None) -> str:
    return clean_text(node.text(deep=True)) if node is not None else ""


def _child_lists(node: LexborNode, tag: str) -> list[LexborNode]:
    return [c for c in node.iter() if c.tag == tag]


_SENSE_LABEL_CLASSES = frozenset({"context-qualifier-colon", "usage-label-sense"})
_QUALIFIER_SELECTOR = ".qualifier-content, .label-content"
_DROP_FROM_TEXT = ".stubedit, .mw-editsection, .ext-phonos-attribution, .benimune, sup.reference"
# The wiki's "the meaning is not written yet" prompt; it is not a definition.
DEFINITION_PENDING = "Maneya vê madeyê hê nehatiye nivîsîn"


@dataclass(slots=True)
class _Section:
    section_id: int
    parent_id: int | None
    level: int
    ordinal: int
    heading: str
    anchor: str | None
    kind: str
    pos: str | None
    homograph: int | None
    raw: str


@dataclass(slots=True)
class ParsedPage:
    """Rows per table plus media seen on the page."""

    page_id: int
    rows: dict[str, list[tuple[Any, ...]]] = field(default_factory=lambda: defaultdict(list))
    media: dict[str, dict[str, Any]] = field(default_factory=dict)
    placeholder_examples: int = 0


class _Ids:
    def __init__(self, page_id: int) -> None:
        self._base = page_id * ID_SPACE
        self._counters: dict[str, int] = defaultdict(int)

    def next(self, table: str) -> int:
        self._counters[table] += 1
        return self._base + self._counters[table]


def _body_slice(html: str) -> tuple[str, str]:
    start = html.find("mw-parser-output")
    if start < 0:
        return "", ""
    start = html.find(">", start) + 1
    end = html.find("<!--htdig_noindex-->", start)
    tail = html[end:] if end >= 0 else html[-2000:]
    body = html[start:end] if end >= 0 else html[start:]
    # The wrapper's closing tag would otherwise end up in the page's last section.
    return body.rstrip().removesuffix("</div>"), tail


def _split_sections(body: str, ids: _Ids) -> tuple[str, list[_Section], list[str | None]]:
    """Return lead HTML, sections and each section's language code (for h2 sections)."""
    matches = list(_HEADING.finditer(body))
    lead = body[: matches[0].start()] if matches else body
    sections: list[_Section] = []
    lang_codes: list[str | None] = []
    stack: list[_Section] = []
    for ordinal, match in enumerate(matches, start=1):
        level = int(match.group(1))
        inner = match.group(3)
        heading = strip_markup(inner)
        end = matches[ordinal].start() if ordinal < len(matches) else len(body)
        code = _LANG_SPAN.search(inner) if level == 2 else None
        kind, pos, homograph = "language", None, None
        # Only the wiki's language marker makes an h2 a language: ``== Binêre ==`` is not one.
        if code is None:
            classified = classify_heading(heading, level)
            kind, pos, homograph = classified.kind, classified.pos, classified.homograph
        while stack and stack[-1].level >= level:
            stack.pop()
        anchor = _ANCHOR.search(match.group(2))
        section = _Section(
            section_id=ids.next("sections"),
            parent_id=stack[-1].section_id if stack else None,
            level=level,
            ordinal=ordinal,
            heading=heading,
            anchor=html_lib.unescape(anchor.group(1)) if anchor else None,
            kind=kind,
            pos=pos,
            homograph=homograph,
            raw=body[match.end() : end],
        )
        lang_codes.append(code.group(1) if code else None)
        sections.append(section)
        stack.append(section)
    return lead, sections, lang_codes


def _soft_redirect_target(lead: str) -> str | None:
    node = LexborHTMLParser(lead).body
    if node is None:
        return None
    text = _text(node)
    match = _SOFT_REDIRECT.match(text)
    if not match or len(text) > 200:
        return None
    link = node.css_first("a")
    target = link_target(link.attributes.get("href")) if link else None
    return target or clean_text(match.group(1))


def parse_page(
    *,
    html: str,
    title: str,
    page_id: int,
    source_zim: str,
    in_latest_dump: bool,
) -> ParsedPage:
    parsed = ParsedPage(page_id=page_id)
    ids = _Ids(page_id)
    body, tail = _body_slice(html)
    lead_raw, sections, lang_codes = _split_sections(body, ids)

    origin = _ORIGIN_FOOTER.search(tail)
    last_edited = origin.group(1) if origin else None
    revision_id = int(origin.group(2)) if origin else None
    is_conjugation = title.startswith(CONJUGATION_PREFIX)
    display_title = title.replace("_", " ")

    soft_target = None
    if not sections and not is_conjugation:
        soft_target = _soft_redirect_target(lead_raw)
    page_kind = "conjugation" if is_conjugation else "soft_redirect" if soft_target else "entry"

    state = _PageState(parsed, ids, display_title)
    current_entry: int | None = None
    language_count = 0
    opened: dict[str, int] = {}

    def fallback_entry() -> int:
        """Entry for content outside any language section; at most one per page."""
        if is_conjugation:
            code = CONJUGATION_LANGUAGE[1]
            if code not in opened:
                opened[code] = state.open_entry(
                    language_name=CONJUGATION_LANGUAGE[0],
                    language_code=code,
                    ordinal=0,
                )
                state.mark_pos(opened[code], "verb_conjugation")
            return opened[code]
        if "und" not in opened:
            opened["und"] = state.open_entry(language_name=None, language_code="und", ordinal=0)
        return opened["und"]

    lead: _Section | None = None
    if not soft_target and (strip_markup(_STYLE.sub("", lead_raw)) or not sections):
        lead = _Section(
            section_id=ids.next("sections"),
            parent_id=None,
            level=1,
            ordinal=0,
            heading="",
            anchor=None,
            kind="inflection" if is_conjugation else "lead",
            pos=None,
            homograph=None,
            raw=lead_raw,
        )
    # Lead text (hatnotes, "see also") belongs to the first language instead of a fake entry.
    if lead is not None and not (sections and sections[0].kind == "language"):
        current_entry = fallback_entry()
        state.handle_section(lead, current_entry)
        lead = None

    for section, code in zip(sections, lang_codes, strict=True):
        if code is not None:
            # A language repeated on one page merges, keeping entry_key unique.
            if code not in opened:
                language_count += 1
                opened[code] = state.open_entry(
                    language_name=section.heading,
                    language_code=code,
                    ordinal=language_count,
                )
            current_entry = opened[code]
            state.handle_section(section, current_entry)
            if lead is not None:
                state.handle_section(lead, current_entry)
                lead = None
            continue
        if current_entry is None:
            current_entry = fallback_entry()
        state.handle_section(section, current_entry)

    state.finish_entries()
    parsed.placeholder_examples = state.placeholders
    parsed.rows["pages"].append(
        (
            page_id,
            display_title,
            page_kind,
            source_zim,
            int(in_latest_dump),
            revision_id,
            last_edited,
            language_count,
            len(sections),
            f"https://ku.wiktionary.org/wiki/{title}",
        )
    )
    if soft_target:
        parsed.rows["redirects"].append((display_title, soft_target, "soft"))
    return parsed


class _PageState:
    def __init__(self, parsed: ParsedPage, ids: _Ids, title: str) -> None:
        self.parsed = parsed
        self.ids = ids
        self.title = title
        self.rows = parsed.rows
        self.placeholders = 0
        self._entries: dict[int, dict[str, Any]] = {}

    # ---- entries ---------------------------------------------------------------------------

    def open_entry(
        self, *, language_name: str | None, language_code: str | None, ordinal: int
    ) -> int:
        entry_id = self.ids.next("entries")
        self._entries[entry_id] = {
            "language_name": language_name,
            "language_code": language_code,
            "ordinal": ordinal,
            "pos": [],
            "senses": 0,
            "ipa": False,
            "audio": False,
            "etymology": False,
            "translations": False,
            "auto_source": None,
            "auto": False,
            "pending": False,
        }
        return entry_id

    def mark_pos(self, entry_id: int, pos: str) -> None:
        self._entries[entry_id]["pos"].append(pos)

    def finish_entries(self) -> None:
        for entry_id, info in self._entries.items():
            code = info["language_code"] or "und"
            pos = list(dict.fromkeys(info["pos"]))
            self.rows["entries"].append(
                (
                    entry_id,
                    self.parsed.page_id,
                    info["ordinal"],
                    self.title,
                    info["language_name"],
                    code,
                    f"{self.title}|{code}",
                    ", ".join(pos),
                    info["senses"],
                    int(info["ipa"]),
                    int(info["audio"]),
                    int(info["etymology"]),
                    int(info["translations"]),
                    int(info["auto"]),
                    info["auto_source"],
                    int(info["pending"]),
                )
            )

    # ---- sections --------------------------------------------------------------------------

    def handle_section(self, section: _Section, entry_id: int) -> None:
        parser = LexborHTMLParser(_BLOCK_END.sub(r"\1 ", _STYLE.sub("", section.raw)))
        root = parser.body
        info = self._entries[entry_id]
        cleaned = clean_section_html(section.raw)
        text = ""
        if root is not None:
            self._collect_auto_note(root, entry_id, section, info)
            self._collect_media(root, entry_id, section)
            self._collect_tables(root, entry_id, section)
            for node in root.css(_DROP_FROM_TEXT):
                if "benimune" in _classes(node):
                    self.placeholders += 1
                node.decompose()
            text = _text(root)
            self._dispatch(root, entry_id, section, info, text)

        self.rows["sections"].append(
            (
                section.section_id,
                self.parsed.page_id,
                entry_id,
                section.parent_id,
                section.ordinal,
                section.level,
                section.heading,
                section.anchor,
                section.kind,
                section.pos,
                section.homograph,
                text,
            )
        )
        if cleaned:
            self.rows["section_html"].append((section.section_id, cleaned))

    def _dispatch(
        self,
        root: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
        text: str,
    ) -> None:
        kind = section.kind
        if kind == "pos":
            self._parse_pos(root, entry_id, section, info)
        elif kind == "pronunciation":
            self._parse_pronunciation(root, entry_id, section, info)
        elif kind == "etymology":
            self._parse_etymology(root, entry_id, section, info, text)
        elif kind == "translations":
            self._parse_translations(root, entry_id, section, info)
        elif kind in RELATION_TYPES:
            self._parse_relations(root, entry_id, section, kind)
        elif kind == "quotations":
            self._parse_quotation_section(root, entry_id, section)
        elif kind == "references" and text:
            self.rows["reference_notes"].append(
                (self.ids.next("reference_notes"), entry_id, section.section_id, text)
            )

    # ---- quality flag ----------------------------------------------------------------------

    def _collect_auto_note(
        self,
        root: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
    ) -> None:
        note = root.css_first(".werger-template-info")
        if note is None:
            return
        info["auto"] = True
        link = note.css_first("a")
        info["auto_source"] = link.attributes.get("title") if link else None

    # ---- media -----------------------------------------------------------------------------

    def _collect_media(self, root: LexborNode, entry_id: int, section: _Section) -> None:
        for img in root.css("img"):
            src = img.attributes.get("src") or ""
            path = normalize_asset_path(src)
            if not path:
                continue
            media_id = media_id_for(path)
            figure = img.parent
            caption = None
            role = "icon"
            while figure is not None and figure.tag not in ("figure", "body"):
                figure = figure.parent
            if figure is not None and figure.tag == "figure":
                role = "illustration"
                caption = _text(figure.css_first("figcaption")) or None
            if "hiero_" in path:
                role = "hieroglyph"
            self.parsed.media.setdefault(
                media_id,
                {
                    "media_id": media_id,
                    "kind": "image",
                    "zim_path": path,
                    "source_url": None,
                    "commons_file": None,
                    "original_width": _int(img.attributes.get("data-file-width")),
                    "original_height": _int(img.attributes.get("data-file-height")),
                },
            )
            self._add_usage(media_id, entry_id, section, role, caption)

        for link in root.css('a[href*="upload.wikimedia.org"]'):
            href = (link.attributes.get("href") or "").strip()
            if href.startswith("//"):
                href = f"https:{href}"
            kind = "image" if href.casefold().endswith(_IMAGE_EXT) else "audio"
            media_id = media_id_for(href)
            self.parsed.media.setdefault(
                media_id,
                {
                    "media_id": media_id,
                    "kind": kind,
                    "zim_path": None,
                    "source_url": href,
                    "commons_file": commons_file_from_url(href),
                    "original_width": None,
                    "original_height": None,
                },
            )
            self._add_usage(
                media_id, entry_id, section, "pronunciation" if kind == "audio" else "link", None
            )

    def _add_usage(
        self,
        media_id: str,
        entry_id: int,
        section: _Section,
        role: str,
        caption: str | None,
    ) -> None:
        self.rows["media_usages"].append(
            (
                self.ids.next("media_usages"),
                media_id,
                self.parsed.page_id,
                entry_id,
                section.section_id,
                role,
                caption,
            )
        )

    # ---- tables ----------------------------------------------------------------------------

    def _collect_tables(self, root: LexborNode, entry_id: int, section: _Section) -> None:
        for ordinal, table in enumerate(root.css("table"), start=1):
            classes = _classes(table)
            # Layout tables wrap the real ones: only leaf tables hold forms.
            if "audiotable" in classes or len(table.css("table")) > 1:
                continue
            is_inflection = section.kind == "inflection" or bool(
                classes & {"inflection-table", "tewandin-tablo", "wikitable"}
            )
            if not is_inflection:
                continue
            caption = _text(table.css_first("caption")) or None
            grid = _table_grid(table)
            if not grid:
                continue
            table_id = self.ids.next("inflection_tables")
            width = max(len(row) for row in grid)
            self.rows["inflection_tables"].append(
                (
                    table_id,
                    entry_id,
                    section.section_id,
                    ordinal,
                    caption,
                    len(grid),
                    width,
                    json.dumps(
                        [[cell[1] for cell in row] for row in grid],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                )
            )
            for row_header, col_header, group, form, target in _table_forms(grid, width):
                self.rows["inflection_forms"].append(
                    (
                        self.ids.next("inflection_forms"),
                        table_id,
                        entry_id,
                        group,
                        row_header,
                        col_header,
                        form,
                        target,
                    )
                )

    # ---- part of speech (senses) -----------------------------------------------------------

    def _parse_pos(
        self,
        root: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
    ) -> None:
        info["pos"].append(section.pos)
        for line in root.css(".headword-line"):
            head = line.css_first(".headword")
            genders = [
                (abbr.attributes.get("title") or _text(abbr)) for abbr in line.css(".gender abbr")
            ]
            self.rows["headwords"].append(
                (
                    self.ids.next("headwords"),
                    entry_id,
                    section.section_id,
                    section.pos,
                    section.homograph,
                    _text(head) or None,
                    ", ".join(g for g in genders if g) or None,
                    _text(line),
                )
            )
        lists = [c for c in root.iter() if c.tag == "ol" and "references" not in _classes(c)]
        if lists:
            for ol in lists:
                self._parse_sense_list(ol, entry_id, section, info, None, 0)
            return
        # Older pages write definitions as bullets, indents or plain paragraphs.
        count = 0
        for child in root.iter():
            if child.tag in ("ul", "dl"):
                for li in child.iter():
                    if li.tag in ("li", "dd"):
                        count += self._add_sense(li, entry_id, section, info, None, 0)
        if count == 0:
            for child in root.iter():
                if child.tag == "p" and child.css_first(".headword-line") is None:
                    self._add_sense(child, entry_id, section, info, None, 0)

    def _parse_sense_list(
        self,
        ol: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
        parent: int | None,
        depth: int,
    ) -> None:
        for li in ol.iter():
            if li.tag == "li":
                self._add_sense(li, entry_id, section, info, parent, depth)

    def _add_sense(
        self,
        li: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
        parent: int | None,
        depth: int,
    ) -> int:
        text = clean_text(_own_text(li, skip_classes=_SENSE_LABEL_CLASSES))
        nested = [c for c in li.iter() if c.tag in _LIST_TAGS]
        if not text and not nested:
            return 0
        if text.startswith(DEFINITION_PENDING):
            info["pending"] = True
            return 0
        labels = [
            _text(n)
            for child in li.iter()
            if _classes(child) & _SENSE_LABEL_CLASSES
            for n in child.css(".label-content")
        ]
        sense_id = self.ids.next("senses")
        info["senses"] += 1
        self.rows["senses"].append(
            (
                sense_id,
                entry_id,
                section.section_id,
                parent,
                self._next_sense_ordinal(section.section_id, parent),
                depth,
                section.pos,
                ", ".join(labels) or None,
                text,
                json.dumps(_own_links(li), ensure_ascii=False) if li.css_first("a") else None,
            )
        )
        for child in nested:
            if child.tag == "ol":
                self._parse_sense_list(child, entry_id, section, info, sense_id, depth + 1)
            elif child.tag == "dl":
                for dd in child.iter():
                    if dd.tag == "dd":
                        self._add_sense_detail(dd, entry_id, section, sense_id)
            elif child.tag == "ul":
                for item in child.iter():
                    if item.tag == "li":
                        self._add_sense_detail(item, entry_id, section, sense_id)
        return 1

    def _next_sense_ordinal(self, section_id: int, parent: int | None) -> int:
        key = f"sense-{section_id}-{parent}"
        counters = self.ids._counters
        counters[key] += 1
        return counters[key]

    def _add_sense_detail(
        self,
        node: LexborNode,
        entry_id: int,
        section: _Section,
        sense_id: int,
    ) -> None:
        if node.css_first(".benimune") is not None and node.css_first(".e-example") is None:
            return
        citation = node.css_first(".citation-whole")
        if citation is not None:
            self._add_quotation(citation, entry_id, section, sense_id)
            return
        nyms = node.css_first(".nyms")
        if nyms is not None:
            self._add_sense_nyms(nyms, entry_id, section, sense_id)
            return
        usage = node.css_first(".h-usage-example")
        if usage is not None:
            example = _text(usage.css_first(".e-example")) or _text(usage)
            self._add_example(
                entry_id,
                sense_id,
                example,
                _text(usage.css_first(".e-translation")) or None,
                _text(usage.css_first(".e-transliteration")) or None,
            )
            return
        text = clean_text(_own_text(node))
        if text:
            self._add_example(entry_id, sense_id, text, None, None)

    def _add_example(
        self,
        entry_id: int,
        sense_id: int,
        text: str,
        translation: str | None,
        transliteration: str | None,
    ) -> None:
        self.rows["examples"].append(
            (self.ids.next("examples"), entry_id, sense_id, text, translation, transliteration)
        )

    def _add_sense_nyms(
        self,
        nyms: LexborNode,
        entry_id: int,
        section: _Section,
        sense_id: int,
    ) -> None:
        classes = _classes(nyms) - {"nyms"}
        heading = next(iter(classes), "")
        kind = classify_heading(heading, 4).kind
        relation = kind if kind in RELATION_TYPES else "other"
        for span in nyms.css("span[lang]"):
            link = span.css_first("a")
            self._add_relation(
                entry_id,
                section.section_id,
                sense_id,
                relation,
                _text(span),
                link_target(link.attributes.get("href")) if link else None,
                None,
            )

    def _add_relation(
        self,
        entry_id: int,
        section_id: int,
        sense_id: int | None,
        relation: str,
        term: str,
        target: str | None,
        qualifier: str | None,
    ) -> None:
        if not term:
            return
        self.rows["relations"].append(
            (
                self.ids.next("relations"),
                entry_id,
                section_id,
                sense_id,
                relation,
                term,
                target,
                qualifier,
            )
        )

    # ---- quotations ------------------------------------------------------------------------

    def _add_quotation(
        self,
        citation: LexborNode,
        entry_id: int,
        section: _Section,
        sense_id: int | None,
    ) -> None:
        source = citation.css_first(".cited-source")
        source_text = _text(source)
        year_match = _YEAR.search(source_text)
        authors = source.css(".j-pewist") if source is not None else []
        author = _text(authors[1]) if len(authors) > 1 else None
        self.rows["quotations"].append(
            (
                self.ids.next("quotations"),
                entry_id,
                section.section_id,
                sense_id,
                year_match.group(1) if year_match else None,
                author or None,
                _text(citation.css_first("cite")) or None,
                source_text.rstrip(":") or None,
                _text(citation.css_first(".cited-passage")) or _text(citation),
                _text(citation.css_first(".e-transliteration")) or None,
                _text(citation.css_first(".e-translation")) or None,
            )
        )

    def _parse_quotation_section(self, root: LexborNode, entry_id: int, section: _Section) -> None:
        citations = root.css(".citation-whole")
        for citation in citations:
            self._add_quotation(citation, entry_id, section, None)
        if citations:
            return
        for item in root.css("li, dd, p"):
            text = clean_text(_own_text(item))
            if text:
                self.rows["quotations"].append(
                    (
                        self.ids.next("quotations"),
                        entry_id,
                        section.section_id,
                        None,
                        None,
                        None,
                        None,
                        None,
                        text,
                        None,
                        None,
                    )
                )

    # ---- pronunciation ---------------------------------------------------------------------

    def _parse_pronunciation(
        self,
        root: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
    ) -> None:
        items = root.css("li") or root.css("p, dd")
        for item in items:
            qualifier = ", ".join(_text(n) for n in item.css(_QUALIFIER_SELECTOR)) or None
            ipas = item.css(".IPA")
            audio = item.css('a[href*="upload.wikimedia.org"]')
            for ipa in ipas:
                value = _text(ipa)
                if value:
                    info["ipa"] = True
                    self._add_pron(entry_id, section, "ipa", value, qualifier, None)
            for link in audio:
                href = (link.attributes.get("href") or "").strip()
                if href.startswith("//"):
                    href = f"https:{href}"
                info["audio"] = True
                self._add_pron(
                    entry_id,
                    section,
                    "audio",
                    commons_file_from_url(href) or href,
                    qualifier,
                    media_id_for(href),
                )
            if ipas or audio:
                continue
            text = clean_text(_own_text(item))
            if not text:
                continue
            label, sep, value = text.partition(":")
            folded = label.strip().casefold()
            if sep and "kîte" in folded:
                self._add_pron(entry_id, section, "syllabification", value.strip(), qualifier, None)
            elif sep and "qafiye" in folded:
                self._add_pron(entry_id, section, "rhyme", value.strip(), qualifier, None)
            else:
                self._add_pron(entry_id, section, "other", text, qualifier, None)

    def _add_pron(
        self,
        entry_id: int,
        section: _Section,
        kind: str,
        value: str,
        qualifier: str | None,
        media_id: str | None,
    ) -> None:
        self.rows["pronunciations"].append(
            (
                self.ids.next("pronunciations"),
                entry_id,
                section.section_id,
                kind,
                value,
                qualifier,
                media_id,
            )
        )

    # ---- etymology -------------------------------------------------------------------------

    def _parse_etymology(
        self,
        root: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
        text: str,
    ) -> None:
        if not text:
            return
        info["etymology"] = True
        terms = [
            target
            for target in (link_target(a.attributes.get("href")) for a in root.css("a"))
            if target
        ]
        self.rows["etymologies"].append(
            (
                self.ids.next("etymologies"),
                entry_id,
                section.section_id,
                text,
                json.dumps(list(dict.fromkeys(terms)), ensure_ascii=False) if terms else None,
            )
        )

    # ---- translations ----------------------------------------------------------------------

    def _parse_translations(
        self,
        root: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
    ) -> None:
        frames = root.css(".NavFrame") or [root]
        for frame in frames:
            gloss = _text(frame.css_first(".NavHead")) or None
            for item in frame.css("li"):
                self._add_translation_item(item, entry_id, section, info, gloss)

    def _add_translation_item(
        self,
        item: LexborNode,
        entry_id: int,
        section: _Section,
        info: dict[str, Any],
        gloss: str | None,
    ) -> None:
        language: str | None = None
        code: str | None = None
        terms: list[LexborNode] = []
        for node in _own_nodes(item):
            classes = _classes(node)
            label = next((c for c in classes if c.startswith("trad-")), None)
            if label and language is None:
                language = _text(node)
                code = label.removeprefix("trad-")
            elif node.attributes.get("lang") and node.tag == "span":
                terms.append(node)
        if language is None:
            language = clean_text(_own_text(item).split(":", 1)[0])[:80] or None
        gender_nodes = [n for n in _own_nodes(item) if "gender" in _classes(n)]
        gender = _text(gender_nodes[0]) if len(gender_nodes) == 1 else None
        transliteration = [n for n in _own_nodes(item) if "tr" in _classes(n)]
        translit_text = _text(transliteration[0]) if len(transliteration) == 1 else None
        for term in terms:
            if "tr" in _classes(term):
                continue
            value = _text(term)
            if not value:
                continue
            link = term.css_first("a")
            info["translations"] = True
            self.rows["translations"].append(
                (
                    self.ids.next("translations"),
                    entry_id,
                    section.section_id,
                    gloss,
                    language,
                    code or term.attributes.get("lang"),
                    value,
                    link_target(link.attributes.get("href")) if link else None,
                    translit_text,
                    gender,
                )
            )

    # ---- relations -------------------------------------------------------------------------

    def _parse_relations(
        self,
        root: LexborNode,
        entry_id: int,
        section: _Section,
        relation: str,
    ) -> None:
        items = root.css("li, dd")
        if not items:
            items = root.css("p")
        for item in items:
            qualifier = ", ".join(
                _text(n)
                for n in _own_nodes(item)
                if _classes(n) & {"qualifier-content", "label-content"}
            )
            spans = [n for n in _own_nodes(item) if n.tag == "span" and n.attributes.get("lang")]
            if relation == "other_scripts" and len(spans) > 1:
                # ``kurdî-erebî: هه‌ڤال`` -> the first span names the script.
                qualifier = _text(spans[0])
                spans = spans[1:]
            if spans:
                for span in spans:
                    link = span.css_first("a")
                    self._add_relation(
                        entry_id,
                        section.section_id,
                        None,
                        relation,
                        _text(span),
                        link_target(link.attributes.get("href")) if link else None,
                        qualifier or None,
                    )
                continue
            links = [
                n
                for n in _own_nodes(item)
                if n.tag == "a" and link_target(n.attributes.get("href"))
            ]
            if links:
                for link in links:
                    self._add_relation(
                        entry_id,
                        section.section_id,
                        None,
                        relation,
                        _text(link),
                        link_target(link.attributes.get("href")),
                        qualifier or None,
                    )
                continue
            self._add_relation(
                entry_id,
                section.section_id,
                None,
                relation,
                clean_text(_own_text(item)),
                None,
                qualifier or None,
            )


def _int(value: str | None) -> int | None:
    try:
        return int(value) if value else None
    except ValueError:
        return None


def _own_links(node: LexborNode) -> list[str]:
    targets = [link_target(n.attributes.get("href")) for n in _own_nodes(node) if n.tag == "a"]
    return list(dict.fromkeys(t for t in targets if t))


# Grid cell: (is_header, text, link target, is the span origin)
_Cell = tuple[bool, str, str | None, bool]


def _table_grid(table: LexborNode) -> list[list[_Cell]]:
    """Expand rowspan/colspan into a rectangular grid."""
    grid: list[list[_Cell]] = []
    pending: dict[tuple[int, int], _Cell] = {}
    rows = [r for r in table.css("tr")]
    for r_index, row in enumerate(rows):
        cells: list[_Cell] = []
        column = 0
        for cell in row.iter():
            if cell.tag not in ("td", "th"):
                continue
            while (r_index, column) in pending:
                cells.append(pending[(r_index, column)])
                column += 1
            text = _text(cell)
            link = cell.css_first("a")
            target = link_target(link.attributes.get("href")) if link else None
            colspan = _int(cell.attributes.get("colspan")) or 1
            rowspan = _int(cell.attributes.get("rowspan")) or 1
            is_header = cell.tag == "th"
            origin: _Cell = (is_header, text, target, True)
            copy: _Cell = (is_header, text, target, False)
            for offset in range(min(colspan, 100)):
                cells.append(origin if offset == 0 else copy)
                for down in range(1, min(rowspan, 100)):
                    pending[(r_index + down, column + offset)] = copy
            column += colspan
        while (r_index, column) in pending:
            cells.append(pending[(r_index, column)])
            column += 1
        grid.append(cells)
    return [row for row in grid if row]


def _table_forms(
    grid: list[list[_Cell]],
    width: int,
) -> Iterator[tuple[str | None, str | None, str | None, str, str | None]]:
    """Yield (row header, column header, group header, form, link) per data cell."""
    full_rows = {
        index
        for index, row in enumerate(grid)
        if len(row) == width and width > 1 and all(c[0] and c[1] == row[0][1] for c in row)
    }
    for r_index, row in enumerate(grid):
        for c_index, cell in enumerate(row):
            if cell[0] or not cell[3]:
                continue
            form = cell[1]
            if not form or form in {"-", "—", "–"}:
                continue
            row_header = next(
                (row[i][1] for i in range(c_index - 1, -1, -1) if row[i][0] and row[i][1]),
                None,
            )
            col_header = None
            group = None
            for above in range(r_index - 1, -1, -1):
                candidates = grid[above]
                if c_index >= len(candidates):
                    continue
                head = candidates[c_index]
                if not head[0] or not head[1]:
                    continue
                if above in full_rows:
                    group = head[1]
                    break
                if col_header is None:
                    col_header = head[1]
            yield row_header, col_header, group, form, cell[2]
