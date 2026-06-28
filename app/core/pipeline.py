"""Fetch → normalise → dedup → upsert pipeline for a single source."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

import app.core.sources  # noqa: F401 — side-effect: registers all adapters
from app.core.dedup import make_content_hash, make_dedup_key
from app.core.sources.base import FetchContext, RemoteMode, get_adapter
from app.models.cv import CV
from app.models.job import Job
from app.models.job_score import JobScore
from app.models.source import Source

log = logging.getLogger(__name__)


def run_fetch(source_key: str, titles: list[str], session: Session) -> list[dict[str, int | str]]:
    """Run fetch for all enabled sources with the given adapter type."""
    sources = session.scalars(
        select(Source).where(Source.type == source_key, Source.enabled.is_(True))
    ).all()
    if not sources:
        raise ValueError(f"No source row found for type={source_key!r}. Run `make seed` first.")
    return [run_fetch_source(source, titles, session) for source in sources]


def run_fetch_source(source: Source, titles: list[str], session: Session) -> dict[str, int | str]:
    """Run fetch for a single Source row."""
    ctx = FetchContext(
        titles=titles,
        locations=None,
        remote_modes=list(RemoteMode),
        config=source.config or {},
        since=source.last_run_at,
    )

    now = datetime.now(UTC)

    existing: dict[str, str] = {
        row.external_id: row.content_hash
        for row in session.execute(
            select(Job.external_id, Job.content_hash).where(Job.source_id == source.id)
        ).all()
    }

    fetched = new = updated = skipped = 0
    new_job_ids: list[uuid.UUID] = []
    seen_external_ids: list[str] = []

    for raw in get_adapter(source.type).fetch(ctx):
        fetched += 1
        content_hash = make_content_hash(raw.title, raw.company, raw.location)
        dedup_key = make_dedup_key(raw.title, raw.company, raw.location)

        is_new = raw.external_id not in existing
        seen_external_ids.append(raw.external_id)
        if not is_new:
            if existing[raw.external_id] == content_hash:
                skipped += 1
                continue
            updated += 1
        else:
            new += 1

        job_id = uuid.uuid4()
        if is_new:
            new_job_ids.append(job_id)

        stmt = (
            pg_insert(Job)
            .values(
                id=job_id,
                source_id=source.id,
                external_id=raw.external_id,
                title=raw.title,
                company=raw.company,
                url=raw.url,
                description=raw.description,
                remote_mode=raw.remote_mode.value,
                location=raw.location,
                salary_min=raw.salary_min,
                salary_max=raw.salary_max,
                salary_currency=raw.salary_currency,
                salary_period=raw.salary_period,
                salary_disclosed=raw.salary_disclosed,
                posted_at=raw.posted_at,
                fetched_at=now,
                last_seen_at=now,
                content_hash=content_hash,
                dedup_key=dedup_key,
            )
            .on_conflict_do_update(
                constraint="uq_jobs_source_external",
                set_={
                    "title": raw.title,
                    "company": raw.company,
                    "url": raw.url,
                    "description": raw.description,
                    "remote_mode": raw.remote_mode.value,
                    "location": raw.location,
                    "salary_min": raw.salary_min,
                    "salary_max": raw.salary_max,
                    "salary_currency": raw.salary_currency,
                    "salary_period": raw.salary_period,
                    "salary_disclosed": raw.salary_disclosed,
                    "posted_at": raw.posted_at,
                    "fetched_at": now,
                    "last_seen_at": now,
                    "content_hash": content_hash,
                    "dedup_key": dedup_key,
                    "updated_at": now,
                },
            )
        )
        session.execute(stmt)

    # Bump last_seen_at for skipped jobs (content unchanged — not touched by the upsert above).
    if seen_external_ids:
        session.execute(
            update(Job)
            .where(Job.source_id == source.id, Job.external_id.in_(seen_external_ids))
            .values(last_seen_at=now)
        )

    session.commit()
    source.last_run_at = now
    session.commit()

    _enqueue_scoring(session, new_job_ids, source.authority)

    counts: dict[str, int | str] = {
        "source": source.type,
        "source_name": source.name,
        "fetched": fetched,
        "new": new,
        "updated": updated,
        "skipped": skipped,
    }
    log.info("fetch complete", extra={"source": source.type, "fetched": fetched, "new": new})
    return counts


def _enqueue_scoring(session: Session, job_ids: list[uuid.UUID], source_authority: int) -> None:
    if not job_ids:
        return

    from app.tasks.scoring import score_job_task

    default_cv_ids = list(session.scalars(select(CV.id).where(CV.is_default.is_(True))))
    if not default_cv_ids:
        log.info("no default CV set — skipping scoring enqueue for %d new jobs", len(job_ids))
        return

    new_job_rows = session.execute(select(Job.id, Job.dedup_key).where(Job.id.in_(job_ids))).all()
    new_dedup_keys = [row.dedup_key for row in new_job_rows]

    total_enqueued = 0
    for cv_id in default_cv_ids:
        # For dedup_keys that already have a scored sibling against this CV, record the
        # maximum authority of that sibling's source. We only skip enqueueing if a sibling
        # of equal or higher authority is already scored — an ATS job must always be scored
        # even when an aggregator duplicate was scored first.
        scored_max_authority: dict[str, int] = {
            str(row[0]): int(row[1])
            for row in session.execute(
                select(Job.dedup_key, func.max(Source.authority))
                .join(JobScore, JobScore.job_id == Job.id)
                .join(Source, Source.id == Job.source_id)
                .where(JobScore.cv_id == cv_id)
                .where(Job.dedup_key.in_(new_dedup_keys))
                .group_by(Job.dedup_key)
            ).all()
        }

        cv_id_str = str(cv_id)
        enqueued = 0
        for row in new_job_rows:
            existing_auth = scored_max_authority.get(row.dedup_key, -1)
            if existing_auth >= source_authority:
                continue  # sibling of equal-or-higher authority already scored for this CV
            score_job_task.delay(str(row.id), cv_id_str)
            enqueued += 1

        log.info(
            "enqueued scoring for %d/%d new jobs against cv=%s",
            enqueued,
            len(job_ids),
            cv_id_str,
        )
        total_enqueued += enqueued

    log.info("total scoring tasks enqueued: %d across %d CVs", total_enqueued, len(default_cv_ids))
