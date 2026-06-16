from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, and_, false, func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.cv import CV
from app.models.job import Job
from app.models.job_score import JobScore
from app.models.source import Source

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


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
    fit_score: int | None = None
    flags: list[str] | None = None

    model_config = {"from_attributes": True}


class JobDetail(JobOut):
    matched_skills: list[str] | None = None
    gaps: list[str] | None = None
    rationale: str | None = None


class JobsPage(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int


def _default_cv_id(session: Session) -> uuid.UUID | None:
    return session.scalar(select(CV.id).where(CV.is_default.is_(True)).limit(1))


def _build_query(
    cv_id: uuid.UUID | None,
    min_fit: int | None,
    remote_mode: str | None,
    salary_disclosed: bool | None,
) -> Select[tuple[Job, JobScore]]:
    """Build a scored + deduplicated jobs query.

    Uses DISTINCT ON (dedup_key) so each logical job appears once, preferring the
    sibling that already has a score (avoids showing a blank score when a duplicate
    from another source was scored first).
    """
    cv_join_cond = (
        and_(JobScore.job_id == Job.id, JobScore.cv_id == cv_id) if cv_id is not None else false()
    )

    # Inner: pick one row per dedup_key, preferring ATS sources then scored siblings.
    dedup_inner = (
        select(Job.id.label("job_id"))
        .join(Source, Source.id == Job.source_id)
        .outerjoin(JobScore, cv_join_cond)
        .distinct(Job.dedup_key)
        .order_by(
            Job.dedup_key,
            Source.authority.desc(),  # ATS rows beat aggregators
            (JobScore.fit_score.isnot(None)).desc(),
            JobScore.fit_score.desc().nulls_last(),
            Job.fetched_at.desc(),
        )
        .subquery()
    )

    q: Select[tuple[Job, JobScore]] = (
        select(Job, JobScore)
        .join(dedup_inner, Job.id == dedup_inner.c.job_id)
        .outerjoin(JobScore, cv_join_cond)
    )

    if min_fit is not None:
        q = q.where(JobScore.fit_score >= min_fit)
    if remote_mode is not None:
        q = q.where(Job.remote_mode == remote_mode)
    if salary_disclosed is not None:
        q = q.where(Job.salary_disclosed.is_(salary_disclosed))

    return q


@router.get("", response_model=JobsPage)
def list_jobs(
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    min_fit: int | None = Query(None, ge=0, le=100),
    remote_mode: str | None = Query(None),
    salary_disclosed: bool | None = Query(None),
) -> JobsPage:
    cv_id = _default_cv_id(session)
    q = _build_query(cv_id, min_fit, remote_mode, salary_disclosed)

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
                fit_score=score.fit_score if score else None,
                flags=score.flags if score else None,
            )
        )
    return JobsPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> JobDetail:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    cv_id = _default_cv_id(session)
    score: JobScore | None = None
    if cv_id is not None:
        score = session.scalar(
            select(JobScore).where(JobScore.job_id == job_id, JobScore.cv_id == cv_id)
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
        fit_score=score.fit_score if score else None,
        flags=score.flags if score else None,
        matched_skills=score.matched_skills if score else None,
        gaps=score.gaps if score else None,
        rationale=score.rationale if score else None,
    )
