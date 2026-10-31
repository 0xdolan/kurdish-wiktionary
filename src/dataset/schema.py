"""Release schema: one registry drives DDL, exports and the generated data dictionary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Column:
    name: str
    sql_type: str
    description: str


@dataclass(frozen=True, slots=True)
class Table:
    name: str
    description: str
    columns: tuple[Column, ...]
    primary_key: str | None = None


def _c(name: str, sql_type: str, description: str) -> Column:
    return Column(name, sql_type, description)


ENTRY_FK = _c("entry_id", "BIGINT", "Foreign key to entries.entry_id")
SECTION_FK = _c("section_id", "BIGINT", "Foreign key to sections.section_id")

TABLES: tuple[Table, ...] = (
    Table(
        "pages",
        "One row per wiki page (ZIM article). A page holds one entry per language.",
        (
            _c("page_id", "BIGINT", "Build-specific page id. Not stable between releases"),
            _c("title", "TEXT", "Page title as shown on the wiki"),
            _c("page_kind", "TEXT", "entry, soft_redirect (a 'Binêre X' stub) or conjugation"),
            _c("source_zim", "TEXT", "ZIM flavour the page was read from: maxi or nopic"),
            _c("in_latest_dump", "INTEGER", "1 when the page exists in the newest ZIM"),
            _c("revision_id", "BIGINT", "MediaWiki revision (oldid) captured in the ZIM"),
            _c("last_edited", "TEXT", "Date of that revision (YYYY-MM-DD)"),
            _c("language_count", "INTEGER", "Number of language sections on the page"),
            _c("section_count", "INTEGER", "Number of headings on the page"),
            _c("url", "TEXT", "Live page on ku.wiktionary.org"),
        ),
        "page_id",
    ),
    Table(
        "redirects",
        "Alternative titles: 'hard' ZIM redirects and 'soft' 'Binêre X' stub pages.",
        (
            _c("alias", "TEXT", "Title that redirects"),
            _c("target", "TEXT", "Title it points to"),
            _c("redirect_kind", "TEXT", "hard or soft"),
        ),
    ),
    Table(
        "entries",
        "One row per page + language: the main lookup table of the dataset.",
        (
            _c("entry_id", "BIGINT", "Build-specific entry id. Not stable between releases"),
            _c("page_id", "BIGINT", "Foreign key to pages.page_id"),
            _c("ordinal", "INTEGER", "Position of the language section on the page"),
            _c("title", "TEXT", "The word: page title"),
            _c("language_name", "TEXT", "Language heading in Kurmancî (Îngilîzî, Tirkî, ...)"),
            _c("language_code", "TEXT", "Wiki language code; 'und' when the page gives none"),
            _c("entry_key", "TEXT", "title|language_code: use this key across releases"),
            _c("pos_list", "TEXT", "Comma-separated parts of speech found in the entry"),
            _c("sense_count", "INTEGER", "Rows in senses for this entry"),
            _c("has_ipa", "INTEGER", "1 when an IPA transcription exists"),
            _c("has_audio", "INTEGER", "1 when a pronunciation recording is linked"),
            _c("has_etymology", "INTEGER", "1 when an etymology section has text"),
            _c("has_translations", "INTEGER", "1 when translations were extracted"),
            _c(
                "is_auto_generated",
                "INTEGER",
                "1 when the wiki marks the entry as bot-made from a translation table; "
                "the wiki warns these may contain translation errors",
            ),
            _c("auto_source_page", "TEXT", "Translation page the bot entry was made from"),
            _c(
                "definition_pending",
                "INTEGER",
                "1 when the wiki shows 'the meaning is not written yet' instead of a definition",
            ),
        ),
        "entry_id",
    ),
    Table(
        "sections",
        "Every heading on every page, in order, forming the wiki's section tree.",
        (
            _c("section_id", "BIGINT", "Build-specific section id"),
            _c("page_id", "BIGINT", "Foreign key to pages.page_id"),
            ENTRY_FK,
            _c("parent_section_id", "BIGINT", "Enclosing section (h3 under h2, h4 under h3)"),
            _c("ordinal", "INTEGER", "Heading position on the page; 0 for text before headings"),
            _c("level", "INTEGER", "Heading level: 2 language, 3 and 4 subsections"),
            _c("heading", "TEXT", "Heading exactly as written on the wiki"),
            _c("anchor", "TEXT", "HTML anchor of the heading"),
            _c("section_type", "TEXT", "Normalized type: pos, etymology, translations, ..."),
            _c("pos", "TEXT", "Part of speech when section_type is pos"),
            _c("homograph", "INTEGER", "N from a numbered heading such as 'Navdêr 2'"),
            _c("text", "TEXT", "Section body as plain text"),
        ),
        "section_id",
    ),
    Table(
        "section_html",
        "Cleaned HTML of each section, kept apart from sections because it is large.",
        (SECTION_FK, _c("html", "TEXT", "Section HTML without per-page CSS or widget state")),
        "section_id",
    ),
    Table(
        "headwords",
        "Headword line of each part-of-speech section, with grammatical gender.",
        (
            _c("headword_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("pos", "TEXT", "Part of speech"),
            _c("homograph", "INTEGER", "N from a numbered heading"),
            _c("headword", "TEXT", "Headword form"),
            _c("gender", "TEXT", "Gender as the wiki words it (mê, nêr, ...)"),
            _c("headword_line", "TEXT", "Full headword line as plain text"),
        ),
        "headword_id",
    ),
    Table(
        "senses",
        "Definitions, one row each. Sub-senses point at their parent through parent_sense_id.",
        (
            _c("sense_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("parent_sense_id", "BIGINT", "Parent sense for a sub-sense"),
            _c("ordinal", "INTEGER", "Position among sibling senses, from 1"),
            _c("depth", "INTEGER", "0 for a top-level sense"),
            _c("pos", "TEXT", "Part of speech"),
            _c("labels", "TEXT", "Topic or usage labels, comma-separated"),
            _c("definition", "TEXT", "Definition as plain text"),
            _c("linked_terms", "TEXT", "JSON array of wiki pages linked from the definition"),
        ),
        "sense_id",
    ),
    Table(
        "examples",
        "Usage examples attached to a sense.",
        (
            _c("example_id", "BIGINT", "Row id"),
            ENTRY_FK,
            _c("sense_id", "BIGINT", "Foreign key to senses.sense_id"),
            _c("example", "TEXT", "Example sentence"),
            _c("translation", "TEXT", "Translation or explanation, when given"),
            _c("transliteration", "TEXT", "Transliteration, when given"),
        ),
        "example_id",
    ),
    Table(
        "quotations",
        "Dated literary citations, from senses and from 'Ji wêjeyê' sections.",
        (
            _c("quotation_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("sense_id", "BIGINT", "Sense the citation supports, when known"),
            _c("year", "TEXT", "Year from the citation (first 3-4 digit number)"),
            _c("author", "TEXT", "Author"),
            _c("work", "TEXT", "Title of the work"),
            _c("source_text", "TEXT", "Full citation line"),
            _c("passage", "TEXT", "Quoted passage"),
            _c("transliteration", "TEXT", "Latin transliteration, when given"),
            _c("translation", "TEXT", "Translation, when given"),
        ),
        "quotation_id",
    ),
    Table(
        "pronunciations",
        "IPA, syllabification, rhymes and audio recordings ('Bilêvkirin' sections).",
        (
            _c("pronunciation_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("kind", "TEXT", "ipa, audio, syllabification, rhyme or other"),
            _c("value", "TEXT", "Transcription, or the Commons file name for audio"),
            _c("qualifier", "TEXT", "Region or dialect label (Amed, Bidlîs, ...)"),
            _c("media_id", "TEXT", "Foreign key to media.media_id for audio"),
        ),
        "pronunciation_id",
    ),
    Table(
        "etymologies",
        "Word origins ('Etîmolojî' sections).",
        (
            _c("etymology_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("etymology", "TEXT", "Etymology as plain text"),
            _c("linked_terms", "TEXT", "JSON array of wiki pages linked from the etymology"),
        ),
        "etymology_id",
    ),
    Table(
        "translations",
        "Translations ('Werger' sections), one row per translated term.",
        (
            _c("translation_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("gloss", "TEXT", "Sense the translation table belongs to, when labelled"),
            _c("target_language", "TEXT", "Target language name in Kurmancî"),
            _c("target_code", "TEXT", "Target language code"),
            _c("term", "TEXT", "Translated term"),
            _c("term_page", "TEXT", "Wiki page the term links to"),
            _c("transliteration", "TEXT", "Transliteration, when the line has exactly one"),
            _c("gender", "TEXT", "Gender, when the line has exactly one"),
        ),
        "translation_id",
    ),
    Table(
        "relations",
        "Word-to-word links: synonyms, antonyms, derived terms, other scripts, and more.",
        (
            _c("relation_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("sense_id", "BIGINT", "Sense the relation belongs to, for per-sense synonyms"),
            _c("relation_type", "TEXT", "synonyms, antonyms, derived_terms, other_scripts, ..."),
            _c("term", "TEXT", "Related term as displayed"),
            _c("term_page", "TEXT", "Wiki page the term links to"),
            _c("qualifier", "TEXT", "Label on the item (script name, part of speech, ...)"),
        ),
        "relation_id",
    ),
    Table(
        "inflection_tables",
        "Declension and conjugation tables as rectangular JSON grids.",
        (
            _c("table_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("ordinal", "INTEGER", "Position of the table in its section"),
            _c("caption", "TEXT", "Table caption"),
            _c("row_count", "INTEGER", "Rows after expanding spans"),
            _c("column_count", "INTEGER", "Columns after expanding spans"),
            _c("grid_json", "TEXT", "JSON array of rows of cell text"),
        ),
        "table_id",
    ),
    Table(
        "inflection_forms",
        "Long format of the tables: one inflected form per row with its headers.",
        (
            _c("form_id", "BIGINT", "Row id"),
            _c("table_id", "BIGINT", "Foreign key to inflection_tables.table_id"),
            ENTRY_FK,
            _c("group_header", "TEXT", "Full-width header above the cell"),
            _c("row_header", "TEXT", "Nearest header to the left (case, person, ...)"),
            _c("column_header", "TEXT", "Nearest header above (gender, number, tense, ...)"),
            _c("form", "TEXT", "Inflected form"),
            _c("form_page", "TEXT", "Wiki page the form links to"),
        ),
        "form_id",
    ),
    Table(
        "reference_notes",
        "'Çavkanî' sections: sources and provenance notes as plain text.",
        (
            _c("reference_id", "BIGINT", "Row id"),
            ENTRY_FK,
            SECTION_FK,
            _c("note", "TEXT", "Reference text"),
        ),
        "reference_id",
    ),
    Table(
        "media",
        "Every media file referenced by a page or stored in the ZIM, with licence and status.",
        (
            _c("media_id", "TEXT", "16 hex digits: SHA-1 of the ZIM path or source URL"),
            _c("kind", "TEXT", "audio or image"),
            _c("role", "TEXT", "pronunciation, illustration, hieroglyph, icon, link or ui"),
            _c("source", "TEXT", "zim or wikimedia"),
            _c("zim_path", "TEXT", "Path inside the ZIM"),
            _c("source_url", "TEXT", "Download URL on upload.wikimedia.org"),
            _c("commons_file", "TEXT", "Wikimedia Commons file name"),
            _c("mime", "TEXT", "MIME type detected from the file bytes"),
            _c("bytes", "BIGINT", "File size"),
            _c("sha256", "TEXT", "SHA-256 of the file"),
            _c("local_path", "TEXT", "Path below the release media folder"),
            _c("status", "TEXT", "present, missing or failed"),
            _c("error", "TEXT", "Last download error"),
            _c("usage_count", "INTEGER", "Rows in media_usages"),
            _c("original_width", "INTEGER", "Width of the original image"),
            _c("original_height", "INTEGER", "Height of the original image"),
            _c("license", "TEXT", "Short licence name from Commons; empty when unknown"),
            _c("license_url", "TEXT", "Licence URL from Commons"),
            _c("artist", "TEXT", "Author, as plain text from Commons"),
            _c("description_url", "TEXT", "Commons description page"),
            _c("license_match", "TEXT", "exact, by_dimensions or empty"),
        ),
        "media_id",
    ),
    Table(
        "media_usages",
        "Where each media file appears.",
        (
            _c("usage_id", "BIGINT", "Row id"),
            _c("media_id", "TEXT", "Foreign key to media.media_id"),
            _c("page_id", "BIGINT", "Foreign key to pages.page_id"),
            ENTRY_FK,
            SECTION_FK,
            _c("role", "TEXT", "pronunciation, illustration, hieroglyph, icon or link"),
            _c("caption", "TEXT", "Figure caption"),
        ),
        "usage_id",
    ),
)

TABLE_BY_NAME: dict[str, Table] = {table.name: table for table in TABLES}

INDEXES: tuple[str, ...] = (
    "CREATE INDEX ix_entries_title ON entries(title)",
    "CREATE INDEX ix_entries_lang ON entries(language_code)",
    "CREATE INDEX ix_entries_key ON entries(entry_key)",
    "CREATE INDEX ix_entries_page ON entries(page_id)",
    "CREATE INDEX ix_pages_title ON pages(title)",
    "CREATE INDEX ix_sections_entry ON sections(entry_id)",
    "CREATE INDEX ix_sections_type ON sections(section_type)",
    "CREATE INDEX ix_senses_entry ON senses(entry_id)",
    "CREATE INDEX ix_senses_section ON senses(section_id)",
    "CREATE INDEX ix_headwords_entry ON headwords(entry_id)",
    "CREATE INDEX ix_examples_entry ON examples(entry_id)",
    "CREATE INDEX ix_examples_sense ON examples(sense_id)",
    "CREATE INDEX ix_quotations_entry ON quotations(entry_id)",
    "CREATE INDEX ix_pronunciations_entry ON pronunciations(entry_id)",
    "CREATE INDEX ix_etymologies_entry ON etymologies(entry_id)",
    "CREATE INDEX ix_translations_entry ON translations(entry_id)",
    "CREATE INDEX ix_translations_code ON translations(target_code)",
    "CREATE INDEX ix_relations_entry ON relations(entry_id)",
    "CREATE INDEX ix_relations_type ON relations(relation_type)",
    "CREATE INDEX ix_inflection_tables_entry ON inflection_tables(entry_id)",
    "CREATE INDEX ix_inflection_forms_entry ON inflection_forms(entry_id)",
    "CREATE INDEX ix_reference_notes_entry ON reference_notes(entry_id)",
    "CREATE INDEX ix_media_usages_media ON media_usages(media_id)",
    "CREATE INDEX ix_media_usages_entry ON media_usages(entry_id)",
    "CREATE INDEX ix_redirects_alias ON redirects(alias)",
)


def create_table_sql(table: Table) -> str:
    """Portable DDL that runs unchanged on SQLite and PostgreSQL."""
    lines = []
    for column in table.columns:
        suffix = " PRIMARY KEY" if column.name == table.primary_key else ""
        lines.append(f"    {column.name} {column.sql_type}{suffix}")
    body = ",\n".join(lines)
    return f"CREATE TABLE {table.name} (\n{body}\n)"
