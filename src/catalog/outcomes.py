"""Query and export canonical / wordlist extract outcomes (skipped, failed)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.outcome_reason import categorize_outcome_message, outcome_retry_hint
from src.repository.db.models import WordlistExtractStatus, WordlistTitleModel
from src.repository.db.models.canonical import CanonicalExtractStatus, CanonicalLemmaModel


@dataclass(frozen=True, slots=True)
class LemmaOutcome:
    title: str
    title_normalized: str
    status: str
    reason: str
    category: str


@dataclass(frozen=True, slots=True)
class OutcomeRow:
    title: str
    title_normalized: str
    status: str
    reason: str | None
    category: str
    entry_id: int | None
    extracted_at: str | None
    retry_hint: str


@dataclass(frozen=True, slots=True)
class OutcomeCategoryCount:
    status: str
    category: str
    count: int
    sample_titles: list[str]


@dataclass(frozen=True, slots=True)
class OutcomeReport:
    scope: str
    generated_at: str
    skipped_total: int
    failed_total: int
    categories: list[OutcomeCategoryCount]
    rows: list[OutcomeRow]


def lemma_outcome_from_row(
    *,
    title: str,
    title_normalized: str,
    status: str,
    last_error: str | None,
) -> LemmaOutcome:
    reason = last_error or ""
    return LemmaOutcome(
        title=title,
        title_normalized=title_normalized,
        status=status,
        reason=reason,
        category=categorize_outcome_message(last_error),
    )


def _canonical_outcome_select(statuses: Sequence[str]) -> Any:
    return (
        select(
            CanonicalLemmaModel.title,
            CanonicalLemmaModel.title_normalized,
            CanonicalLemmaModel.extract_status,
            CanonicalLemmaModel.last_error,
            CanonicalLemmaModel.entry_id,
            CanonicalLemmaModel.extracted_at,
        )
        .where(CanonicalLemmaModel.extract_status.in_(statuses))
        .order_by(CanonicalLemmaModel.title_normalized.asc())
    )


def _wordlist_outcome_select(statuses: Sequence[str]) -> Any:
    return (
        select(
            WordlistTitleModel.title,
            WordlistTitleModel.title_normalized,
            WordlistTitleModel.extract_status,
            WordlistTitleModel.last_error,
            WordlistTitleModel.entry_id,
            WordlistTitleModel.extracted_at,
        )
        .where(WordlistTitleModel.extract_status.in_(statuses))
        .order_by(WordlistTitleModel.title_normalized.asc())
    )


def _statuses_for_filter(scope: str, status_filter: str) -> list[str]:
    skipped_val = (
        CanonicalExtractStatus.SKIPPED.value
        if scope == "canonical"
        else WordlistExtractStatus.SKIPPED.value
    )
    failed_val = (
        CanonicalExtractStatus.FAILED.value
        if scope == "canonical"
        else WordlistExtractStatus.FAILED.value
    )
    if status_filter == "skipped":
        return [skipped_val]
    if status_filter == "failed":
        return [failed_val]
    return [skipped_val, failed_val]


async def iter_outcome_rows(
    session: AsyncSession,
    *,
    scope: str,
    status_filter: str,
    limit: int,
    offset: int = 0,
) -> list[OutcomeRow]:
    statuses = _statuses_for_filter(scope, status_filter)
    stmt = (
        _canonical_outcome_select(statuses)
        if scope == "canonical"
        else _wordlist_outcome_select(statuses)
    )
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()
    result: list[OutcomeRow] = []
    for title, normalized, status, last_error, entry_id, extracted_at in rows:
        category = categorize_outcome_message(last_error)
        result.append(
            OutcomeRow(
                title=title,
                title_normalized=normalized,
                status=status,
                reason=last_error,
                category=category,
                entry_id=entry_id,
                extracted_at=extracted_at.isoformat() if extracted_at else None,
                retry_hint=outcome_retry_hint(category, status),
            )
        )
    return result


async def count_outcomes(session: AsyncSession, *, scope: str) -> tuple[int, int]:
    if scope == "canonical":
        skipped = CanonicalExtractStatus.SKIPPED.value
        failed = CanonicalExtractStatus.FAILED.value

        async def _count(st: str) -> int:
            stmt = (
                select(func.count())
                .select_from(CanonicalLemmaModel)
                .where(CanonicalLemmaModel.extract_status == st)
            )
            return int((await session.execute(stmt)).scalar_one())

    else:
        skipped = WordlistExtractStatus.SKIPPED.value
        failed = WordlistExtractStatus.FAILED.value

        async def _count(st: str) -> int:
            stmt = (
                select(func.count())
                .select_from(WordlistTitleModel)
                .where(WordlistTitleModel.extract_status == st)
            )
            return int((await session.execute(stmt)).scalar_one())

    return await _count(skipped), await _count(failed)


async def build_outcome_report(
    session: AsyncSession,
    *,
    scope: str,
    status_filter: str = "both",
    row_limit: int = 500,
    sample_per_category: int = 5,
) -> OutcomeReport:
    skipped_total, failed_total = await count_outcomes(session, scope=scope)
    rows = await iter_outcome_rows(
        session,
        scope=scope,
        status_filter=status_filter,
        limit=row_limit,
    )

    bucket: dict[tuple[str, str], list[str]] = {}
    for row in rows:
        key = (row.status, row.category)
        bucket.setdefault(key, [])
        if len(bucket[key]) < sample_per_category:
            bucket[key].append(row.title)

    categories: list[OutcomeCategoryCount] = []

    for status_value in _statuses_for_filter(scope, status_filter):
        if scope == "canonical":
            stmt = (
                select(CanonicalLemmaModel.last_error, func.count())
                .where(CanonicalLemmaModel.extract_status == status_value)
                .group_by(CanonicalLemmaModel.last_error)
                .order_by(func.count().desc())
            )
        else:
            stmt = (
                select(WordlistTitleModel.last_error, func.count())
                .where(WordlistTitleModel.extract_status == status_value)
                .group_by(WordlistTitleModel.last_error)
                .order_by(func.count().desc())
            )
        for last_error, count in (await session.execute(stmt)).all():
            category = categorize_outcome_message(last_error)
            samples = bucket.get((status_value, category), [])[:sample_per_category]
            categories.append(
                OutcomeCategoryCount(
                    status=status_value,
                    category=category,
                    count=int(count),
                    sample_titles=samples,
                )
            )

    return OutcomeReport(
        scope=scope,
        generated_at=datetime.now(tz=UTC).isoformat(),
        skipped_total=skipped_total,
        failed_total=failed_total,
        categories=categories,
        rows=rows,
    )


def report_to_json(report: OutcomeReport) -> str:
    payload = {
        "scope": report.scope,
        "generated_at": report.generated_at,
        "skipped_total": report.skipped_total,
        "failed_total": report.failed_total,
        "categories": [
            {
                "status": c.status,
                "category": c.category,
                "count": c.count,
                "sample_titles": c.sample_titles,
            }
            for c in report.categories
        ],
        "rows": [asdict(row) for row in report.rows],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


async def export_outcomes_jsonl(
    session: AsyncSession,
    *,
    scope: str,
    status_filter: str,
    batch_size: int = 5000,
) -> AsyncIterator[str]:
    offset = 0
    while True:
        chunk = await iter_outcome_rows(
            session,
            scope=scope,
            status_filter=status_filter,
            limit=batch_size,
            offset=offset,
        )
        if not chunk:
            break
        for row in chunk:
            yield json.dumps(asdict(row), ensure_ascii=False)
        offset += len(chunk)
        if len(chunk) < batch_size:
            break
