# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Celery task for running a single source fetch by ID."""

from __future__ import annotations

import uuid

from app.workers import celery_app


@celery_app.task(name="fetch_source_by_id")
def fetch_source_by_id(source_id_str: str) -> dict:
    from sqlalchemy import select

    from app.core.pipeline import run_fetch_source
    from app.db import SessionLocal
    from app.models.profile import SearchProfile
    from app.models.source import Source

    source_id = uuid.UUID(source_id_str)

    with SessionLocal() as session:
        source = session.get(Source, source_id)
        if source is None:
            return {"error": f"Source {source_id_str} not found"}

        profiles = session.scalars(
            select(SearchProfile).where(SearchProfile.active.is_(True))
        ).all()
        seen: set[str] = set()
        titles: list[str] = []
        for p in profiles:
            for t in p.title_variations or []:
                if t not in seen:
                    seen.add(t)
                    titles.append(t)

        return run_fetch_source(source, titles, session)
