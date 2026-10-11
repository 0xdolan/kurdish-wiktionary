"""Sanitize Wiktionary HTML fragments for MDict embedding."""

from __future__ import annotations

import re

_SCRIPT_STYLE = re.compile(r"<script\b[^>]*>.*?</script>", re.I | re.DOTALL)
_STYLE = re.compile(r"<style\b[^>]*>.*?</style>", re.I | re.DOTALL)
_ONCLICK = re.compile(r"\s+on\w+\s*=\s*[\"'][^\"']*[\"']", re.I)
_COLLAPSE_CLASSES = frozenset(
    {
        "inflection-table-collapsed",
        "inflection-table-collapsible",
        "no-vc",
    }
)


def _unwrap_body_fragment(html: str) -> str:
    stripped = _SCRIPT_STYLE.sub("", html).strip()
    stripped = _STYLE.sub("", stripped)
    body_match = re.search(r"<body[^>]*>(.*)</body>", stripped, re.I | re.DOTALL)
    if body_match:
        return body_match.group(1).strip()
    stripped = re.sub(r"^<html[^>]*>", "", stripped, count=1, flags=re.I)
    stripped = re.sub(r"</html>\s*$", "", stripped, count=1, flags=re.I)
    stripped = re.sub(r"^<head[^>]*>.*?</head>\s*", "", stripped, count=1, flags=re.I | re.DOTALL)
    stripped = re.sub(r"^<body[^>]*>", "", stripped, count=1, flags=re.I)
    stripped = re.sub(r"</body>\s*$", "", stripped, count=1, flags=re.I)
    return stripped.strip()


def _normalize_class_list(class_value: str, *, extra: str = "") -> str:
    classes = [c for c in class_value.split() if c and c not in _COLLAPSE_CLASSES]
    if extra and extra not in classes:
        classes.append(extra)
    return " ".join(classes)


def _rewrite_class_attr(match: re.Match[str], *, extra: str) -> str:
    normalized = _normalize_class_list(match.group(1), extra=extra)
    return f'class="{normalized}"'


def rewrite_wiktionary_links(html: str) -> str:
    """Turn in-wiki anchors into ``entry://`` links for MDict."""
    if not html.strip():
        return ""
    out = re.sub(
        r"<a\b[^>]*\bclass=\"[^\"]*(?:extiw|external)[^\"]*\"[^>]*>(.*?)</a>",
        r"\1",
        html,
        flags=re.I | re.DOTALL,
    )

    def _fix_anchor(match: re.Match[str]) -> str:
        tag = match.group(0)
        href_match = re.search(r'\bhref="([^"]*)"', tag)
        if not href_match:
            return tag
        href = href_match.group(1).strip()
        if not href or href.startswith("#") or href.startswith("entry://"):
            return tag
        if href.startswith("http://") or href.startswith("https://") or href.startswith("//"):
            return tag
        if "action=edit" in tag:
            return ""
        title_match = re.search(r'\btitle="([^"]*)"', tag)
        label = (title_match.group(1) if title_match else href.split("#", 1)[0]).strip()
        if not label or label.startswith("Category:"):
            return tag
        tag = re.sub(r'\bhref="[^"]*"', f'href="entry://{label}"', tag, count=1)
        if "wikt-xref" not in tag:
            if re.search(r'\bclass="', tag):
                tag = re.sub(
                    r'\bclass="([^"]*)"',
                    lambda m: f'class="{m.group(1)} wikt-xref"',
                    tag,
                    count=1,
                )
            else:
                tag = tag.replace("<a ", '<a class="wikt-xref" ', 1)
        return tag

    return re.sub(r"<a\b[^>]*>.*?</a>", _fix_anchor, out, flags=re.I | re.DOTALL)


_ARABIC_SPAN = re.compile(
    r"(<span\b(?=[^>]*\bclass=\"[^\"]*\bArab\b)[^>]*)(>)",
    re.I,
)


