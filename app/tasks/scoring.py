"""Celery task: score a job against a CV using the LLM rubric."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import get_settings
from app.db import SessionLocal
from app.models.cv import CV
from app.models.job import Job
from app.models.job_score import JobScore
from app.workers import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="score_job")
def score_job_task(job_id_str: str, cv_id_str: str) -> None:
    job_id = uuid.UUID(job_id_str)
    cv_id = uuid.UUID(cv_id_str)

    with SessionLocal() as session:
        existing = session.scalar(
            select(JobScore.id).where(
                JobScore.job_id == job_id,
                JobScore.cv_id == cv_id,
            )
        )
        if existing is not None:
            log.debug("score already exists for job=%s cv=%s — skipping", job_id_str, cv_id_str)
            return

        job = session.get(Job, job_id)
        cv = session.get(CV, cv_id)
        if job is None or cv is None:
            log.warning("score_job: job or CV not found (job=%s cv=%s)", job_id_str, cv_id_str)
            return

        from app.core.llm.provider import get_llm_provider
        from app.core.llm.scoring import score_job

        provider = get_llm_provider()
        result = score_job(
            job_title=job.title,
            job_company=job.company,
            job_description=job.description or "",
            cv_parsed=cv.parsed or {},
            provider=provider,
        )

        settings = get_settings()
        stmt = (
            pg_insert(JobScore)
            .values(
                id=uuid.uuid4(),
                job_id=job_id,
                cv_id=cv_id,
                profile_id=None,
                fit_score=result["fit_score"],
                matched_skills=result["matched_skills"],
                gaps=result["gaps"],
                flags=result["flags"],
                rationale=result["rationale"],
                model=settings.llm_model,
                scored_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(constraint="uq_job_scores_job_cv")
        )
        session.execute(stmt)
        session.commit()

    log.info(
        "scored job=%s cv=%s fit_score=%d",
        job_id_str,
        cv_id_str,
        result["fit_score"],
    )
