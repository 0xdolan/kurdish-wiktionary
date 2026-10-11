from html import escape

from src.core.models import WiktionaryEntry
from src.mdict.html_sanitize import sanitize_section_html
from src.mdict.constants import SPEAKER_ICON_HREF
from src.mdict.section_labels import SECTION_HTML_ORDER, SECTION_TITLES, wrap_section

_SPEAKER_ICON = (
    f'<img class="wikt-speaker-img" src="{SPEAKER_ICON_HREF}" width="20" height="20" '
    f'alt="" />'
)


def render_cross_reference(display_text: str, headword: str) -> str:
    """MDict in-dictionary link (GoldenDict / MDict `entry://` scheme)."""
    target = headword.strip()
    return (
        f'<a class="wikt-xref" href="entry://{escape(target)}">'
        f"{escape(display_text)}</a>"
    )


def _render_lang_toggle() -> str:
    return (
        '<div class="wikt-sidebar-tools">'
        '<p class="wikt-lang-toggle">'
        '<span class="wikt-lang-toggle-heading">'
        '<span class="wikt-toggle-ku">Zimanê sernavan</span>'
        '<span class="wikt-toggle-en">Section titles</span>'
        "</span>"
        '<label class="wikt-lang-segment">'
        '<input type="checkbox" id="wikt-en-labels" class="wikt-lang-segment-input" />'
        '<span class="wikt-lang-segment-track">'
        '<span class="wikt-lang-segment-option wikt-lang-segment-option--ku">Kurdî</span>'
        '<span class="wikt-lang-segment-option wikt-lang-segment-option--en">English</span>'
        '<span class="wikt-lang-segment-thumb" aria-hidden="true"></span>'
        "</span>"
        "</label>"
        '<span class="wikt-lang-toggle-caption">'
        '<span class="wikt-toggle-ku">Sernavên bi Kurdî (Kurmancî)</span>'
        '<span class="wikt-toggle-en">English section titles</span>'
        "</span>"
        "</p>"
        "</div>"
    )


def _render_entry_sidebar() -> str:
    return (
        '<aside class="wikt-sidebar" aria-label="Entry navigation">'
        '<div class="wikt-sidebar-sticky">'
        f"{_render_lang_toggle()}"
        '<nav class="wikt-toc" aria-label="Sections">'
        '<div class="wikt-toc-header">'
        '<span class="wikt-toc-icon" aria-hidden="true"></span>'
        '<p class="wikt-toc-title">'
        '<span class="wikt-toc-title-ku">Naverok</span>'
        '<span class="wikt-toc-title-en">Contents</span>'
        "</p>"
        "</div>"
        '<div class="wikt-toc-scroll">'
        '<ul class="wikt-toc-list"></ul>'
        "</div>"
        "</nav>"
        "</div>"
        "</aside>"
    )


def _render_pos_badges(part_of_speech: list[str]) -> str:
    if not part_of_speech:
        return ""
    badges = "".join(f'<span class="wikt-pos">{escape(p)}</span>' for p in part_of_speech)
    return f'<div class="wikt-meta-row">{badges}</div>'


def _is_pronunciation_token(token: str) -> bool:
    stripped = token.strip()
    if not stripped:
        return False
    lower = stripped.casefold()
    if lower.startswith("http://") or lower.startswith("https://"):
        return False
    return "upload.wikimedia.org" not in lower and not lower.startswith("//")


def _audio_items(entry: WiktionaryEntry) -> list[dict]:
    raw = entry.metadata.get("mdict_media")
    if not isinstance(raw, list):
        return []
    return [m for m in raw if isinstance(m, dict) and m.get("kind") == "audio"]


def _image_items(entry: WiktionaryEntry) -> list[dict]:
    raw = entry.metadata.get("mdict_media")
    if not isinstance(raw, list):
        return []
    images = [m for m in raw if isinstance(m, dict) and m.get("kind") == "image"]
    photos = [
        m
        for m in images
        if ".jpg" in str(m.get("href", "")).casefold()
        or ".jpeg" in str(m.get("href", "")).casefold()
    ]
    return photos if photos else images[:1]


def _render_pronunciation_inner(entry: WiktionaryEntry) -> str:
    ipa_tokens = [
        t for t in entry.phonetic_transcriptions if _is_pronunciation_token(t)
    ]
    audio_items = _audio_items(entry)
    if not ipa_tokens and not audio_items:
        return ""

    parts: list[str] = ['<div class="wikt-pron-block">']
    if ipa_tokens:
        chips = "".join(f'<span class="wikt-ipa">{escape(t)}</span>' for t in ipa_tokens)
        parts.append(f'<div class="wikt-meta-row wikt-ipa-row">{chips}</div>')

    if audio_items:
        parts.append('<ul class="wikt-audio-list wikt-audio-list-compact">')
        for item in audio_items:
            href = str(item.get("href", "")).strip()
            if not href:
                continue
            label = str(item.get("label") or "Guhdar bike")
            parts.append(
                f'<li class="wikt-audio-item">'
                f'<span class="wikt-audio-label">{escape(label)}</span>'
                f'<button type="button" class="wikt-audio-btn" data-audio-src="{escape(href)}" '
                f'aria-label="{escape(label)}">{_SPEAKER_ICON}</button>'
                f"</li>"
            )
        parts.append("</ul>")
    parts.append("</div>")
    return "".join(parts)


