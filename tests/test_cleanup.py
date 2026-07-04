# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Integration tests for the daily cleanup task.

Tests hit the real PostgreSQL database. Each test tags rows with a per-run UUID
and removes them in a finally block.

Scenarios verified:
- A stale standard job (last_seen_at past the window) is deleted.
- A job seen within the window survives.
- A shortlisted job is exempt from cleanup even when stale.
- An applied job is exempt from cleanup even when stale.
- An HN job stale by the standard window but fresh within the HN window survives.
- An HN job stale past the HN window is deleted.
- If no source has run recently the task aborts without deleting anything.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.db import SessionLocal
from app.models.job import Job
from app.models.job_state import JobState
from app.models.source import Source
from app.models.user import User
from app.tasks.cleanup import cleanup_stale_jobs

_TAG = uuid.uuid4().hex[:8]
_NOW = datetime.now(UTC)


def _src(
    session: object, *, src_type: str = "remotive", last_run_at: datetime | None = None
) -> Source:
    src = Source(
        type=src_type,
        name=f"[cleanup-test-{_TAG}] {src_type}",
        authority=0,
        config={},
        enabled=True,
        cadence_minutes=60,
        last_run_at=last_run_at,
    )
    session.add(src)  # type: ignore[union-attr]
    return src


def _job(session: object, *, source: Source, last_seen_at: datetime) -> Job:
    job = Job(
        source_id=source.id,
        external_id=f"ext-{uuid.uuid4().hex[:8]}-{_TAG}",
        title="Engineer",
        company=f"Co-{_TAG}",
        url="https://example.com",
        remote_mode="remote",
        dedup_key=f"dedup-{uuid.uuid4().hex[:8]}-{_TAG}",
        content_hash="abc123",
        fetched_at=_NOW,
        last_seen_at=last_seen_at,
        salary_disclosed=False,
    )
    session.add(job)  # type: ignore[union-attr]
    return job


def _state(session: object, *, job: Job, user: User, status: str) -> JobState:
    state = JobState(user_id=user.id, job_id=job.id, status=status)
    session.add(state)  # type: ignore[union-attr]
    return state


def _user(session: object) -> User:
    u = User(email=f"cleanup-test-{uuid.uuid4().hex[:8]}@example.com", name="Test")
    session.add(u)  # type: ignore[union-attr]
    return u


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_exists(session: object, job_id: uuid.UUID) -> bool:
    return session.get(Job, job_id) is not None  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_stale_standard_job_is_deleted() -> None:
    with SessionLocal() as session:
        src = _src(session, last_run_at=_NOW)
        session.flush()
        job = _job(session, source=src, last_seen_at=_NOW - timedelta(days=15))
        session.commit()
        job_id = job.id
        try:
            cleanup_stale_jobs()
            with SessionLocal() as s2:
                assert not _job_exists(s2, job_id), "Stale job should have been deleted"
        finally:
            with SessionLocal() as s2:
                s2.delete(s2.get(Source, src.id)) if s2.get(Source, src.id) else None
                s2.commit()


def test_fresh_job_survives_cleanup() -> None:
    with SessionLocal() as session:
        src = _src(session, last_run_at=_NOW)
        session.flush()
        job = _job(session, source=src, last_seen_at=_NOW - timedelta(days=3))
        session.commit()
        job_id = job.id
        src_id = src.id
        try:
            cleanup_stale_jobs()
            with SessionLocal() as s2:
                assert _job_exists(s2, job_id), "Fresh job should survive cleanup"
        finally:
            with SessionLocal() as s2:
                j = s2.get(Job, job_id)
                if j:
                    s2.delete(j)
                s = s2.get(Source, src_id)
                if s:
                    s2.delete(s)
                s2.commit()


