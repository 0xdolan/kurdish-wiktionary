from html import escape

from src.core.models import WiktionaryEntry


def render_entry_html(entry: WiktionaryEntry) -> str:
    parts: list[str] = [
        '<div class="wikt-entry">',
        f'<h1 class="wikt-headword">{escape(entry.entry)}</h1>',
    ]

    if entry.phonetic_transcriptions or entry.pronunciations:
        ipa = ", ".join(entry.phonetic_transcriptions + entry.pronunciations)
        parts.append(f'<p class="wikt-pronunciation">{escape(ipa)}</p>')

    if entry.part_of_speech:
        pos = ", ".join(entry.part_of_speech)
        parts.append(f'<p class="wikt-pos"><em>{escape(pos)}</em></p>')

    if entry.definitions:
        parts.append('<ol class="wikt-definitions">')
        for definition in entry.definitions:
            parts.append(f"<li>{escape(definition)}</li>")
        parts.append("</ol>")

    if entry.examples:
        parts.append('<ul class="wikt-examples">')
        for example in entry.examples:
            parts.append(f"<li>{escape(example)}</li>")
        parts.append("</ul>")

    if entry.synonyms:
        syns = ", ".join(entry.synonyms)
        parts.append(f'<p class="wikt-synonyms"><strong>Synonyms:</strong> {escape(syns)}</p>')

    if entry.antonyms:
        ants = ", ".join(entry.antonyms)
        parts.append(f'<p class="wikt-antonyms"><strong>Antonyms:</strong> {escape(ants)}</p>')

    if entry.etymology:
        parts.append(f'<p class="wikt-etymology">{escape(entry.etymology)}</p>')

    if entry.derived_terms:
        derived = ", ".join(entry.derived_terms)
        parts.append(
            f'<p class="wikt-derived"><strong>Derived:</strong> {escape(derived)}</p>'
        )

    parts.append("</div>")
    return "".join(parts)
