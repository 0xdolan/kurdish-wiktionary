"""Initial entries schema.

Revision ID: 20261009_0001
Revises:
Create Date: 2026-10-09

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261009_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry", sa.String(length=512), nullable=False),
        sa.Column("entry_normalized", sa.String(length=512), nullable=False),
        sa.Column("language_code", sa.String(length=16), nullable=False),
        sa.Column("etymology", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("zim_uuid", sa.String(length=64), nullable=True),
        sa.Column("source_date", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entry_normalized", "language_code", name="uq_entries_normalized_lang"),
    )
    op.create_index("ix_entries_entry_normalized", "entries", ["entry_normalized"], unique=False)

    child_tables = [
        "entry_definitions",
        "entry_examples",
        "entry_synonyms",
        "entry_antonyms",
        "entry_phonetics",
        "entry_pronunciations",
        "entry_derived_terms",
        "entry_parts_of_speech",
    ]
    for table in child_tables:
        op.create_table(
            table,
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("value", sa.Text(), nullable=False),
            sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(f"ix_{table}_entry_id", table, ["entry_id"], unique=False)


def downgrade() -> None:
    for table in reversed(
        [
            "entry_parts_of_speech",
            "entry_derived_terms",
            "entry_pronunciations",
            "entry_phonetics",
            "entry_antonyms",
            "entry_synonyms",
            "entry_examples",
            "entry_definitions",
        ]
    ):
        op.drop_index(f"ix_{table}_entry_id", table_name=table)
        op.drop_table(table)
    op.drop_index("ix_entries_entry_normalized", table_name="entries")
    op.drop_table("entries")
