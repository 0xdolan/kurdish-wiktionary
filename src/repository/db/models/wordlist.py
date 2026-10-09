from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.repository.db.models.entry import Base


class WordlistExtractStatus(StrEnum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    SKIPPED = "skipped"
    FAILED = "failed"


class WordlistTitleModel(Base):
    __tablename__ = "wordlist_titles"
    __table_args__ = (
        UniqueConstraint("title_normalized", "zim_uuid", name="uq_wordlist_title_zim"),
        Index("ix_wordlist_extract_status", "extract_status"),
        Index("ix_wordlist_title_normalized", "title_normalized"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    title_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    zim_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    zim_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extract_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=WordlistExtractStatus.PENDING.value,
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
