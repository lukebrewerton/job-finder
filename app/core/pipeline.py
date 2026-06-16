"""Fetch → normalise → dedup → upsert pipeline for a single source."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

import app.core.sources  # noqa: F401 — side-effect: registers all adapters
from app.core.dedup import make_content_hash, make_dedup_key
from app.core.sources.base import FetchContext, RemoteMode, get_adapter
from app.models.job import Job
from app.models.source import Source

log = logging.getLogger(__name__)


def run_fetch(source_key: str, titles: list[str], session: Session) -> dict[str, int | str]:
    source = session.scalars(select(Source).where(Source.type == source_key)).first()
    if source is None:
        raise ValueError(f"No source row found for type={source_key!r}. Run `make seed` first.")

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

    for raw in get_adapter(source_key).fetch(ctx):
        fetched += 1
        content_hash = make_content_hash(raw.title, raw.company, raw.location)
        dedup_key = make_dedup_key(raw.title, raw.company, raw.location)

        if raw.external_id in existing:
            if existing[raw.external_id] == content_hash:
                skipped += 1
                continue
            updated += 1
        else:
            new += 1

        stmt = (
            pg_insert(Job)
            .values(
                id=uuid.uuid4(),
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
                    "content_hash": content_hash,
                    "dedup_key": dedup_key,
                    "updated_at": now,
                },
            )
        )
        session.execute(stmt)

    session.commit()
    source.last_run_at = now
    session.commit()

    counts: dict[str, int | str] = {
        "source": source_key,
        "fetched": fetched,
        "new": new,
        "updated": updated,
        "skipped": skipped,
    }
    log.info("fetch complete", extra=counts)
    return counts
