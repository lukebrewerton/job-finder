# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""JSON-LD careers page adapter.

Given a `url` in source config, fetches the page HTML and extracts
schema.org JobPosting blocks from <script type="application/ld+json"> tags.
Structured, low-fragility — does not scrape free-form HTML.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register
from app.core.sources.utils import infer_remote_mode

_SCRIPT_RE = re.compile(
    r'<script[^>]+type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobFinderBot/1.0; +https://github.com/)",
    "Accept": "text/html,application/xhtml+xml",
}


@register
class JsonLdAdapter:
    key = "jsonld"
    requires_config = True

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        url = ctx.config.get("url", "")
        if not url:
            raise ValueError("JSON-LD source requires config.url")

        company = ctx.config.get("company", "")

        resp = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=30)
        resp.raise_for_status()

        for posting in _extract_job_postings(resp.text):
            raw = _map_posting(posting, company)
            if raw is not None:
                yield raw


def _extract_job_postings(html: str) -> list[dict]:
    postings: list[dict] = []
    for match in _SCRIPT_RE.finditer(html):
        with contextlib.suppress(json.JSONDecodeError, ValueError):
            data = json.loads(match.group(1))
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict) and "@graph" in data:
                items = data["@graph"]
            else:
                items = [data]
            for item in items:
                if isinstance(item, dict) and _is_job_posting(item):
                    postings.append(item)
    return postings


def _is_job_posting(obj: dict) -> bool:
    type_val = obj.get("@type", "")
    if isinstance(type_val, list):
        return "JobPosting" in type_val
    return type_val == "JobPosting"


def _map_posting(posting: dict, company_fallback: str) -> RawJob | None:
    title = posting.get("title") or posting.get("name") or ""
    if not title:
        return None

    company_obj = posting.get("hiringOrganization") or {}
    company = (
        company_obj.get("name") if isinstance(company_obj, dict) else str(company_obj)
    ) or company_fallback
    if not company:
        return None

    url = posting.get("url") or posting.get("sameAs") or ""

    description = posting.get("description") or ""

    location = _extract_location(posting)

    job_location_type = posting.get("jobLocationType") or ""
    if job_location_type.upper() == "TELECOMMUTE":
        remote_mode = RemoteMode.REMOTE
    else:
        remote_mode = infer_remote_mode(title, description)

    posted_at: datetime | None = None
    if date_str := posting.get("datePosted"):
        with contextlib.suppress(ValueError):
            posted_at = datetime.fromisoformat(str(date_str)).replace(tzinfo=UTC)

    salary_min, salary_max, salary_currency, salary_period, salary_disclosed = _extract_salary(
        posting
    )

    external_id = posting.get("identifier") or posting.get("url") or title
    if isinstance(external_id, dict):
        external_id = external_id.get("value") or title

    return RawJob(
        external_id=str(external_id),
        title=title,
        company=company,
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
        raw=posting,
    )


def _extract_location(posting: dict) -> str:
    loc = posting.get("jobLocation")
    if not loc:
        return ""
    if isinstance(loc, list):
        loc = loc[0]
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, str):
            return addr
        if isinstance(addr, dict):
            parts = [
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("addressCountry"),
            ]
            return ", ".join(p for p in parts if p)
    return str(loc) if loc else ""


def _extract_salary(
    posting: dict,
) -> tuple[int | None, int | None, str | None, str | None, bool]:
    base = posting.get("baseSalary")
    if not base or not isinstance(base, dict):
        return None, None, None, None, False

    value = base.get("value") or {}
    currency = base.get("currency")
    # unitText may appear on the outer MonetaryAmount or inner QuantitativeValue.
    unit_raw = base.get("unitText") or (value.get("unitText") if isinstance(value, dict) else None)
    period_map = {"YEAR": "year", "MONTH": "month", "HOUR": "hour", "DAY": "day"}
    period = period_map.get((unit_raw or "").upper())

    if isinstance(value, dict):
        min_val = value.get("minValue")
        max_val = value.get("maxValue")
        single = value.get("value")
        salary_min = int(min_val) if min_val is not None else (int(single) if single else None)
        salary_max = int(max_val) if max_val is not None else None
    elif isinstance(value, (int, float)):
        salary_min = int(value)
        salary_max = None
    else:
        return None, None, None, None, False

    disclosed = salary_min is not None or salary_max is not None
    return salary_min, salary_max, currency, period, disclosed
