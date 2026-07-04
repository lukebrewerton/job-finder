# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""add authority to sources, drop type unique constraint

Allows multiple source rows with the same type (e.g. one per ATS company).
authority is used to prefer ATS rows over aggregators in dedup logic.

Revision ID: fcdbf8cbf7a8
Revises: a1f9d2c43c11
Create Date: 2026-06-16 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "fcdbf8cbf7a8"
down_revision: str | None = "a1f9d2c43c11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL auto-names an anonymous UniqueConstraint("type") as sources_type_key.
    op.drop_constraint("sources_type_key", "sources", type_="unique")
    op.add_column(
        "sources",
        sa.Column("authority", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sources", "authority")
    op.create_unique_constraint("sources_type_key", "sources", ["type"])
