"""Wordlist titles for catalog pipeline.

Revision ID: 20261010_0003
Revises: 20261009_0002
Create Date: 2026-10-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0003"
down_revision: Union[str, Sequence[str], None] = "20261009_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wordlist_titles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("title_normalized", sa.String(length=512), nullable=False),
        sa.Column("zim_uuid", sa.String(length=64), nullable=False),
        sa.Column("zim_path", sa.String(length=1024), nullable=True),
        sa.Column("extract_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("entry_id", sa.Integer(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["entry_id"], ["entries.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("title_normalized", "zim_uuid", name="uq_wordlist_title_zim"),
    )
    op.create_index("ix_wordlist_extract_status", "wordlist_titles", ["extract_status"], unique=False)
    op.create_index("ix_wordlist_title_normalized", "wordlist_titles", ["title_normalized"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_wordlist_title_normalized", table_name="wordlist_titles")
    op.drop_index("ix_wordlist_extract_status", table_name="wordlist_titles")
    op.drop_table("wordlist_titles")
