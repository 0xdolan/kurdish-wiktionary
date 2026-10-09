from src.core.models import WiktionaryEntry
from src.repository.db.models import EntryModel


def entry_model_to_schema(row: EntryModel) -> WiktionaryEntry:
    metadata = dict(row.extra_metadata or {})
    metadata.setdefault("data_source", "sql")
    return WiktionaryEntry(
        entry=row.entry,
        part_of_speech=[r.value for r in row.parts_of_speech],
        definitions=[r.value for r in row.definitions],
        phonetic_transcriptions=[r.value for r in row.phonetics],
        pronunciations=[r.value for r in row.pronunciations],
        examples=[r.value for r in row.examples],
        synonyms=[r.value for r in row.synonyms],
        antonyms=[r.value for r in row.antonyms],
        etymology=row.etymology,
        derived_terms=[r.value for r in row.derived_terms],
        metadata=metadata,
    )
