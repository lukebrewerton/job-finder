"""add oidc_sub to users

Revision ID: e5a3b8c91d24
Revises: d4f2a9c05b71
Create Date: 2026-06-17 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a3b8c91d24"
down_revision: str | None = "d4f2a9c05b71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oidc_sub", sa.String(), nullable=True))
    op.create_index("ix_users_oidc_sub", "users", ["oidc_sub"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_oidc_sub", table_name="users")
    op.drop_column("users", "oidc_sub")