def test_shortlisted_job_is_exempt() -> None:
    with SessionLocal() as session:
        user = _user(session)
        src = _src(session, last_run_at=_NOW)
        session.flush()
        job = _job(session, source=src, last_seen_at=_NOW - timedelta(days=20))
        session.flush()
        _state(session, job=job, user=user, status="shortlisted")
        session.commit()
        job_id = job.id
        src_id = src.id
        user_id = user.id
        try:
            cleanup_stale_jobs()
            with SessionLocal() as s2:
                assert _job_exists(s2, job_id), "Shortlisted job should be exempt from cleanup"
        finally:
            with SessionLocal() as s2:
                j = s2.get(Job, job_id)
                if j:
                    s2.delete(j)
                s = s2.get(Source, src_id)
                if s:
                    s2.delete(s)
                u = s2.get(User, user_id)
                if u:
                    s2.delete(u)
                s2.commit()


def test_applied_job_is_exempt() -> None:
    with SessionLocal() as session:
        user = _user(session)
        src = _src(session, last_run_at=_NOW)
        session.flush()
        job = _job(session, source=src, last_seen_at=_NOW - timedelta(days=30))
        session.flush()
        _state(session, job=job, user=user, status="applied")
        session.commit()
        job_id = job.id
        src_id = src.id
        user_id = user.id
        try:
            cleanup_stale_jobs()
            with SessionLocal() as s2:
                assert _job_exists(s2, job_id), "Applied job should be exempt from cleanup"
        finally:
            with SessionLocal() as s2:
                j = s2.get(Job, job_id)
                if j:
                    s2.delete(j)
                s = s2.get(Source, src_id)
                if s:
                    s2.delete(s)
                u = s2.get(User, user_id)
                if u:
                    s2.delete(u)
                s2.commit()


def test_hn_job_survives_within_hn_window() -> None:
    """HN job stale by the standard window but fresh within HN window must survive."""
    with SessionLocal() as session:
        src = _src(session, src_type="hn_whoishiring", last_run_at=_NOW)
        session.flush()
        # 20 days old — past standard 14-day window, within HN 60-day window
        job = _job(session, source=src, last_seen_at=_NOW - timedelta(days=20))
        session.commit()
        job_id = job.id
        src_id = src.id
        try:
            cleanup_stale_jobs()
            with SessionLocal() as s2:
                assert _job_exists(s2, job_id), "HN job within HN window should survive"
        finally:
            with SessionLocal() as s2:
                j = s2.get(Job, job_id)
                if j:
                    s2.delete(j)
                s = s2.get(Source, src_id)
                if s:
                    s2.delete(s)
                s2.commit()


def test_hn_job_deleted_past_hn_window() -> None:
    """HN job past the HN window is deleted."""
    with SessionLocal() as session:
        src = _src(session, src_type="hn_whoishiring", last_run_at=_NOW)
        session.flush()
        job = _job(session, source=src, last_seen_at=_NOW - timedelta(days=61))
        session.commit()
        job_id = job.id
        try:
            cleanup_stale_jobs()
            with SessionLocal() as s2:
                assert not _job_exists(s2, job_id), "HN job past HN window should be deleted"
        finally:
            with SessionLocal() as s2:
                s = s2.get(Source, src.id)
                if s:
                    s2.delete(s)
                s2.commit()


def test_cleanup_aborts_when_no_recent_fetch() -> None:
    """Task aborts without deleting anything when fetches have not run recently."""
    with SessionLocal() as session:
        # Source with a very old last_run_at
        src = _src(session, last_run_at=_NOW - timedelta(days=100))
        session.flush()
        job = _job(session, source=src, last_seen_at=_NOW - timedelta(days=20))
        session.commit()
        job_id = job.id
        src_id = src.id
        try:
            result = cleanup_stale_jobs()
            assert result["aborted"] is True
            assert result["deleted"] == 0
            with SessionLocal() as s2:
                assert _job_exists(s2, job_id), "Job should not be deleted when guard trips"
        finally:
            with SessionLocal() as s2:
                j = s2.get(Job, job_id)
                if j:
                    s2.delete(j)
                s = s2.get(Source, src_id)
                if s:
                    s2.delete(s)
                s2.commit()
