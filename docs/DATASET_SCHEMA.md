# Data dictionary

Generated from `src/dataset/schema.py`. Each table ships under the same name in every
format. `entry_key` (`title|language_code`) is the key to use across releases; numeric
ids are rebuilt each release.

## `pages`

One row per wiki page (ZIM article). A page holds one entry per language.

| Column | Type | Meaning |
|---|---|---|
| `page_id` | BIGINT | Build-specific page id. Not stable between releases |
| `title` | TEXT | Page title as shown on the wiki |
| `page_kind` | TEXT | entry, soft_redirect (a 'Binêre X' stub) or conjugation |
| `source_zim` | TEXT | ZIM flavour the page was read from: maxi or nopic |
| `in_latest_dump` | INTEGER | 1 when the page exists in the newest ZIM |
| `revision_id` | BIGINT | MediaWiki revision (oldid) captured in the ZIM |
| `last_edited` | TEXT | Date of that revision (YYYY-MM-DD) |
| `language_count` | INTEGER | Number of language sections on the page |
| `section_count` | INTEGER | Number of headings on the page |
| `url` | TEXT | Live page on ku.wiktionary.org |

## `redirects`

Alternative titles: 'hard' ZIM redirects and 'soft' 'Binêre X' stub pages.

| Column | Type | Meaning |
|---|---|---|
| `alias` | TEXT | Title that redirects |
| `target` | TEXT | Title it points to |
| `redirect_kind` | TEXT | hard or soft |

## `entries`

One row per page + language: the main lookup table of the dataset.

| Column | Type | Meaning |
|---|---|---|
| `entry_id` | BIGINT | Build-specific entry id. Not stable between releases |
| `page_id` | BIGINT | Foreign key to pages.page_id |
| `ordinal` | INTEGER | Position of the language section on the page |
| `title` | TEXT | The word: page title |
| `language_name` | TEXT | Language heading in Kurmancî (Îngilîzî, Tirkî, ...) |
| `language_code` | TEXT | Wiki language code; 'und' when the page gives none |
| `entry_key` | TEXT | title|language_code: use this key across releases |
| `pos_list` | TEXT | Comma-separated parts of speech found in the entry |
| `sense_count` | INTEGER | Rows in senses for this entry |
| `has_ipa` | INTEGER | 1 when an IPA transcription exists |
| `has_audio` | INTEGER | 1 when a pronunciation recording is linked |
| `has_etymology` | INTEGER | 1 when an etymology section has text |
| `has_translations` | INTEGER | 1 when translations were extracted |
| `is_auto_generated` | INTEGER | 1 when the wiki marks the entry as bot-made from a translation table; the wiki warns these may contain translation errors |
| `auto_source_page` | TEXT | Translation page the bot entry was made from |
| `definition_pending` | INTEGER | 1 when the wiki shows 'the meaning is not written yet' instead of a definition |

## `sections`

Every heading on every page, in order, forming the wiki's section tree.

| Column | Type | Meaning |
|---|---|---|
| `section_id` | BIGINT | Build-specific section id |
| `page_id` | BIGINT | Foreign key to pages.page_id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `parent_section_id` | BIGINT | Enclosing section (h3 under h2, h4 under h3) |
| `ordinal` | INTEGER | Heading position on the page; 0 for text before headings |
| `level` | INTEGER | Heading level: 2 language, 3 and 4 subsections |
| `heading` | TEXT | Heading exactly as written on the wiki |
| `anchor` | TEXT | HTML anchor of the heading |
| `section_type` | TEXT | Normalized type: pos, etymology, translations, ... |
| `pos` | TEXT | Part of speech when section_type is pos |
| `homograph` | INTEGER | N from a numbered heading such as 'Navdêr 2' |
| `text` | TEXT | Section body as plain text |

## `section_html`

Cleaned HTML of each section, kept apart from sections because it is large.

| Column | Type | Meaning |
|---|---|---|
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `html` | TEXT | Section HTML without per-page CSS or widget state |

## `headwords`

Headword line of each part-of-speech section, with grammatical gender.

| Column | Type | Meaning |
|---|---|---|
| `headword_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `pos` | TEXT | Part of speech |
| `homograph` | INTEGER | N from a numbered heading |
| `headword` | TEXT | Headword form |
| `gender` | TEXT | Gender as the wiki words it (mê, nêr, ...) |
| `headword_line` | TEXT | Full headword line as plain text |

## `senses`

Definitions, one row each. Sub-senses point at their parent through parent_sense_id.

| Column | Type | Meaning |
|---|---|---|
| `sense_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `parent_sense_id` | BIGINT | Parent sense for a sub-sense |
| `ordinal` | INTEGER | Position among sibling senses, from 1 |
| `depth` | INTEGER | 0 for a top-level sense |
| `pos` | TEXT | Part of speech |
| `labels` | TEXT | Topic or usage labels, comma-separated |
| `definition` | TEXT | Definition as plain text |
| `linked_terms` | TEXT | JSON array of wiki pages linked from the definition |

