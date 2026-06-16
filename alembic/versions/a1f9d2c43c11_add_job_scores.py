"""add job_scores table

Revision ID: a1f9d2c43c11
Revises: 2e2b9d38714e
Create Date: 2026-06-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "a1f9d2c43c11"
down_revision = "2e2b9d38714e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_scores",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "cv_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cvs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "profile_id",
            UUID(as_uuid=True),
            sa.ForeignKey("search_profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("fit_score", sa.Integer, nullable=False),
        sa.Column("matched_skills", JSONB, nullable=False, server_default="[]"),
        sa.Column("gaps", JSONB, nullable=False, server_default="[]"),
        sa.Column("flags", JSONB, nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("model", sa.String, nullable=False, server_default=""),
        sa.Column(
            "scored_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("job_id", "cv_id", name="uq_job_scores_job_cv"),
    )
    op.create_index("ix_job_scores_job_id", "job_scores", ["job_id"])
    op.create_index("ix_job_scores_cv_id", "job_scores", ["cv_id"])
    op.create_index("ix_job_scores_fit_score", "job_scores", ["fit_score"])


def downgrade() -> None:
    op.drop_table("job_scores")
