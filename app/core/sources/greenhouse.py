"""Greenhouse ATS adapter.

Fetches a company's entire public job board. Requires `board_token` in source config.
No keyword filtering — the whole board is ingested and dedup handles overlap with aggregators.
"""

from __future__ import annotations

import contextlib
import html
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register
from app.core.sources.utils import infer_remote_mode

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


@register
class GreenhouseAdapter:
    key = "greenhouse"
    requires_config = True

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        token = ctx.config.get("board_token", "")
        if not token:
            raise ValueError("Greenhouse source requires config.board_token")

        url = _BASE_URL.format(token=token)
        resp = httpx.get(url, params={"content": "true"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        company = data.get("company", {}).get("name", "") or token
        for item in data.get("jobs", []):
            yield _map_item(item, company)


def _map_item(item: dict, company: str) -> RawJob:
    title = item.get("title", "")
    location = (item.get("location") or {}).get("name") or ""

    # content is HTML-entity-encoded HTML; decode entities for readability
    raw_content = item.get("content", "") or ""
    description = html.unescape(raw_content)

    remote_mode = _infer_from_location(location, title, description)

    posted_at: datetime | None = None
    if date_str := item.get("first_published") or item.get("updated_at"):
        with contextlib.suppress(ValueError):
            posted_at = datetime.fromisoformat(date_str.replace("Z", "+00:00")).astimezone(UTC)

    return RawJob(
        external_id=str(item["id"]),
        title=title,
        company=item.get("company_name") or company,
        url=item.get("absolute_url", ""),
        description=description,
        remote_mode=remote_mode,
        location=location or None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        salary_period=None,
        salary_disclosed=False,
        posted_at=posted_at,
        raw=item,
    )


def _infer_from_location(location: str, title: str, description: str) -> RemoteMode:
    # Many Greenhouse boards encode remote status in the location field.
    loc_lower = location.lower()
    if "remote" in loc_lower:
        return RemoteMode.REMOTE
    # Fall back to text inference on title + description.
    return infer_remote_mode(title, description)
