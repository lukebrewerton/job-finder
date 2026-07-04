# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# Sync SQLAlchemy is used throughout. FastAPI runs these calls in a threadpool, and
# Celery (which is sync) shares the exact same models and sessions — no async/sync
# split to reason about. A deliberate maintainability-over-cleverness choice.

engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base. Models (Phase 1+) subclass this; Alembic reads its metadata."""


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped session."""
    with SessionLocal() as session:
        yield session
