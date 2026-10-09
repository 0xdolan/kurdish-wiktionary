from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.repository.db.models.entry_assets import EntryHtmlModel, EntryMediaModel


async def upsert_entry_html(
    session: AsyncSession,
    entry_id: int,
    *,
    html_full: str,
    section_html: dict[str, str],
) -> None:
    insert_stmt = pg_insert(EntryHtmlModel).values(
        entry_id=entry_id,
        html_full=html_full,
        section_html=section_html,
    )
    excluded = insert_stmt.excluded
    stmt = insert_stmt.on_conflict_do_update(
        index_elements=["entry_id"],
        set_={
            "html_full": excluded.html_full,
            "section_html": excluded.section_html,
        },
    )
    await session.execute(stmt)


async def replace_entry_media(
    session: AsyncSession,
    entry_id: int,
    media: list[dict[str, Any]],
) -> int:
    await session.execute(delete(EntryMediaModel).where(EntryMediaModel.entry_id == entry_id))
    seen: set[str] = set()
    rows: list[EntryMediaModel] = []
    for item in media:
        url = str(item.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        rows.append(
            EntryMediaModel(
                entry_id=entry_id,
                kind=str(item.get("kind", "other")),
                url=url,
                local_path=item.get("local_path"),
                extra={k: v for k, v in item.items() if k not in {"url", "kind", "local_path"}},
            )
        )
    session.add_all(rows)
    await session.flush()
    return len(rows)


async def get_entry_html(session: AsyncSession, entry_id: int) -> EntryHtmlModel | None:
    stmt = select(EntryHtmlModel).where(EntryHtmlModel.entry_id == entry_id)
    return (await session.execute(stmt)).scalar_one_or_none()