def _mark_arabic_script_spans(html: str) -> str:
    """Ensure RTL + hook class on Wiktionary ``span.Arab`` / ``*-Arab`` markup."""

    def _inject(match: re.Match[str]) -> str:
        opening = match.group(1)
        if "wikt-script-arabic" not in opening:
            opening = re.sub(
                r'\bclass="([^"]*)"',
                lambda m: f'class="{m.group(1)} wikt-script-arabic"',
                opening,
                count=1,
            )
        if 'dir="' not in opening:
            opening += ' dir="rtl"'
        return opening + match.group(2)

    if "Arab" not in html:
        return html
    return _ARABIC_SPAN.sub(_inject, html)


_TPOS_SPAN = re.compile(
    r'<span\b[^>]*\bclass="[^"]*\btpos\b[^"]*"[^>]*>.*?</span>',
    re.I | re.DOTALL,
)


def _is_simple_latn_term_list(html: str) -> bool:
    if "term-list" in html or "translations" in html or "list-switcher" in html:
        return False
    if "Arab" in html or "citation-whole" in html:
        return False
    return bool(re.search(r"<li>\s*<span class=\"Latn\"", html))


def _prepare_term_link_lists(html: str) -> str:
    """Style synonyms / see-also / antonym ``ul`` lists as MDict chips."""
    if not _is_simple_latn_term_list(html) or "wikt-chip-list" in html:
        return html
    return re.sub(
        r"<ul>",
        '<ul class="wikt-term-list wikt-chip-list">',
        html,
        count=1,
    )


def _prepare_translations(html: str) -> str:
    """Normalize Werger / ``translations`` block for MDict CSS grid layout."""
    if "translations" not in html and "werger-content" not in html:
        return html
    out = re.sub(r'\s+style="[^"]*"', "", html)
    out = re.sub(
        r'<div class="NavHead">\s*(?:<i>\s*</i>)?\s*</div>\s*',
        "",
        out,
        flags=re.I,
    )
    out = _TPOS_SPAN.sub("", out)
    if 'class="translations wikt-translations"' not in out:
        out = out.replace('<div class="translations">', '<div class="translations wikt-translations">')
    out = re.sub(
        r'class="([^"]*\bwerger-content\b[^"]*)"',
        lambda m: _rewrite_class_attr(m, extra="wikt-translations-frame"),
        out,
    )
    out = re.sub(
        r'class="NavContent"',
        'class="NavContent wikt-translations-body"',
        out,
        count=1,
    )
    return out


def _looks_like_prose_etymology(html: str) -> bool:
    blocked = (
        "translations",
        "term-list",
        "inflection-table",
        "list-switcher",
        "<ul",
        "<table",
    )
    if any(token in html for token in blocked):
        return False
    return "<p" in html


def _prepare_etymology(html: str) -> str:
    """Apply ``wikt-etymology`` panel class to etymology ``<p>`` blocks."""
    if not _looks_like_prose_etymology(html) or "wikt-etymology" in html:
        return html

    def _tag_p(match: re.Match[str]) -> str:
        opening = match.group(0)
        if "class=" in opening:
            return re.sub(
                r'\bclass="([^"]*)"',
                lambda m: f'class="{m.group(1)} wikt-etymology"',
                opening,
                count=1,
            )
        return '<p class="wikt-etymology">'

    return re.sub(r"<p\b[^>]*>", _tag_p, html)


def _prepare_derived_terms(html: str) -> str:
    if "term-list" not in html and "list-switcher" not in html:
        return html
    out = re.sub(r'\s+style="[^"]*"', "", html)
    out = re.sub(
        r'class="([^"]*\blist-switcher-wrapper\b[^"]*)"',
        lambda m: _rewrite_class_attr(m, extra="wikt-derived-wrap"),
        out,
    )
    out = re.sub(
        r'class="([^"]*\bterm-list\b[^"]*)"',
        lambda m: _rewrite_class_attr(m, extra="wikt-derived-grid"),
        out,
    )
    out = re.sub(
        r'(<div[^>]*\bwikt-derived-grid\b[^>]*>\s*)<ul>',
        r'\1<ul class="wikt-derived-list wikt-chip-list">',
        out,
        count=1,
        flags=re.I | re.DOTALL,
    )
    return _tag_derived_list_items(out)


