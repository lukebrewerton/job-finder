"""Integration tests for ATS dedup authority (Phase 5, clause 3).

These tests hit the real PostgreSQL database.  Each test inserts isolated
rows tagged with a per-run UUID and removes them in a finally block so the
suite stays idempotent.

Clause under test:
  "ATS rows win dedup over aggregators" — when two source rows hold the same
  logical job (identical dedup_key), GET /api/jobs must surface the ATS row
  (authority=10), not the aggregator row (authority=0).

  Additionally: _enqueue_scoring must still enqueue an ATS job for scoring
  even when an aggregator duplicate was already scored first.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.jobs import _build_query
from app.core.dedup import make_content_hash, make_dedup_key
from app.core.pipeline import _enqueue_scoring
from app.db import SessionLocal
from app.main import app
from app.models.cv import CV
from app.models.job import Job
from app.models.job_score import JobScore
from app.models.source import Source
from app.models.user import User

client = TestClient(app)

_NOW = datetime.now(UTC)
# Per-run tag so parallel runs don't collide and leftover rows are identifiable.
_TAG = uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src(session: object, *, name: str, authority: int, src_type: str = "") -> Source:
    src = Source(
        type=src_type or ("greenhouse" if authority > 0 else "remotive"),
        name=f"[test-{_TAG}] {name}",
        authority=authority,
        config={},
        enabled=True,
        cadence_minutes=60,
    )
    session.add(src)  # type: ignore[union-attr]
    return src


def _job(
    session: object,
    *,
    source: Source,
    ext: str,
    title: str,
    company: str,
    location: str = "Remote",
) -> Job:
    dkey = make_dedup_key(title, company, location)
    job = Job(
        source_id=source.id,
        external_id=f"{ext}-{_TAG}",
        title=title,
        company=company,
        url=f"https://example.com/{ext}-{_TAG}",
        remote_mode="remote",
        location=location,
        dedup_key=dkey,
        content_hash=make_content_hash(title, company, location),
        fetched_at=_NOW,
        salary_disclosed=False,
    )
    session.add(job)  # type: ignore[union-attr]
    return job


def _get_real_default_cv_id(session: object) -> uuid.UUID | None:
    """Return the existing default CV if one exists in the real database."""
    return session.scalar(select(CV.id).where(CV.is_default.is_(True)).limit(1))  # type: ignore[union-attr]


def _score(session: object, *, job: Job, cv_id: uuid.UUID, score: int = 70) -> JobScore:
    js = JobScore(
        job_id=job.id,
        cv_id=cv_id,
        fit_score=score,
        matched_skills=["Python"],
        gaps=[],
        flags=[],
        rationale="stub",
        model="stub",
    )
    session.add(js)  # type: ignore[union-attr]
    return js


# ---------------------------------------------------------------------------
# Clause 3a: dedup query — ATS beats aggregator in DISTINCT ON ordering
# ---------------------------------------------------------------------------


def test_dedup_query_surfaces_ats_job_not_aggregator_for_shared_dedup_key() -> None:
    """_build_query returns the ATS row (auth 10) when both sources hold the same logical job."""
    company = f"DedupCo-{_TAG}"
    title = "Platform Engineer"

    with SessionLocal() as session:
        agg = _src(session, name="aggregator", authority=0)
        ats = _src(session, name="ATS", authority=10)
        session.flush()

        agg_job = _job(session, source=agg, ext="agg", title=title, company=company)
        ats_job = _job(session, source=ats, ext="ats", title=title, company=company)
        session.commit()

        try:
            cv_id = _get_real_default_cv_id(session)
            q = _build_query(cv_id, None, None, None, None, False, None, None)
            returned_ids = {str(row[0].id) for row in session.execute(q).all()}

            assert str(ats_job.id) in returned_ids, "ATS job must be surfaced"
            assert str(agg_job.id) not in returned_ids, "Aggregator duplicate must not appear"
        finally:
            # ON DELETE CASCADE removes jobs → job_scores when source is deleted.
            session.delete(agg)
            session.delete(ats)
            session.commit()


def test_dedup_query_surfaces_ats_job_even_when_only_aggregator_is_scored() -> None:
    """ATS row wins dedup even when the aggregator sibling carries the score."""
    company = f"ScoredAgg-{_TAG}"
    title = "Cloud Engineer"

    with SessionLocal() as session:
        cv_id = _get_real_default_cv_id(session)

        agg = _src(session, name="aggregator", authority=0)
        ats = _src(session, name="ATS", authority=10)
        session.flush()

        agg_job = _job(session, source=agg, ext="sagg", title=title, company=company)
        ats_job = _job(session, source=ats, ext="sats", title=title, company=company)
        session.flush()

        if cv_id is not None:
            _score(session, job=agg_job, cv_id=cv_id, score=75)

        session.commit()

        try:
            q = _build_query(cv_id, None, None, None, None, False, None, None)
            returned_ids = {str(row[0].id) for row in session.execute(q).all()}

            # ATS row must win dedup; scored aggregator sibling must not appear.
            assert str(ats_job.id) in returned_ids
            assert str(agg_job.id) not in returned_ids
        finally:
            session.delete(agg)
            session.delete(ats)
            session.commit()


# ---------------------------------------------------------------------------
# Clause 3b: _enqueue_scoring — ATS overrides scored aggregator
# ---------------------------------------------------------------------------


def test_enqueue_scoring_fires_for_ats_when_aggregator_sibling_already_scored() -> None:
    """_enqueue_scoring enqueues an ATS job (auth 10) despite a scored aggregator sibling."""
    company = f"EnqueueCo-{_TAG}"
    title = "DevOps Engineer"

    with SessionLocal() as session:
        cv_id = _get_real_default_cv_id(session)
        if cv_id is None:
            # No real default CV — create a temporary one.
            user = User(email=f"test-{_TAG}@example.com", name="Test")
            session.add(user)
            session.flush()
            cv = CV(
                user_id=user.id,
                name="Test CV",
                raw_text="test",
                parsed={"skills": [], "roles": [], "years_experience": 0, "summary": ""},
                is_default=True,
            )
            session.add(cv)
            session.flush()
            cv_id = cv.id
            created_user_id = user.id
        else:
            created_user_id = None

        agg = _src(session, name="aggregator", authority=0)
        ats = _src(session, name="ATS", authority=10)
        session.flush()

        agg_job = _job(session, source=agg, ext="eq-agg", title=title, company=company)
        ats_job = _job(session, source=ats, ext="eq-ats", title=title, company=company)
        session.flush()

        # Aggregator job already scored.
        _score(session, job=agg_job, cv_id=cv_id, score=65)
        session.commit()

        try:
            enqueued: list[tuple[str, str]] = []

            def fake_delay(job_id: str, cv_id_str: str) -> None:
                enqueued.append((job_id, cv_id_str))

            with patch("app.tasks.scoring.score_job_task.delay", side_effect=fake_delay):
                _enqueue_scoring(session, [ats_job.id], source_authority=10)

            assert (
                len(enqueued) == 1
            ), "ATS job should be enqueued for scoring despite a scored aggregator sibling"
            assert enqueued[0][0] == str(ats_job.id)
        finally:
            session.delete(agg)
            session.delete(ats)
            if created_user_id is not None:
                user_obj = session.get(User, created_user_id)
                if user_obj:
                    session.delete(user_obj)
            session.commit()


def test_enqueue_scoring_skips_when_equal_authority_sibling_already_scored() -> None:
    """_enqueue_scoring skips a job when an equal-authority sibling is already scored."""
    company = f"SkipCo-{_TAG}"
    title = "Backend Engineer"

    with SessionLocal() as session:
        cv_id = _get_real_default_cv_id(session)
        if cv_id is None:
            user = User(email=f"test2-{_TAG}@example.com", name="Test2")
            session.add(user)
            session.flush()
            cv = CV(
                user_id=user.id,
                name="Test CV 2",
                raw_text="test",
                parsed={"skills": [], "roles": [], "years_experience": 0, "summary": ""},
                is_default=True,
            )
            session.add(cv)
            session.flush()
            cv_id = cv.id
            created_user_id = user.id
        else:
            created_user_id = None

        agg1 = _src(session, name="agg1", authority=0)
        agg2 = _src(session, name="agg2", authority=0)
        session.flush()

        scored_job = _job(session, source=agg1, ext="sk-s", title=title, company=company)
        new_job = _job(session, source=agg2, ext="sk-n", title=title, company=company)
        session.flush()

        # Equal-authority sibling already scored.
        _score(session, job=scored_job, cv_id=cv_id, score=60)
        session.commit()

        try:
            enqueued: list[tuple[str, str]] = []

            def fake_delay(job_id: str, cv_id_str: str) -> None:
                enqueued.append((job_id, cv_id_str))

            with patch("app.tasks.scoring.score_job_task.delay", side_effect=fake_delay):
                _enqueue_scoring(session, [new_job.id], source_authority=0)

            assert len(enqueued) == 0, "Should not enqueue: equal-authority sibling already scored"
        finally:
            session.delete(agg1)
            session.delete(agg2)
            if created_user_id is not None:
                user_obj = session.get(User, created_user_id)
                if user_obj:
                    session.delete(user_obj)
            session.commit()
