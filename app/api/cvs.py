# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import io
import uuid

from fastapi import APIRouter, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select, update

from app.api.deps import CurrentUser, DbSession
from app.core.llm.cv_parse import parse_cv
from app.core.llm.provider import get_llm_provider
from app.models.cv import CV
from app.models.job import Job
from app.models.job_score import JobScore

router = APIRouter(prefix="/api/cvs", tags=["cvs"])


def _enqueue_rescore(cv_id: uuid.UUID, session: DbSession) -> int:
    from app.tasks.scoring import score_job_task

    # Clear existing scores so the task's idempotency check doesn't skip them.
    # Safe for new CVs (no-op) and correct for explicit re-scores.
    session.execute(delete(JobScore).where(JobScore.cv_id == cv_id))
    session.commit()

    job_ids = list(session.scalars(select(Job.id)))
    cv_str = str(cv_id)
    for jid in job_ids:
        score_job_task.delay(str(jid), cv_str)
    return len(job_ids)


class CVOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    parsed: dict
    version: int
    is_default: bool

    model_config = {"from_attributes": True}


def _extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        import docx

        doc = docx.Document(io.BytesIO(content))
        return "\n".join(para.text for para in doc.paragraphs)
    # Plain text (or unknown extension) — decode as UTF-8.
    return content.decode("utf-8", errors="replace")


@router.get("", response_model=list[CVOut])
def list_cvs(session: DbSession, user: CurrentUser) -> list[CV]:
    return list(session.scalars(select(CV).where(CV.user_id == user.id)).all())


@router.post("", response_model=CVOut, status_code=201)
async def upload_cv(
    file: UploadFile,
    session: DbSession,
    user: CurrentUser,
) -> CV:
    filename = file.filename or "cv.txt"
    content = await file.read()
    raw_text = _extract_text(filename, content)

    provider = get_llm_provider()
    parsed = parse_cv(raw_text, provider)

    # Make this the default; clear the flag on all existing CVs for this user.
    session.execute(update(CV).where(CV.user_id == user.id).values(is_default=False))

    cv = CV(
        user_id=user.id,
        name=filename,
        raw_text=raw_text,
        parsed=parsed,
        version=1,
        is_default=True,
    )
    session.add(cv)
    session.commit()
    session.refresh(cv)
    _enqueue_rescore(cv.id, session)
    return cv


@router.get("/{cv_id}", response_model=CVOut)
def get_cv(cv_id: uuid.UUID, session: DbSession, user: CurrentUser) -> CV:
    cv = session.get(CV, cv_id)
    if cv is None or cv.user_id != user.id:
        raise HTTPException(status_code=404, detail="CV not found.")
    return cv


@router.post("/{cv_id}/rescore")
def rescore_cv(cv_id: uuid.UUID, session: DbSession, user: CurrentUser) -> dict[str, int]:
    cv = session.get(CV, cv_id)
    if cv is None or cv.user_id != user.id:
        raise HTTPException(status_code=404, detail="CV not found.")
    enqueued = _enqueue_rescore(cv_id, session)
    return {"enqueued": enqueued}


@router.put("/{cv_id}/default", response_model=CVOut)
def set_default_cv(cv_id: uuid.UUID, session: DbSession, user: CurrentUser) -> CV:
    cv = session.get(CV, cv_id)
    if cv is None or cv.user_id != user.id:
        raise HTTPException(status_code=404, detail="CV not found.")
    session.execute(update(CV).where(CV.user_id == user.id).values(is_default=False))
    cv.is_default = True
    session.commit()
    session.refresh(cv)
    return cv
