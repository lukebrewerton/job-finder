from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register
from app.core.sources.utils import infer_remote_mode

_BASE_URL = "https://www.reed.co.uk/api/1.0/search"
_RESULTS_PER_PAGE = 100


@register
class ReedAdapter:
    key = "reed"
    requires_config = False

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        from app.config import get_settings

        api_key = get_settings().reed_api_key
        queries = ctx.titles if ctx.titles else [""]

        for title in queries:
            params: dict[str, str | int] = {"resultsToTake": _RESULTS_PER_PAGE}
            if title:
                params["keywords"] = title

            resp = httpx.get(
                _BASE_URL,
                params=params,
                auth=(api_key, ""),
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                yield _map_item(item)


def _map_item(item: dict) -> RawJob:
    salary_min_raw = item.get("minimumSalary")
    salary_max_raw = item.get("maximumSalary")
    has_salary = salary_min_raw is not None or salary_max_raw is not None

    posted_at: datetime | None = None
    if date_str := item.get("date"):
        with contextlib.suppress(ValueError):
            # Reed returns dates as "DD/MM/YYYY"
            posted_at = datetime.strptime(date_str, "%d/%m/%Y").replace(tzinfo=UTC)

    title = item.get("jobTitle", "")
    description = item.get("jobDescription", "")
    remote_mode = (
        RemoteMode.REMOTE if item.get("is_remote") else infer_remote_mode(title, description)
    )

    return RawJob(
        external_id=str(item["jobId"]),
        title=title,
        company=item.get("employerName", ""),
        url=item.get("jobUrl", ""),
        description=description,
        remote_mode=remote_mode,
        location=item.get("locationName"),
        salary_min=int(salary_min_raw) if salary_min_raw is not None else None,
        salary_max=int(salary_max_raw) if salary_max_raw is not None else None,
        salary_currency=item.get("currency") or "GBP",
        salary_period="year",
        salary_disclosed=has_salary,
        posted_at=posted_at,
        raw=item,
    )
