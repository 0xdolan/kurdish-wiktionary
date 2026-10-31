"""Classify Wîkîferheng headings into stable section types.

Headings are free text typed by editors (``Bide ber``, ``Bideber``, ``Bibe ber``), so every
heading is normalized and mapped to one English ``section_type``. The original heading is always
kept in the data; anything unknown becomes ``other`` and is counted in the quality report.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Sections that hold dictionary senses: heading -> part of speech.
POS_HEADINGS: dict[str, str] = {
    "navder": "noun",
    "formeke navdere": "noun_form",
    "serenav": "proper_noun",
    "formeke serenave": "proper_noun_form",
    "leker": "verb",
    "formeke lekere": "verb_form",
    "reheki lekere": "verb_root",
    "reh": "root",
    "rengder": "adjective",
    "formeke rengdere": "adjective_form",
    "hoker": "adverb",
    "formeke hokere": "adverb_form",
    "biwej": "idiom",
    "gotineke pesiyan": "proverb",
    "hejmar": "numeral",
    "cinav": "pronoun",
    "formeke cinave": "pronoun_form",
    "dacek": "adposition",
    "pesdacek": "preposition",
    "pasdacek": "postposition",
    "bazinedacek": "circumposition",
    "pasgir": "suffix",
    "pesgir": "prefix",
    "navgir": "infix",
    "banesan": "interjection",
    "giredek": "conjunction",
    "pirtik": "particle",
    "kurtenav": "abbreviation",
    "kurte": "short_form",
    "tip": "letter",
    "sembol": "symbol",
    "hevok": "phrase",
    "ifade": "expression",
    "reheke lekere": "verb_root",
    "wate": "sense",
    "partisip": "participle",
    "partisip i": "participle",
    "partisip ii": "participle",
    "artikel": "article",
    "mane": "sense",
    "واته": "sense",
}

# Everything else: heading -> section type. Types map to a typed table in ``schema.py``.
SECTION_HEADINGS: dict[str, str] = {
    "bilevkirin": "pronunciation",
    "pronunciation": "pronunciation",
    "dengnasi": "pronunciation",
    "jorpeyv": "hypernyms",
    "agahdari": "usage_notes",
    "agahi": "usage_notes",
    "not": "usage_notes",
    "nise": "usage_notes",
    "herwisa": "see_also",
    "herwhia": "see_also",
    "biner": "see_also",
    "bide": "compare",
    "tekilidar": "related_terms",
    "peyven eleqedar": "related_terms",
    "nave ilmi": "scientific_names",
    "ji wejeya dini": "quotations",
    "bi nivisen din": "other_scripts",
    "bi tipen erebi": "other_scripts",
    "romanizekirin": "other_scripts",
    "peyven jecekiri": "derived_terms",
    "neziki": "near_synonyms",
    "jeder": "references",
    "pirhejmar": "plural_forms",
    "tabloya tewandine": "inflection",
    "etimoloji": "etymology",
    "etimoloj": "etymology",
    "werger": "translations",
    "tewandin": "inflection",
    "tewin": "inflection",
    "tewandi": "inflection",
    "formen alternativ": "alternative_forms",
    "nivisen alternatif": "alternative_forms",
    "bi alfabeyen din": "other_scripts",
    "bi tipen din": "other_scripts",
    "bi zaravayen din": "dialect_forms",
    "bi zaravayen kurdi": "dialect_forms",
    "bi sorani": "dialect_forms",
    "je": "derived_terms",
    "tekildar": "related_terms",
    "tekili": "related_terms",
    "tekildari": "related_terms",
    "bide ber": "compare",
    "bideber": "compare",
    "bibe ber": "compare",
    "bidin ber": "compare",
    "binere herwiha": "see_also",
    "herwiha binere": "see_also",
    "binere": "see_also",
    "bibine": "see_also",
    "herwiha": "see_also",
    "her wiha": "see_also",
    "herweha": "see_also",
    "hevmane": "synonyms",
    "hevwate": "synonyms",
    "nezik": "near_synonyms",
    "dijmane": "antonyms",
    "jornav": "hypernyms",
    "jernav": "hyponyms",
    "meronim": "meronyms",
    "dunde": "descendants",
    "anagram": "anagrams",
    "qafiye": "rhymes",
    "nave zanisti": "scientific_names",
    "bikaranin": "usage_notes",
    "noten bikaranine": "usage_notes",
    "agadari": "usage_notes",
    "ji wejeye": "quotations",
    "ji wejeya klasik": "quotations",
    "cavkani": "references",
    "zedetir hin bibe": "further_reading",
    "behtir xwendin": "further_reading",
    "behtir bixwine": "further_reading",
    "gotinen pesiyan": "proverbs",
    "pirepend": "proverbs",
    "pend": "proverbs",
    "bernav": "epithets",
    "bergend": "paraphrases",
    "peyv bi peyv": "word_by_word",
    "pirjimar": "plural_forms",
    "pirrjimar": "plural_forms",
    "yekjimar": "singular_forms",
    "minak": "examples",
    "nimune": "examples",
}

# Sections whose list items become rows in ``relations`` (section_type is the relation type).
RELATION_TYPES: frozenset[str] = frozenset(
    {
        "alternative_forms",
        "other_scripts",
        "dialect_forms",
        "derived_terms",
        "related_terms",
        "compare",
        "see_also",
        "synonyms",
        "near_synonyms",
        "antonyms",
        "hypernyms",
        "hyponyms",
        "meronyms",
        "descendants",
        "anagrams",
        "rhymes",
        "scientific_names",
        "proverbs",
        "idioms",
        "epithets",
        "paraphrases",
        "plural_forms",
        "singular_forms",
    }
)

# Human labels for docs, Excel sheets and the dictionary UI: type -> (Kurmancî, English).
SECTION_LABELS: dict[str, tuple[str, str]] = {
    "pos": ("Beşê axaftinê", "Part of speech"),
    "pronunciation": ("Bilêvkirin", "Pronunciation"),
    "etymology": ("Etîmolojî", "Etymology"),
    "translations": ("Werger", "Translations"),
    "inflection": ("Tewandin", "Inflection"),
    "alternative_forms": ("Formên alternatîv", "Alternative forms"),
    "other_scripts": ("Bi alfabeyên din", "Other scripts"),
    "dialect_forms": ("Bi zaravayên din", "Dialect forms"),
    "derived_terms": ("Jê", "Derived terms"),
    "related_terms": ("Têkildar", "Related terms"),
    "compare": ("Bide ber", "Compare"),
    "see_also": ("Binêre herwiha", "See also"),
    "synonyms": ("Hevmane", "Synonyms"),
    "near_synonyms": ("Nêzîk", "Near synonyms"),
    "antonyms": ("Dijmane", "Antonyms"),
    "hypernyms": ("Jornav", "Hypernyms"),
    "hyponyms": ("Jêrnav", "Hyponyms"),
    "meronyms": ("Meronîm", "Meronyms"),
    "descendants": ("Dûnde", "Descendants"),
    "anagrams": ("Anagram", "Anagrams"),
    "rhymes": ("Qafiye", "Rhymes"),
    "scientific_names": ("Navê zanistî", "Scientific names"),
    "usage_notes": ("Bikaranîn", "Usage notes"),
    "quotations": ("Ji wêjeyê", "Quotations"),
    "references": ("Çavkanî", "References"),
    "further_reading": ("Zêdetir hîn bibe", "Further reading"),
    "proverbs": ("Gotinên pêşiyan", "Proverbs"),
    "idioms": ("Biwêj", "Idioms"),
    "epithets": ("Bernav", "Epithets"),
    "paraphrases": ("Bergend", "Paraphrases"),
    "word_by_word": ("Peyv bi peyv", "Word by word"),
    "plural_forms": ("Pirjimar", "Plural forms"),
    "singular_forms": ("Yekjimar", "Singular forms"),
    "examples": ("Nimûne", "Examples"),
    "other": ("Yên din", "Other"),
}

POS_LABELS: dict[str, tuple[str, str]] = {
    "noun": ("Navdêr", "Noun"),
    "noun_form": ("Formeke navdêrê", "Noun form"),
    "proper_noun": ("Serenav", "Proper noun"),
    "proper_noun_form": ("Formeke serenavê", "Proper noun form"),
    "verb": ("Lêker", "Verb"),
    "verb_form": ("Formeke lêkerê", "Verb form"),
    "verb_root": ("Rehekî lêkerê", "Verb root"),
    "root": ("Reh", "Root"),
    "adjective": ("Rengdêr", "Adjective"),
    "adjective_form": ("Formeke rengdêrê", "Adjective form"),
    "adverb": ("Hoker", "Adverb"),
    "adverb_form": ("Formeke hokerê", "Adverb form"),
    "idiom": ("Biwêj", "Idiom"),
    "proverb": ("Gotineke pêşiyan", "Proverb"),
    "numeral": ("Hejmar", "Numeral"),
    "pronoun": ("Cînav", "Pronoun"),
    "pronoun_form": ("Formeke cînavê", "Pronoun form"),
    "adposition": ("Daçek", "Adposition"),
    "preposition": ("Pêşdaçek", "Preposition"),
    "postposition": ("Paşdaçek", "Postposition"),
    "circumposition": ("Bazinedaçek", "Circumposition"),
    "suffix": ("Paşgir", "Suffix"),
    "prefix": ("Pêşgir", "Prefix"),
    "infix": ("Navgir", "Infix"),
    "interjection": ("Baneşan", "Interjection"),
    "conjunction": ("Girêdek", "Conjunction"),
    "particle": ("Pirtik", "Particle"),
    "abbreviation": ("Kurtenav", "Abbreviation"),
    "short_form": ("Kurte", "Short form"),
    "letter": ("Tîp", "Letter"),
    "symbol": ("Sembol", "Symbol"),
    "phrase": ("Hevok", "Phrase"),
    "expression": ("Îfade", "Expression"),
    "participle": ("Partîsîp", "Participle"),
    "article": ("Artîkel", "Article"),
    "sense": ("Mane", "Sense (no part of speech given)"),
}

_TRAILING_NUMBER = re.compile(r"\s+(\d{1,2})$")
_INVISIBLE = re.compile(r"[​-‏‪-‮⁠﻿]")
_SPACES = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class Classified:
    """``kind`` is ``pos`` or the section type; ``homograph`` is N from ``Navdêr N``."""

    kind: str
    pos: str | None
    homograph: int | None


def normalize_heading(heading: str) -> str:
    """Casefold, drop diacritics and invisible marks: ``Bilêvkirin`` -> ``bilevkirin``."""
    text = _INVISIBLE.sub("", heading)
    text = text.replace("ı", "i")
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    stripped = stripped.replace("ـ", "")
    # Arabic-script "wate" variants share a final form after this folding.
    stripped = stripped.replace("ە", "ه")
    stripped = stripped.strip(" :=\t\n").casefold()
    return _SPACES.sub(" ", stripped)


def classify_heading(heading: str, level: int) -> Classified:
    """Map a heading to its section type. ``level`` matters only for ``Biwêj`` (see below)."""
    key = normalize_heading(heading)
    homograph: int | None = None
    match = _TRAILING_NUMBER.search(key)
    if match:
        base = key[: match.start()]
        if base in POS_HEADINGS or base in SECTION_HEADINGS:
            key = base
            homograph = int(match.group(1))
    # An h3 ``Biwêj`` is an idiom entry with senses; an h4 one lists idioms using the word.
    if key == "biwej" and level >= 4:
        return Classified("idioms", None, homograph)
    if key in POS_HEADINGS:
        return Classified("pos", POS_HEADINGS[key], homograph)
    if key in SECTION_HEADINGS:
        return Classified(SECTION_HEADINGS[key], None, homograph)
    return Classified("other", None, homograph)
