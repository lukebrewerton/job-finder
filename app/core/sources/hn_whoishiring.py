# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""HN 'Who is hiring?' adapter.

Fetches the current monthly thread via the Algolia HN API, then uses an LLM
to parse each top-level comment (which is a freeform job posting) into a RawJob.

Cost controls:
- Only top-level comments (parent_id == story_id) are processed.
- Comments are pre-filtered to those containing at least one of the profile's
  title keywords (case-insensitive). This greatly reduces LLM calls.
- A hard cap (_MAX_COMMENTS) prevents runaway cost on busy threads.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Iterable
from datetime import datetime

import httpx

from app.core.sources.base import FetchContext, RawJob, RemoteMode, register

_ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
_THREAD_SEARCH = f"{_ALGOLIA_BASE}/search_by_date"
_COMMENT_SEARCH = f"{_ALGOLIA_BASE}/search"
_MAX_COMMENTS = 50


def _find_thread_id() -> str | None:
    """Return the objectID of the most recent 'Who is hiring?' thread."""
    resp = httpx.get(
        _THREAD_SEARCH,
        params={"tags": "story,author_whoishiring", "hitsPerPage": 5},
        timeout=15,
    )
    resp.raise_for_status()
    for hit in resp.json().get("hits", []):
        title = hit.get("title", "")
        if re.search(r"who is hiring", title, re.IGNORECASE) and (
            "wants to be hired" not in title.lower()
        ):
            return str(hit["objectID"])
    return None


def _fetch_top_level_comments(story_id: str) -> list[dict]:
    """Return up to _MAX_COMMENTS top-level comments for a story."""
    params: dict[str, str | int] = {
        "tags": f"comment,story_{story_id}",
        "hitsPerPage": 100,
        "page": 0,
    }
    resp = httpx.get(_COMMENT_SEARCH, params=params, timeout=30)
    resp.raise_for_status()
    hits = resp.json().get("hits", [])
    story_id_int = int(story_id)
    return [h for h in hits if h.get("parent_id") == story_id_int]


def _matches_titles(text: str, titles: list[str]) -> bool:
    if not titles:
        return True
    lower = text.lower()
    return any(t.lower() in lower for t in titles)


@register
class HNWhoIsHiringAdapter:
    key = "hn_whoishiring"
    requires_config = False

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]:
        from app.core.llm.normalise import normalise_hn_comment
        from app.core.llm.provider import get_llm_provider as get_provider

        provider = get_provider()
        story_id = _find_thread_id()
        if story_id is None:
            return

        comments = _fetch_top_level_comments(story_id)

        processed = 0
        for comment in comments:
            if processed >= _MAX_COMMENTS:
                break

            text = comment.get("comment_text", "")
            if not _matches_titles(text, ctx.titles):
                continue

            fields = normalise_hn_comment(text, provider)
            if fields is None:
                continue

            if not fields.get("title") or not fields.get("company"):
                continue

            processed += 1

            posted_at: datetime | None = None
            if created := comment.get("created_at"):
                with contextlib.suppress(ValueError):
                    posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))

            remote_mode_str = fields.get("remote_mode") or "unknown"
            try:
                remote_mode = RemoteMode(remote_mode_str)
            except ValueError:
                remote_mode = RemoteMode.UNKNOWN

            salary_min = fields.get("salary_min")
            salary_max = fields.get("salary_max")
            salary_disclosed = salary_min is not None or salary_max is not None

            url = fields.get("url") or ""
            if not url:
                url = f"https://news.ycombinator.com/item?id={comment['objectID']}"

            yield RawJob(
                external_id=str(comment["objectID"]),
                title=fields["title"],
                company=fields["company"],
                url=url,
                description=text,
                remote_mode=remote_mode,
                location=fields.get("location"),
                salary_min=salary_min,
                salary_max=salary_max,
                salary_currency=fields.get("salary_currency"),
                salary_period="year" if salary_disclosed else None,
                salary_disclosed=salary_disclosed,
                posted_at=posted_at,
                raw=comment,
            )