def _render_thumbnails_inner(entry: WiktionaryEntry) -> str:
    blocks: list[str] = []
    for item in _image_items(entry):
        href = str(item.get("href", "")).strip()
        if not href:
            continue
        caption = str(item.get("caption") or item.get("label") or "").strip()
        alt = caption or entry.entry
        blocks.append(
            f'<figure class="wikt-thumb wikt-thumb-open" data-full-src="{escape(href)}">'
            f'<img class="wikt-thumb-img" src="{escape(href)}" '
            f'alt="{escape(alt)}" loading="lazy" />'
            f'<figcaption class="wikt-thumb-caption">{escape(caption)}</figcaption>'
            f"</figure>"
        )
    if not blocks:
        return ""
    return f'<div class="wikt-thumb-grid">{"".join(blocks)}</div>'


def _render_pronunciation_section(entry: WiktionaryEntry) -> str:
    pron = _render_pronunciation_inner(entry)
    if not pron:
        return ""
    return wrap_section("bilevkirin", pron)


def _render_illustrations_section(entry: WiktionaryEntry) -> str:
    visuals = _render_thumbnails_inner(entry)
    if not visuals:
        return ""
    return wrap_section("wêne", visuals)


def _render_chip_links(section_key: str, items: list[str]) -> str:
    if not items:
        return ""
    links = "".join(render_cross_reference(item, item) for item in items)
    return wrap_section(section_key, f'<p class="wikt-chip-list">{links}</p>')


def _render_navder(entry: WiktionaryEntry) -> str:
    if not entry.definitions:
        return ""
    lis = "".join(f"<li>{escape(d)}</li>" for d in entry.definitions)
    return wrap_section("navder", f'<ol class="wikt-definitions">{lis}</ol>')


def _render_examples(entry: WiktionaryEntry) -> str:
    if not entry.examples:
        return ""
    lis = "".join(f"<li>{escape(ex)}</li>" for ex in entry.examples)
    return wrap_section("nimune", f'<ul class="wikt-examples">{lis}</ul>')


def _section_html_map(entry: WiktionaryEntry) -> dict[str, str]:
    raw = entry.metadata.get("section_html")
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if v}


def _render_stored_sections(entry: WiktionaryEntry) -> str:
    sections = _section_html_map(entry)
    parts: list[str] = []
    rendered_keys: set[str] = set()

    for key in SECTION_HTML_ORDER:
        fragment = sections.get(key)
        if not fragment:
            continue
        safe = sanitize_section_html(fragment)
        if not safe.strip():
            continue
        css_key = key.replace(" ", "-")
        block = f'<div class="wikt-section-html wikt-section-{css_key}">{safe}</div>'
        parts.append(wrap_section(key, block))
        rendered_keys.add(key)

    chip_fallback = {
        "hevmane": entry.synonyms,
        "dijmane": entry.antonyms,
        "je": entry.derived_terms,
    }
    for key, items in chip_fallback.items():
        if key in rendered_keys or not items:
            continue
        parts.append(_render_chip_links(key, items))

    if "etimoloji" not in rendered_keys and entry.etymology:
        parts.append(
            wrap_section("etimoloji", f'<p class="wikt-etymology">{escape(entry.etymology)}</p>')
        )

    return "".join(parts)


def render_entry_html(entry: WiktionaryEntry) -> str:
    """Body fragment for one MDict article (stylesheet + script linked in txt_writer)."""
    head = escape(entry.entry)
    parts: list[str] = [
        '<article class="wikt-entry">',
        '<div class="wikt-entry-layout">',
        _render_entry_sidebar(),
        '<div class="wikt-entry-main">',
        '<header class="wikt-header" id="wikt-sec-head">',
        f'<h1 class="wikt-headword">{head}</h1>',
        _render_pos_badges(entry.part_of_speech),
        "</header>",
        _render_pronunciation_section(entry),
        _render_illustrations_section(entry),
        _render_navder(entry),
        _render_examples(entry),
        _render_stored_sections(entry),
    ]

    source = entry.metadata.get("zim_source") or entry.metadata.get("zim_path")
    if source:
        parts.append(f'<p class="wikt-footer-note">Source: {escape(str(source))}</p>')

    parts.extend(
        [
            "</div>",
            "</div>",
            '<div class="wikt-lightbox-root" aria-hidden="true"></div>',
            "</article>",
        ]
    )
    return "".join(parts)


def sample_brave_entry() -> WiktionaryEntry:
    """Reference entry for preview HTML and documentation (English demo lemma)."""
    return WiktionaryEntry(
        entry="brave",
        part_of_speech=["adjective", "verb"],
        phonetic_transcriptions=["/breɪv/"],
        pronunciations=["(US) enPR: brāv"],
        definitions=[
            "Strong in the face of fear; courageous.",
            "Having any sort of superiority or excellence, especially physical superiority.",
            "Making a fine show or display.",
        ],
        examples=[
            "After braving the elements, the hikers reached the summit.",
            "The brave knight stood between the dragon and the village.",
        ],
        synonyms=["courageous", "fearless", "bold"],
        antonyms=["cowardly", "timid"],
        etymology=(
            "From Middle English brave, from Old French brave, "
            "possibly from Proto-Italic *gʷrāwos."
        ),
        derived_terms=["bravery", "bravely", "braveness"],
        metadata={
            "conjugation": [
                ["", "Present", "Past"],
                ["I", "brave", "braved"],
                ["you", "brave", "braved"],
                ["he/she", "braves", "braved"],
            ],
            "zim_source": "preview — not from ZIM",
        },
    )
