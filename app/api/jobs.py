from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, and_, false, func, not_, or_, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.db import get_session
from app.models.cv import CV
from app.models.job import Job
from app.models.job_score import JobScore
from app.models.job_state import JobState
from app.models.profile import SearchProfile
from app.models.source import Source

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Case-insensitive word-boundary regex for entry-level role detection.
# Applied as NOT match when the active profile has exclude_entry_level=True.
_ENTRY_LEVEL_RE = r"\y(trainee|intern|internship|apprentice|graduate|junior)\y|entry[\s\-]level"


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    company: str
    url: str
    location: str | None
    remote_mode: str
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    salary_disclosed: bool
    source_id: uuid.UUID
    last_seen_at: datetime
    fit_score: int | None = None
    flags: list[str] | None = None
    status: str | None = None
    notes: str | None = None
    applied_at: datetime | None = None

    model_config = {"from_attributes": True}


class JobDetail(JobOut):
    matched_skills: list[str] | None = None
    gaps: list[str] | None = None
    rationale: str | None = None
    summary: str | None = None


class JobsPage(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int


class JobStateIn(BaseModel):
    status: str
    notes: str | None = None


class JobStateOut(BaseModel):
    job_id: uuid.UUID
    status: str
    notes: str | None
    applied_at: datetime | None

    model_config = {"from_attributes": True}


def _default_cv_id(session: Session, user_id: uuid.UUID) -> uuid.UUID | None:
    return session.scalar(
        select(CV.id).where(CV.is_default.is_(True), CV.user_id == user_id).limit(1)
    )


def _active_profile(session: Session, user_id: uuid.UUID) -> SearchProfile | None:
    return session.scalar(
        select(SearchProfile)
        .where(SearchProfile.user_id == user_id, SearchProfile.active.is_(True))
        .limit(1)
    )


def _status_dedup_keys_subquery(user_id: uuid.UUID, statuses: list[str]):
    """Subquery: dedup_keys for jobs the user has set to any of the given statuses."""
    return (
        select(Job.dedup_key)
        .join(JobState, JobState.job_id == Job.id)
        .where(JobState.user_id == user_id, JobState.status.in_(statuses))
        .subquery()
    )


def _build_query(
    cv_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    min_fit: int | None,
    remote_mode: str | None,
    salary_disclosed: bool | None,
    exclude_entry_level: bool,
    status_filter: str | None,
    search: str | None,
) -> Select[tuple[Job, JobScore, JobState]]:
    """Build a scored + deduplicated jobs query.

    Uses DISTINCT ON (dedup_key) so each logical job appears once, preferring the
    sibling that already has a score (avoids showing a blank score when a duplicate
    from another source was scored first).
    """
    cv_join_cond = (
        and_(JobScore.job_id == Job.id, JobScore.cv_id == cv_id) if cv_id is not None else false()
    )
    state_join_cond = (
        and_(JobState.job_id == Job.id, JobState.user_id == user_id)
        if user_id is not None
        else false()
    )

    # Inner: pick one row per dedup_key, preferring ATS sources then scored siblings.
    dedup_inner = (
        select(Job.id.label("job_id"))
        .join(Source, Source.id == Job.source_id)
        .outerjoin(JobScore, cv_join_cond)
        .distinct(Job.dedup_key)
        .order_by(
            Job.dedup_key,
            Source.authority.desc(),
            (JobScore.fit_score.isnot(None)).desc(),
            JobScore.fit_score.desc().nulls_last(),
            Job.fetched_at.desc(),
        )
        .subquery()
    )

    q: Select[tuple[Job, JobScore, JobState]] = (
        select(Job, JobScore, JobState)
        .join(dedup_inner, Job.id == dedup_inner.c.job_id)
        .outerjoin(JobScore, cv_join_cond)
        .outerjoin(JobState, state_join_cond)
    )

    if min_fit is not None:
        q = q.where(JobScore.fit_score >= min_fit)
    if remote_mode is not None:
        q = q.where(Job.remote_mode == remote_mode)
    if salary_disclosed is not None:
        q = q.where(Job.salary_disclosed.is_(salary_disclosed))
    if exclude_entry_level:
        q = q.where(not_(Job.title.op("~*")(_ENTRY_LEVEL_RE)))
    if search:
        term = f"%{search}%"
        q = q.where(or_(Job.title.ilike(term), Job.company.ilike(term)))

    if user_id is not None:
        if status_filter == "applied":
            q = q.where(Job.dedup_key.in_(_status_dedup_keys_subquery(user_id, ["applied"])))
        elif status_filter == "shortlisted":
            q = q.where(Job.dedup_key.in_(_status_dedup_keys_subquery(user_id, ["shortlisted"])))
        else:
            # Active view: hide jobs the user has triaged away.
            q = q.where(
                Job.dedup_key.not_in(
                    _status_dedup_keys_subquery(user_id, ["applied", "rejected", "ignored"])
                )
            )

    return q


@router.get("", response_model=JobsPage)
def list_jobs(
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    min_fit: int | None = Query(None, ge=0, le=100),
    remote_mode: str | None = Query(None),
    salary_disclosed: bool | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None, max_length=200),
) -> JobsPage:
    cv_id = _default_cv_id(session, user.id)
    profile = _active_profile(session, user.id)
    exclude_entry_level = profile.exclude_entry_level if profile else False

    q = _build_query(
        cv_id=cv_id,
        user_id=user.id,
        min_fit=min_fit,
        remote_mode=remote_mode,
        salary_disclosed=salary_disclosed,
        exclude_entry_level=exclude_entry_level,
        status_filter=status,
        search=search,
    )

    total = session.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = session.execute(
        q.order_by(JobScore.fit_score.desc().nulls_last(), Job.fetched_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items: list[JobOut] = []
    for row in rows:
        job: Job = row[0]
        score: JobScore | None = row[1]
        state: JobState | None = row[2]
        items.append(
            JobOut(
                id=job.id,
                title=job.title,
                company=job.company,
                url=job.url,
                location=job.location,
                remote_mode=job.remote_mode,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                salary_currency=job.salary_currency,
                salary_disclosed=job.salary_disclosed,
                source_id=job.source_id,
                last_seen_at=job.last_seen_at,
                fit_score=score.fit_score if score else None,
                flags=score.flags if score else None,
                status=state.status if state else None,
                notes=state.notes if state else None,
                applied_at=state.applied_at if state else None,
            )
        )
    return JobsPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUser,
) -> JobDetail:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    cv_id = _default_cv_id(session, user.id)
    score: JobScore | None = None
    if cv_id is not None:
        score = session.scalar(
            select(JobScore).where(JobScore.job_id == job_id, JobScore.cv_id == cv_id)
        )

    state = session.scalar(
        select(JobState).where(JobState.job_id == job_id, JobState.user_id == user.id)
    )

    return JobDetail(
        id=job.id,
        title=job.title,
        company=job.company,
        url=job.url,
        location=job.location,
        remote_mode=job.remote_mode,
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        salary_currency=job.salary_currency,
        salary_disclosed=job.salary_disclosed,
        source_id=job.source_id,
        last_seen_at=job.last_seen_at,
        fit_score=score.fit_score if score else None,
        flags=score.flags if score else None,
        matched_skills=score.matched_skills if score else None,
        gaps=score.gaps if score else None,
        rationale=score.rationale if score else None,
        summary=score.summary if score else None,
        status=state.status if state else None,
        notes=state.notes if state else None,
        applied_at=state.applied_at if state else None,
    )


@router.put("/{job_id}/state", response_model=JobStateOut)
def set_job_state(
    job_id: uuid.UUID,
    body: JobStateIn,
    session: Annotated[Session, Depends(get_session)],
    user: CurrentUser,
) -> JobState:
    valid_statuses = {"new", "shortlisted", "applied", "rejected", "ignored"}
    if body.status not in valid_statuses:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    state = session.scalar(
        select(JobState).where(JobState.job_id == job_id, JobState.user_id == user.id)
    )
    if state is None:
        state = JobState(user_id=user.id, job_id=job_id)
        session.add(state)

    prev_status = state.status
    state.status = body.status
    state.notes = body.notes

    if body.status == "applied" and prev_status != "applied":
        state.applied_at = datetime.now(UTC)
    elif body.status != "applied":
        state.applied_at = None

    session.commit()
    session.refresh(state)
    return state
