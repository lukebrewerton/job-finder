from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.job import Job

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

    model_config = {"from_attributes": True}


class JobsPage(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    page_size: int


@router.get("", response_model=JobsPage)
def list_jobs(
    session: Annotated[Session, Depends(get_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> JobsPage:
    total = session.scalar(select(func.count()).select_from(Job)) or 0
    items = session.scalars(
        select(Job).order_by(Job.fetched_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return JobsPage(items=list(items), total=total, page=page, page_size=page_size)
