from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register

_BASE_URL = "https://remotive.com/api/remote-jobs"
_RESULTS_PER_PAGE = 50


@register
class RemotiveAdapter:
    key = "remotive"
    requires_config = False

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        queries = ctx.titles if ctx.titles else [""]

        seen_ids: set[str] = set()
        for title in queries:
            params: dict[str, str | int] = {"limit": _RESULTS_PER_PAGE}
            if title:
                params["search"] = title

            resp = httpx.get(_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("jobs", []):
                raw = _map_item(item)
                if raw.external_id not in seen_ids:
                    seen_ids.add(raw.external_id)
                    yield raw


def _map_item(item: dict) -> RawJob:
    salary_str = (item.get("salary") or "").strip()
    salary_disclosed = bool(salary_str)

    posted_at: datetime | None = None
    if pub_date := item.get("publication_date"):
        with contextlib.suppress(ValueError):
            posted_at = datetime.fromisoformat(pub_date).replace(tzinfo=UTC)

    return RawJob(
        external_id=str(item["id"]),
        title=item.get("title", ""),
        company=item.get("company_name", ""),
        url=item.get("url", ""),
        description=item.get("description", ""),
        remote_mode=RemoteMode.REMOTE,
        location=item.get("candidate_required_location") or None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        salary_disclosed=salary_disclosed,
        posted_at=posted_at,
        raw=item,
    )
