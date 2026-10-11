"""Kurdish (default) and English section titles for MDict entries."""

from __future__ import annotations

# Normalized heading key → (Kurdish label, English label)
SECTION_TITLES: dict[str, tuple[str, str]] = {
    "bilevkirin": ("Bilêvkirin", "Pronunciation"),
    "navder": ("Navdêr", "Noun"),
    "peyv": ("Peyv", "Word"),
    "ji wejeya klasik": ("Ji wêjeya klasîk", "From classic literature"),
    "tewandin": ("Tewandin", "Declension"),
    "hevmane": ("Hevmane", "Synonyms"),
    "dijmane": ("Dijmane", "Antonyms"),
    "je": ("Jê", "Derived terms"),
    "etimoloji": ("Etîmolojî", "Etymology"),
    "bide ber": ("Bide ber", "See also"),
    "werger": ("Werger", "Translations"),
    "nimune": ("Nimûne", "Examples"),
    "wêne": ("Wêne", "Illustrations"),
    "wene": ("Wêne", "Illustrations"),
}

# Section HTML keys to render after main definitions (order matters).
SECTION_HTML_ORDER: tuple[str, ...] = (
    "ji wejeya klasik",
    "tewandin",
    "bi alfabeyen din",
    "hevmane",
    "dijmane",
    "je",
    "etimoloji",
    "bide ber",
    "werger",
)


def section_title(key: str, *, english: bool = False) -> str:
    ku, en = SECTION_TITLES.get(key, (key, key))
    return en if english else ku


def section_dom_id(key: str) -> str:
    return f"wikt-sec-{key.replace(' ', '-')}"


def render_section_fold_start(key: str) -> str:
    ku, en = SECTION_TITLES.get(key, (key.title(), key.title()))
    sec_id = section_dom_id(key)
    return (
        f'<details class="wikt-fold" open data-section-key="{key}" id="{sec_id}">'
        f'<summary class="wikt-section">'
        f'<span class="wikt-fold-chevron" aria-hidden="true"></span>'
        f'<span class="wikt-section-ku">{ku}</span>'
        f'<span class="wikt-section-en">{en}</span>'
        f"</summary>"
        f'<div class="wikt-fold-body">'
    )


def render_section_fold_end() -> str:
    return "</div></details>"


def wrap_section(key: str, body: str) -> str:
    content = body.strip()
    if not content:
        return ""
    return f"{render_section_fold_start(key)}{body}{render_section_fold_end()}"


def render_section_heading(key: str) -> str:
    """Summary-only marker (prefer :func:`wrap_section` for collapsible blocks)."""
    ku, en = SECTION_TITLES.get(key, (key.title(), key.title()))
    return (
        f'<summary class="wikt-section" data-section-key="{key}">'
        f'<span class="wikt-fold-chevron" aria-hidden="true"></span>'
        f'<span class="wikt-section-ku">{ku}</span>'
        f'<span class="wikt-section-en">{en}</span>'
        f"</summary>"
    )
