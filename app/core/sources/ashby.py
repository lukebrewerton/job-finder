# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Ashby HQ ATS adapter.

Fetches a company's job board from the Ashby public posting API.
Requires `board_token` in source config (the organisation's Ashby slug).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register

_BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{token}"

_WORKPLACE_MAP: dict[str, RemoteMode] = {
    "remote": RemoteMode.REMOTE,
    "hybrid": RemoteMode.HYBRID,
    "onsite": RemoteMode.ONSITE,
}


@register
class AshbyAdapter:
    key = "ashby"
    requires_config = True

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        token = ctx.config.get("board_token", "")
        if not token:
            raise ValueError("Ashby source requires config.board_token")

        url = _BASE_URL.format(token=token)
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for item in data.get("jobs", []):
            if not item.get("isListed", True):
                continue
            yield _map_item(item, token)


def _map_item(item: dict, company_fallback: str) -> RawJob:
    title = item.get("title", "")

    workplace_raw = (item.get("workplaceType") or "").lower()
    if item.get("isRemote") and workplace_raw not in _WORKPLACE_MAP:
        remote_mode = RemoteMode.REMOTE
    else:
        remote_mode = _WORKPLACE_MAP.get(workplace_raw, RemoteMode.UNKNOWN)

    location = item.get("location") or ""
    if not location:
        country = (item.get("address") or {}).get("postalAddress", {}).get("addressCountry", "")
        location = country

    posted_at: datetime | None = None
    if published := item.get("publishedAt"):
        with contextlib.suppress(ValueError):
            posted_at = datetime.fromisoformat(published.replace("Z", "+00:00")).astimezone(UTC)

    compensation = item.get("compensation") or {}
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_disclosed = False

    components = compensation.get("summaryComponents") or []
    if components:
        comp = components[0]
        if comp.get("min") is not None:
            salary_min = int(comp["min"])
        if comp.get("max") is not None:
            salary_max = int(comp["max"])
        salary_currency = compensation.get("currency")
        interval = (compensation.get("interval") or "").lower()
        salary_period = {"year": "year", "month": "month", "hour": "hour"}.get(interval)
        salary_disclosed = salary_min is not None or salary_max is not None

    url = item.get("jobUrl") or item.get("applyUrl") or ""
    description = item.get("descriptionPlain") or item.get("descriptionHtml") or ""

    return RawJob(
        external_id=str(item["id"]),
        title=title,
        company=company_fallback,
        url=url,
        description=description,
        remote_mode=remote_mode,
        location=location or None,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_currency=salary_currency,
        salary_period=salary_period,
        salary_disclosed=salary_disclosed,
        posted_at=posted_at,
        raw=item,
    )