## `examples`

Usage examples attached to a sense.

| Column | Type | Meaning |
|---|---|---|
| `example_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `sense_id` | BIGINT | Foreign key to senses.sense_id |
| `example` | TEXT | Example sentence |
| `translation` | TEXT | Translation or explanation, when given |
| `transliteration` | TEXT | Transliteration, when given |

## `quotations`

Dated literary citations, from senses and from 'Ji wêjeyê' sections.

| Column | Type | Meaning |
|---|---|---|
| `quotation_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `sense_id` | BIGINT | Sense the citation supports, when known |
| `year` | TEXT | Year from the citation (first 3-4 digit number) |
| `author` | TEXT | Author |
| `work` | TEXT | Title of the work |
| `source_text` | TEXT | Full citation line |
| `passage` | TEXT | Quoted passage |
| `transliteration` | TEXT | Latin transliteration, when given |
| `translation` | TEXT | Translation, when given |

## `pronunciations`

IPA, syllabification, rhymes and audio recordings ('Bilêvkirin' sections).

| Column | Type | Meaning |
|---|---|---|
| `pronunciation_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `kind` | TEXT | ipa, audio, syllabification, rhyme or other |
| `value` | TEXT | Transcription, or the Commons file name for audio |
| `qualifier` | TEXT | Region or dialect label (Amed, Bidlîs, ...) |
| `media_id` | TEXT | Foreign key to media.media_id for audio |

## `etymologies`

Word origins ('Etîmolojî' sections).

| Column | Type | Meaning |
|---|---|---|
| `etymology_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `etymology` | TEXT | Etymology as plain text |
| `linked_terms` | TEXT | JSON array of wiki pages linked from the etymology |

## `translations`

Translations ('Werger' sections), one row per translated term.

| Column | Type | Meaning |
|---|---|---|
| `translation_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `gloss` | TEXT | Sense the translation table belongs to, when labelled |
| `target_language` | TEXT | Target language name in Kurmancî |
| `target_code` | TEXT | Target language code |
| `term` | TEXT | Translated term |
| `term_page` | TEXT | Wiki page the term links to |
| `transliteration` | TEXT | Transliteration, when the line has exactly one |
| `gender` | TEXT | Gender, when the line has exactly one |

## `relations`

Word-to-word links: synonyms, antonyms, derived terms, other scripts, and more.

| Column | Type | Meaning |
|---|---|---|
| `relation_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `sense_id` | BIGINT | Sense the relation belongs to, for per-sense synonyms |
| `relation_type` | TEXT | synonyms, antonyms, derived_terms, other_scripts, ... |
| `term` | TEXT | Related term as displayed |
| `term_page` | TEXT | Wiki page the term links to |
| `qualifier` | TEXT | Label on the item (script name, part of speech, ...) |

## `inflection_tables`

Declension and conjugation tables as rectangular JSON grids.

