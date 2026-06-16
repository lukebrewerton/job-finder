"""Lever ATS adapter.

Fetches a company's entire public job board via the Lever v0 postings API.
Requires `board_token` in source config (the company's Lever slug).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from datetime import UTC, datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register
from app.core.sources.utils import infer_remote_mode

_BASE_URL = "https://api.lever.co/v0/postings/{token}"

_WORKPLACE_MAP: dict[str, RemoteMode] = {
    "remote": RemoteMode.REMOTE,
    "hybrid": RemoteMode.HYBRID,
    "onsite": RemoteMode.ONSITE,
    "on-site": RemoteMode.ONSITE,
}


@register
class LeverAdapter:
    key = "lever"
    requires_config = True

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        token = ctx.config.get("board_token", "")
        if not token:
            raise ValueError("Lever source requires config.board_token")

        url = _BASE_URL.format(token=token)
        resp = httpx.get(url, params={"mode": "json"}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, dict) and not data.get("ok", True):
            raise ValueError(f"Lever API error for {token!r}: {data.get('error')}")

        postings: list[dict] = data if isinstance(data, list) else []
        for item in postings:
            yield _map_item(item, token)


def _map_item(item: dict, company_fallback: str) -> RawJob:
    title = item.get("text", "")
    categories = item.get("categories") or {}
    location = categories.get("location") or ""

    workplace_raw = (item.get("workplaceType") or "").lower()
    remote_mode = _WORKPLACE_MAP.get(workplace_raw) or infer_remote_mode(
        title, item.get("descriptionPlain", "")
    )

    posted_at: datetime | None = None
    if created_ms := item.get("createdAt"):
        with contextlib.suppress(Exception):
            posted_at = datetime.fromtimestamp(int(created_ms) / 1000, tz=UTC)

    url = item.get("hostedUrl") or item.get("applyUrl") or ""

    return RawJob(
        external_id=str(item["id"]),
        title=title,
        company=item.get("company") or company_fallback,
        url=url,
        description=item.get("descriptionPlain") or item.get("description") or "",
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
