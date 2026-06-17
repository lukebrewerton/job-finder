"""add exclude_entry_level to search_profiles

Revision ID: b3c1e7f82a90
Revises: fcdbf8cbf7a8
Create Date: 2026-06-17 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "b3c1e7f82a90"
down_revision: str | None = "fcdbf8cbf7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "search_profiles",
        sa.Column("exclude_entry_level", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("search_profiles", "exclude_entry_level")
