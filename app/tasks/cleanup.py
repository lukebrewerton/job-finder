# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Daily cleanup task — removes job listings that have not been seen in recent fetches.

Shortlisted and applied jobs (matched on dedup_key so ATS/aggregator siblings are both
covered) are always exempt. HN Who is Hiring jobs use a longer window because the
thread is monthly.

Safety guard: if no source has run successfully in twice the cleanup window, the task
aborts rather than risking a mass-delete caused by a broken fetch pipeline.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.workers import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="cleanup_stale_jobs")
def cleanup_stale_jobs() -> dict:
    from app.config import get_settings
    from app.db import SessionLocal
    from app.models.job import Job
    from app.models.job_state import JobState
    from app.models.source import Source

    settings = get_settings()
    now = datetime.now(UTC)
    standard_cutoff = now - timedelta(days=settings.job_cleanup_days)
    hn_cutoff = now - timedelta(days=settings.hn_cleanup_days)

    with SessionLocal() as session:
        # Safety guard: abort if no source has run in 2× the standard cleanup window.
        # This prevents wiping the pool when fetches are broken (e.g. expired API key).
        guard_cutoff = now - timedelta(days=settings.job_cleanup_days * 2)
        most_recent_run = session.scalar(func.max(Source.last_run_at))
        if most_recent_run is None or most_recent_run < guard_cutoff:
            log.warning(
                "cleanup aborted — no successful fetch since %s (guard window: %d days)",
                most_recent_run,
                settings.job_cleanup_days * 2,
            )
            return {"deleted": 0, "aborted": True, "reason": "no recent fetch"}

        # Dedup keys that any user has shortlisted or applied to — exempt from cleanup.
        tracked_dedup_keys = (
            select(Job.dedup_key)
            .join(JobState, JobState.job_id == Job.id)
            .where(JobState.status.in_(["shortlisted", "applied"]))
        )

        # Delete standard sources (non-HN) not seen within the cleanup window.
        std_deleted: int = session.execute(
            delete(Job).where(
                Job.source_id.in_(select(Source.id).where(Source.type != "hn_whoishiring")),
                Job.last_seen_at < standard_cutoff,
                Job.dedup_key.not_in(tracked_dedup_keys),
            )
        ).rowcount  # type: ignore[attr-defined]

        # Delete HN jobs not seen within the longer HN window.
        hn_deleted: int = session.execute(
            delete(Job).where(
                Job.source_id.in_(select(Source.id).where(Source.type == "hn_whoishiring")),
                Job.last_seen_at < hn_cutoff,
                Job.dedup_key.not_in(tracked_dedup_keys),
            )
        ).rowcount  # type: ignore[attr-defined]

        session.commit()

    total = std_deleted + hn_deleted
    log.info(
        "cleanup complete — deleted %d jobs (%d standard, %d HN)",
        total,
        std_deleted,
        hn_deleted,
    )
    return {"deleted": total, "standard": std_deleted, "hn": hn_deleted, "aborted": False}
