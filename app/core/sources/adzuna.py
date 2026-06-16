from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register

_BASE_URL = "https://api.adzuna.com/v1/api/jobs/gb/search"
_RESULTS_PER_PAGE = 50

# Patterns checked in priority order: most specific first.
# "Hybrid" beats "remote" because hybrid roles often say both ("hybrid remote").
_RE_FULLY_REMOTE = re.compile(r"\b(fully\s+remote|100\s*%\s*remote|remote\s+only)\b", re.IGNORECASE)
_RE_REMOTE_FIRST = re.compile(r"\bremote[\s-]first\b", re.IGNORECASE)
_RE_HYBRID = re.compile(r"\bhybrid\b", re.IGNORECASE)
_RE_REMOTE = re.compile(r"\bremote\b", re.IGNORECASE)
_RE_ONSITE = re.compile(r"\b(onsite|on[\s-]site|in[\s-]office|office[\s-]based)\b", re.IGNORECASE)


def _infer_remote_mode(title: str, description: str) -> RemoteMode:
    text = f"{title} {description}"
    if _RE_FULLY_REMOTE.search(text):
        return RemoteMode.REMOTE
    if _RE_REMOTE_FIRST.search(text):
        return RemoteMode.REMOTE_FIRST
    if _RE_HYBRID.search(text):
        return RemoteMode.HYBRID
    if _RE_REMOTE.search(text):
        return RemoteMode.REMOTE
    if _RE_ONSITE.search(text):
        return RemoteMode.ONSITE
    return RemoteMode.UNKNOWN


@register
class AdzunaAdapter:
    key = "adzuna"
    requires_config = False  # credentials come from global settings

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        from app.config import get_settings

        settings = get_settings()
        queries = ctx.titles if ctx.titles else [""]

        for title in queries:
            params: dict[str, str | int] = {
                "app_id": settings.adzuna_app_id,
                "app_key": settings.adzuna_app_key,
                "results_per_page": _RESULTS_PER_PAGE,
                "content-type": "application/json",
            }
            if title:
                params["what"] = title

            resp = httpx.get(f"{_BASE_URL}/1", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                yield _map_item(item)


def _map_item(item: dict) -> RawJob:
    salary_min_raw = item.get("salary_min")
    salary_max_raw = item.get("salary_max")
    has_salary = salary_min_raw is not None or salary_max_raw is not None
    # salary_is_predicted is a string "0" (real figure) or "1" (estimated)
    salary_disclosed = has_salary and item.get("salary_is_predicted") == "0"

    posted_at: datetime | None = None
    if created := item.get("created"):
        posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))

    return RawJob(
        external_id=str(item["id"]),
        title=item["title"],
        company=item.get("company", {}).get("display_name", ""),
        url=item["redirect_url"],
        description=item.get("description", ""),
        remote_mode=_infer_remote_mode(item["title"], item.get("description", "")),
        location=item.get("location", {}).get("display_name"),
        salary_min=int(salary_min_raw) if salary_min_raw is not None else None,
        salary_max=int(salary_max_raw) if salary_max_raw is not None else None,
        salary_currency="GBP",
        salary_period="year",
        salary_disclosed=salary_disclosed,
        posted_at=posted_at,
        raw=item,
    )
