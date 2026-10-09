from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.extraction.text_clean import contains_html_entities
from src.repository.db.models import EntryDefinitionRow, EntryModel
from src.repository.db.models.canonical import CanonicalExtractStatus, CanonicalLemmaModel


@dataclass(frozen=True, slots=True)
class ExtractionAuditResult:
    canonical_total: int
    canonical_extracted: int
    canonical_pending: int
    canonical_skipped: int
    canonical_failed: int
    extracted_missing_entry_id: int
    entries_total: int
    entries_with_html_entities: int
    sample_entity_lemmas: list[str]


async def audit_canonical_extraction(
    session: AsyncSession,
    *,
    entity_sample_limit: int = 10,
) -> ExtractionAuditResult:
    async def _count_status(status: CanonicalExtractStatus) -> int:
        stmt = (
            select(func.count())
            .select_from(CanonicalLemmaModel)
            .where(CanonicalLemmaModel.extract_status == status.value)
        )
        return int((await session.execute(stmt)).scalar_one())

    canonical_total = int(
        (await session.execute(select(func.count()).select_from(CanonicalLemmaModel))).scalar_one()
    )
    extracted_missing = int(
        (
            await session.execute(
                select(func.count())
                .select_from(CanonicalLemmaModel)
                .where(
                    CanonicalLemmaModel.extract_status
                    == CanonicalExtractStatus.EXTRACTED.value,
                    CanonicalLemmaModel.entry_id.is_(None),
                )
            )
        ).scalar_one()
    )

    entries_total = int(
        (await session.execute(select(func.count()).select_from(EntryModel))).scalar_one()
    )

    def_rows = (
        await session.execute(
            select(EntryDefinitionRow.value, EntryModel.entry)
            .join(EntryModel, EntryDefinitionRow.entry_id == EntryModel.id)
            .limit(5000)
        )
    ).all()

    entity_lemmas: list[str] = []
    entity_count = 0
    for text, lemma in def_rows:
        if contains_html_entities(text):
            entity_count += 1
            if len(entity_lemmas) < entity_sample_limit:
                entity_lemmas.append(lemma)

    return ExtractionAuditResult(
        canonical_total=canonical_total,
        canonical_extracted=await _count_status(CanonicalExtractStatus.EXTRACTED),
        canonical_pending=await _count_status(CanonicalExtractStatus.PENDING),
        canonical_skipped=await _count_status(CanonicalExtractStatus.SKIPPED),
        canonical_failed=await _count_status(CanonicalExtractStatus.FAILED),
        extracted_missing_entry_id=extracted_missing,
        entries_total=entries_total,
        entries_with_html_entities=entity_count,
        sample_entity_lemmas=entity_lemmas,
    )
