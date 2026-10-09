"""Canonical lemmas merged across ZIM archives.

Revision ID: 20261010_0004
Revises: 20261010_0003
Create Date: 2026-10-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261010_0004"
down_revision: Union[str, Sequence[str], None] = "20261010_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "canonical_lemmas",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("title_normalized", sa.String(length=512), nullable=False),
        sa.Column(
            "zim_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extract_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("entry_id", sa.Integer(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title_normalized", name="uq_canonical_title_normalized"),
    )
    op.create_index("ix_canonical_extract_status", "canonical_lemmas", ["extract_status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_canonical_extract_status", table_name="canonical_lemmas")
    op.drop_table("canonical_lemmas")
