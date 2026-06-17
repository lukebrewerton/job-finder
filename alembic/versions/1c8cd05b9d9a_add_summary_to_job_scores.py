"""add_summary_to_job_scores

Revision ID: 1c8cd05b9d9a
Revises: e5a3b8c91d24
Create Date: 2026-06-17 09:42:37.101708

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "1c8cd05b9d9a"
down_revision: str | None = "e5a3b8c91d24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "job_scores",
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("job_scores", "summary")
