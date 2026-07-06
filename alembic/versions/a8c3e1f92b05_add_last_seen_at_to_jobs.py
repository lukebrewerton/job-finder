# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""add last_seen_at to jobs

Tracks the most recent fetch in which each job was returned by its source.
Used by the daily cleanup task to expire stale listings.
Defaults to fetched_at so existing rows are not immediately cleaned up.

Revision ID: a8c3e1f92b05
Revises: fcdbf8cbf7a8
Create Date: 2026-06-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c3e1f92b05"
down_revision: str | None = "fcdbf8cbf7a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PostgreSQL does not allow column references in DEFAULT expressions, so we
    # add the column as nullable, backfill from fetched_at, then enforce NOT NULL
    # and add a server default of now() for future inserts.
    op.add_column(
        "jobs",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("UPDATE jobs SET last_seen_at = fetched_at WHERE last_seen_at IS NULL"))
    op.alter_column("jobs", "last_seen_at", nullable=False, server_default=sa.text("now()"))
    op.create_index("ix_jobs_last_seen_at", "jobs", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_last_seen_at", table_name="jobs")
    op.drop_column("jobs", "last_seen_at")