_DERIVED_LI = re.compile(r"<li>(.*?)</li>", re.I | re.DOTALL)
_DERIVED_QUALIFIER = re.compile(
    r'<span[^>]*\bqualifier-brac\b[^>]*>[^<]*</span>\s*'
    r'<span[^>]*\bqualifier-content\b[^>]*>([^<]+)</span>\s*'
    r'<span[^>]*\bqualifier-brac\b[^>]*>[^<]*</span>\s*',
    re.I,
)


def _normalize_derived_item_inner(inner: str) -> tuple[str, str | None]:
    pos_match = _DERIVED_QUALIFIER.search(inner)
    if not pos_match:
        return inner.strip(), None
    pos = pos_match.group(1).strip().replace('"', "")
    rest = _DERIVED_QUALIFIER.sub("", inner, count=1).strip()
    pos_span = f'<span class="wikt-derived-pos">{pos}</span>'
    return f"{pos_span} {rest}".strip(), pos


def _tag_derived_list_items(html: str) -> str:
    if "wikt-derived-list" not in html:
        return html

    def _li(match: re.Match[str]) -> str:
        inner, pos = _normalize_derived_item_inner(match.group(1))
        if pos:
            return (
                f'<li class="wikt-derived-item wikt-derived-item--tagged" '
                f'data-pos="{pos}">{inner}</li>'
            )
        return f'<li class="wikt-derived-item">{inner}</li>'

    return _DERIVED_LI.sub(_li, html)


def _is_alt_script_section(html: str) -> bool:
    return "Arab" in html and "term-list" not in html and "translations" not in html


def _prepare_alt_script_list(html: str) -> str:
    if not _is_alt_script_section(html) or "wikt-alt-script-list" in html:
        return html
    return re.sub(r"<ul>", '<ul class="wikt-alt-script-list">', html, count=1)


def _prepare_citations(html: str) -> str:
    if "citation-whole" not in html:
        return html
    out = re.sub(
        r'\bclass="citation-whole"',
        'class="citation-whole wikt-citation"',
        html,
    )
    out = re.sub(
        r'(<ul[^>]*>\s*)<li>\s*(<div class="citation-whole)',
        r'\1<li class="wikt-citation-item">\2',
        out,
        count=1,
        flags=re.I | re.DOTALL,
    )
    return out


def _prepare_inflection_tables(html: str) -> str:
    """Drop Wiktionary-only collapse hooks; tag wrappers for MDict CSS."""
    if "inflection-table" not in html:
        return html
    out = re.sub(r'\s+style="[^"]*"', "", html)
    out = re.sub(
        r'class="([^"]*\binflection-table-wrapper\b[^"]*)"',
        lambda m: _rewrite_class_attr(m, extra="wikt-inflection-wrap"),
        out,
    )
    out = re.sub(
        r'(<table\b[^>]*\s)class="([^"]*\binflection-table\b[^"]*)"',
        lambda m: (
            f'{m.group(1)}class="{_normalize_class_list(m.group(2), extra="wikt-inflection-table")}"'
        ),
        out,
        flags=re.I,
    )
    return out


def sanitize_section_html(html: str) -> str:
    raw = _SCRIPT_STYLE.sub("", html)
    raw = _STYLE.sub("", raw)
    raw = _ONCLICK.sub("", raw)
    linked = rewrite_wiktionary_links(raw)
    prepared = _prepare_inflection_tables(linked)
    translated = _prepare_translations(prepared)
    derived = _prepare_derived_terms(translated)
    alt = _prepare_alt_script_list(derived)
    terms = _prepare_term_link_lists(alt)
    citations = _prepare_citations(terms)
    etymology = _prepare_etymology(citations)
    rtl = _mark_arabic_script_spans(etymology)
    return _unwrap_body_fragment(rtl)
