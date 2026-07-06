# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""merge heads

Revision ID: 875c0e5c7e8b
Revises: 1c8cd05b9d9a, a8c3e1f92b05
Create Date: 2026-07-06 12:12:10.311977

"""

from collections.abc import Sequence

revision: str = "875c0e5c7e8b"
down_revision: str | None = ("1c8cd05b9d9a", "a8c3e1f92b05")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
