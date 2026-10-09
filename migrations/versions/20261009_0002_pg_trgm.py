"""Enable pg_trgm index on entry_normalized.

Revision ID: 20261009_0002
Revises: 20261009_0001
Create Date: 2026-10-09

"""

from typing import Sequence, Union

from alembic import op

revision: str = "20261009_0002"
down_revision: Union[str, Sequence[str], None] = "20261009_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_entries_entry_normalized_trgm
        ON entries USING gin (entry_normalized gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_entries_entry_normalized_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
