from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EntryModel(Base):
    __tablename__ = "entries"
    __table_args__ = (
        UniqueConstraint("entry_normalized", "language_code", name="uq_entries_normalized_lang"),
        Index("ix_entries_entry_normalized", "entry_normalized"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry: Mapped[str] = mapped_column(String(512), nullable=False)
    entry_normalized: Mapped[str] = mapped_column(String(512), nullable=False)
    language_code: Mapped[str] = mapped_column(String(16), nullable=False, default="ku")
    etymology: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON,
        nullable=False,
        default=dict,
    )
    zim_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    definitions: Mapped[list["EntryDefinitionRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryDefinitionRow.ordinal",
    )
    examples: Mapped[list["EntryExampleRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryExampleRow.ordinal",
    )
    synonyms: Mapped[list["EntrySynonymRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntrySynonymRow.ordinal",
    )
    antonyms: Mapped[list["EntryAntonymRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryAntonymRow.ordinal",
    )
    phonetics: Mapped[list["EntryPhoneticRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryPhoneticRow.ordinal",
    )
    pronunciations: Mapped[list["EntryPronunciationRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryPronunciationRow.ordinal",
    )
    derived_terms: Mapped[list["EntryDerivedTermRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryDerivedTermRow.ordinal",
    )
    parts_of_speech: Mapped[list["EntryPartOfSpeechRow"]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
        order_by="EntryPartOfSpeechRow.ordinal",
    )


class _ChildRowMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class EntryDefinitionRow(Base, _ChildRowMixin):
    __tablename__ = "entry_definitions"
    entry: Mapped[EntryModel] = relationship(back_populates="definitions")


class EntryExampleRow(Base, _ChildRowMixin):
    __tablename__ = "entry_examples"
    entry: Mapped[EntryModel] = relationship(back_populates="examples")


class EntrySynonymRow(Base, _ChildRowMixin):
    __tablename__ = "entry_synonyms"
    entry: Mapped[EntryModel] = relationship(back_populates="synonyms")


class EntryAntonymRow(Base, _ChildRowMixin):
    __tablename__ = "entry_antonyms"
    entry: Mapped[EntryModel] = relationship(back_populates="antonyms")


class EntryPhoneticRow(Base, _ChildRowMixin):
    __tablename__ = "entry_phonetics"
    entry: Mapped[EntryModel] = relationship(back_populates="phonetics")


class EntryPronunciationRow(Base, _ChildRowMixin):
    __tablename__ = "entry_pronunciations"
    entry: Mapped[EntryModel] = relationship(back_populates="pronunciations")


class EntryDerivedTermRow(Base, _ChildRowMixin):
    __tablename__ = "entry_derived_terms"
    entry: Mapped[EntryModel] = relationship(back_populates="derived_terms")


class EntryPartOfSpeechRow(Base, _ChildRowMixin):
    __tablename__ = "entry_parts_of_speech"
    entry: Mapped[EntryModel] = relationship(back_populates="parts_of_speech")
