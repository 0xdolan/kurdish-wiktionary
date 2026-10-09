from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.repository.db.models.entry import Base


class CanonicalExtractStatus(StrEnum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    SKIPPED = "skipped"
    FAILED = "failed"


class CanonicalLemmaModel(Base):
    """One row per normalized lemma, merged across configured ZIM archives."""

    __tablename__ = "canonical_lemmas"
    __table_args__ = (
        UniqueConstraint("title_normalized", name="uq_canonical_title_normalized"),
        Index("ix_canonical_extract_status", "extract_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    zim_sources: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    extract_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CanonicalExtractStatus.PENDING.value,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