| Column | Type | Meaning |
|---|---|---|
| `table_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `ordinal` | INTEGER | Position of the table in its section |
| `caption` | TEXT | Table caption |
| `row_count` | INTEGER | Rows after expanding spans |
| `column_count` | INTEGER | Columns after expanding spans |
| `grid_json` | TEXT | JSON array of rows of cell text |

## `inflection_forms`

Long format of the tables: one inflected form per row with its headers.

| Column | Type | Meaning |
|---|---|---|
| `form_id` | BIGINT | Row id |
| `table_id` | BIGINT | Foreign key to inflection_tables.table_id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `group_header` | TEXT | Full-width header above the cell |
| `row_header` | TEXT | Nearest header to the left (case, person, ...) |
| `column_header` | TEXT | Nearest header above (gender, number, tense, ...) |
| `form` | TEXT | Inflected form |
| `form_page` | TEXT | Wiki page the form links to |

## `reference_notes`

'Çavkanî' sections: sources and provenance notes as plain text.

| Column | Type | Meaning |
|---|---|---|
| `reference_id` | BIGINT | Row id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `note` | TEXT | Reference text |

## `media`

Every media file referenced by a page or stored in the ZIM, with licence and status.

| Column | Type | Meaning |
|---|---|---|
| `media_id` | TEXT | 16 hex digits: SHA-1 of the ZIM path or source URL |
| `kind` | TEXT | audio or image |
| `role` | TEXT | pronunciation, illustration, hieroglyph, icon, link or ui |
| `source` | TEXT | zim or wikimedia |
| `zim_path` | TEXT | Path inside the ZIM |
| `source_url` | TEXT | Download URL on upload.wikimedia.org |
| `commons_file` | TEXT | Wikimedia Commons file name |
| `mime` | TEXT | MIME type detected from the file bytes |
| `bytes` | BIGINT | File size |
| `sha256` | TEXT | SHA-256 of the file |
| `local_path` | TEXT | Path below the release media folder |
| `status` | TEXT | present, missing or failed |
| `error` | TEXT | Last download error |
| `usage_count` | INTEGER | Rows in media_usages |
| `original_width` | INTEGER | Width of the original image |
| `original_height` | INTEGER | Height of the original image |
| `license` | TEXT | Short licence name from Commons; empty when unknown |
| `license_url` | TEXT | Licence URL from Commons |
| `artist` | TEXT | Author, as plain text from Commons |
| `description_url` | TEXT | Commons description page |
| `license_match` | TEXT | exact, by_dimensions or empty |

## `media_usages`

Where each media file appears.

| Column | Type | Meaning |
|---|---|---|
| `usage_id` | BIGINT | Row id |
| `media_id` | TEXT | Foreign key to media.media_id |
| `page_id` | BIGINT | Foreign key to pages.page_id |
| `entry_id` | BIGINT | Foreign key to entries.entry_id |
| `section_id` | BIGINT | Foreign key to sections.section_id |
| `role` | TEXT | pronunciation, illustration, hieroglyph, icon or link |
| `caption` | TEXT | Figure caption |

## Section types

| `section_type` | Kurmancî | English |
|---|---|---|
| `pos` | Beşê axaftinê | Part of speech |
| `pronunciation` | Bilêvkirin | Pronunciation |
| `etymology` | Etîmolojî | Etymology |
| `translations` | Werger | Translations |
| `inflection` | Tewandin | Inflection |
| `alternative_forms` | Formên alternatîv | Alternative forms |
| `other_scripts` | Bi alfabeyên din | Other scripts |
| `dialect_forms` | Bi zaravayên din | Dialect forms |
| `derived_terms` | Jê | Derived terms |
| `related_terms` | Têkildar | Related terms |
| `compare` | Bide ber | Compare |
| `see_also` | Binêre herwiha | See also |
| `synonyms` | Hevmane | Synonyms |
| `near_synonyms` | Nêzîk | Near synonyms |
| `antonyms` | Dijmane | Antonyms |
| `hypernyms` | Jornav | Hypernyms |
| `hyponyms` | Jêrnav | Hyponyms |
| `meronyms` | Meronîm | Meronyms |
| `descendants` | Dûnde | Descendants |
| `anagrams` | Anagram | Anagrams |
| `rhymes` | Qafiye | Rhymes |
| `scientific_names` | Navê zanistî | Scientific names |
| `usage_notes` | Bikaranîn | Usage notes |
| `quotations` | Ji wêjeyê | Quotations |
| `references` | Çavkanî | References |
| `further_reading` | Zêdetir hîn bibe | Further reading |
| `proverbs` | Gotinên pêşiyan | Proverbs |
| `idioms` | Biwêj | Idioms |
| `epithets` | Bernav | Epithets |
| `paraphrases` | Bergend | Paraphrases |
| `word_by_word` | Peyv bi peyv | Word by word |
| `plural_forms` | Pirjimar | Plural forms |
| `singular_forms` | Yekjimar | Singular forms |
| `examples` | Nimûne | Examples |
| `other` | Yên din | Other |

## Parts of speech

| `pos` | Kurmancî | English |
|---|---|---|
| `noun` | Navdêr | Noun |
| `noun_form` | Formeke navdêrê | Noun form |
| `proper_noun` | Serenav | Proper noun |
| `proper_noun_form` | Formeke serenavê | Proper noun form |
| `verb` | Lêker | Verb |
| `verb_form` | Formeke lêkerê | Verb form |
| `verb_root` | Rehekî lêkerê | Verb root |
| `root` | Reh | Root |
| `adjective` | Rengdêr | Adjective |
| `adjective_form` | Formeke rengdêrê | Adjective form |
| `adverb` | Hoker | Adverb |
| `adverb_form` | Formeke hokerê | Adverb form |
| `idiom` | Biwêj | Idiom |
| `proverb` | Gotineke pêşiyan | Proverb |
| `numeral` | Hejmar | Numeral |
| `pronoun` | Cînav | Pronoun |
| `pronoun_form` | Formeke cînavê | Pronoun form |
| `adposition` | Daçek | Adposition |
| `preposition` | Pêşdaçek | Preposition |
| `postposition` | Paşdaçek | Postposition |
| `circumposition` | Bazinedaçek | Circumposition |
| `suffix` | Paşgir | Suffix |
| `prefix` | Pêşgir | Prefix |
| `infix` | Navgir | Infix |
| `interjection` | Baneşan | Interjection |
| `conjunction` | Girêdek | Conjunction |
| `particle` | Pirtik | Particle |
| `abbreviation` | Kurtenav | Abbreviation |
| `short_form` | Kurte | Short form |
| `letter` | Tîp | Letter |
| `symbol` | Sembol | Symbol |
| `phrase` | Hevok | Phrase |
| `expression` | Îfade | Expression |
| `participle` | Partîsîp | Participle |
| `article` | Artîkel | Article |
| `sense` | Mane | Sense (no part of speech given) |
