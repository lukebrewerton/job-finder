# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register

_BASE_URL = "https://himalayas.app/jobs/api"
_RESULTS_PER_PAGE = 100


@register
class HimalayasAdapter:
    key = "himalayas"
    requires_config = False

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        queries = ctx.titles if ctx.titles else [""]

        seen_ids: set[str] = set()
        for title in queries:
            params: dict[str, str | int] = {"limit": _RESULTS_PER_PAGE}
            if title:
                params["q"] = title

            resp = httpx.get(_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("jobs", []):
                raw = _map_item(item)
                if raw.external_id not in seen_ids:
                    seen_ids.add(raw.external_id)
                    yield raw


def _map_item(item: dict) -> RawJob:
    salary_min_raw = item.get("minSalary")
    salary_max_raw = item.get("maxSalary")
    has_salary = salary_min_raw is not None or salary_max_raw is not None

    period_raw = item.get("salaryPeriod") or "annual"
    salary_period = "year" if period_raw == "annual" else period_raw

    posted_at: datetime | None = None
    if pub_date := item.get("pubDate"):
        with contextlib.suppress(ValueError, OSError):
            posted_at = datetime.fromtimestamp(int(pub_date), tz=UTC)

    restrictions = item.get("locationRestrictions") or []
    location = restrictions[0] if restrictions else None

    return RawJob(
        external_id=item.get("guid") or item.get("applicationLink") or "",
        title=item.get("title", ""),
        company=item.get("companyName", ""),
        url=item.get("applicationLink", ""),
        description=item.get("description", ""),
        remote_mode=RemoteMode.REMOTE,
        location=location,
        salary_min=int(salary_min_raw) if salary_min_raw is not None else None,
        salary_max=int(salary_max_raw) if salary_max_raw is not None else None,
        salary_currency=item.get("currency"),
        salary_period=salary_period,
        salary_disclosed=has_salary,
        posted_at=posted_at,
        raw=item,
    )
