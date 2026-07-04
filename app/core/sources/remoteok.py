# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register

_API_URL = "https://remoteok.com/api"


@register
class RemoteOKAdapter:
    key = "remoteok"
    requires_config = False

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        resp = httpx.get(
            _API_URL,
            headers={"User-Agent": "job-finder/1.0"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        # First element is a header/legal object, not a job; skip it.
        for item in data[1:]:
            if "id" not in item:
                continue
            yield _map_item(item)


def _map_item(item: dict) -> RawJob:
    salary_min_raw = item.get("salary_min") or 0
    salary_max_raw = item.get("salary_max") or 0
    salary_min = int(salary_min_raw) if salary_min_raw > 0 else None
    salary_max = int(salary_max_raw) if salary_max_raw > 0 else None
    salary_disclosed = salary_min is not None or salary_max is not None

    posted_at: datetime | None = None
    if date_str := item.get("date"):
        with contextlib.suppress(ValueError):
            posted_at = datetime.fromisoformat(date_str)

    location = item.get("location") or None
    if location:
        location = location.strip().strip(",").strip() or None

    return RawJob(
        external_id=str(item["id"]),
        title=item.get("position", ""),
        company=item.get("company", ""),
        url=item.get("url") or item.get("apply_url", ""),
        description=item.get("description", ""),
        remote_mode=RemoteMode.REMOTE,
        location=location,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency="USD" if salary_disclosed else None,
        salary_period="year" if salary_disclosed else None,
        salary_disclosed=salary_disclosed,
        posted_at=posted_at,
        raw=item,
    )
