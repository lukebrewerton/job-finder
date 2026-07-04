# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""LLM-based normalisation for unstructured job postings (e.g. HN comments).

Only called for sources that cannot provide structured fields directly.
Structured API sources must NOT use this — map fields directly instead.
"""

from __future__ import annotations

import re

from app.core.llm.provider import LLMProvider

_TAG_RE = re.compile(r"<[^>]+>")
_AMP_RE = re.compile(r"&amp;|&lt;|&gt;|&quot;|&#x27;|&#[0-9]+;")
_AMP_MAP = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#x27;": "'"}

_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Job title extracted from the posting."},
        "company": {"type": "string", "description": "Company name."},
        "url": {
            "type": "string",
            "description": "Application URL if present, else empty string.",
        },
        "location": {
            "type": ["string", "null"],
            "description": "Location or region if stated, else null.",
        },
        "remote_mode": {
            "type": "string",
            "enum": ["remote", "remote_first", "hybrid", "onsite", "unknown"],
            "description": (
                "remote: fully remote. remote_first: remote-first culture. "
                "hybrid: mix of office and remote. onsite: office-required. "
                "unknown: not stated."
            ),
        },
        "salary_min": {
            "type": ["integer", "null"],
            "description": "Minimum annual salary as integer (e.g. 130000), or null.",
        },
        "salary_max": {
            "type": ["integer", "null"],
            "description": "Maximum annual salary as integer, or null.",
        },
        "salary_currency": {
            "type": ["string", "null"],
            "description": "ISO currency code (e.g. USD, GBP), or null.",
        },
        "is_job_posting": {
            "type": "boolean",
            "description": "True if this comment is a genuine job posting, False otherwise.",
        },
    },
    "required": [
        "title",
        "company",
        "url",
        "location",
        "remote_mode",
        "salary_min",
        "salary_max",
        "salary_currency",
        "is_job_posting",
    ],
    "additionalProperties": False,
}


def _clean_html(text: str) -> str:
    """Strip HTML tags and decode common entities."""
    text = _TAG_RE.sub(" ", text)
    for entity, char in _AMP_MAP.items():
        text = text.replace(entity, char)
    # Catch remaining numeric entities
    text = _AMP_RE.sub(" ", text)
    return " ".join(text.split())


def normalise_hn_comment(raw_html: str, provider: LLMProvider) -> dict | None:
    """Parse a free-form HN job comment into structured fields.

    Returns a dict with keys matching RawJob fields, or None if the comment
    is not a genuine job posting.
    """
    text = _clean_html(raw_html)[:3000]

    prompt = (
        "You are parsing a comment from Hacker News 'Who is hiring?' thread.\n\n"
        f"COMMENT:\n{text}\n\n"
        "Extract the following fields and return a JSON object with exactly these keys:\n"
        "- is_job_posting: boolean, true if this is a genuine job posting\n"
        "- title: string, the job title\n"
        "- company: string, the company name\n"
        "- url: string, the application URL (empty string if not found)\n"
        "- location: string or null, location/region if stated\n"
        "- remote_mode: one of: remote, remote_first, hybrid, onsite, unknown\n"
        "- salary_min: integer or null, minimum annual salary in the stated currency\n"
        "- salary_max: integer or null, maximum annual salary in the stated currency\n"
        "- salary_currency: string or null, ISO currency code (e.g. USD, GBP)\n"
        "If the comment is not a job posting, set is_job_posting to false and "
        "leave other fields as empty strings or null."
    )

    raw = provider.generate_json(prompt, _SCHEMA)

    if not raw.get("is_job_posting"):
        return None

    return {
        "title": str(raw.get("title") or "").strip(),
        "company": str(raw.get("company") or "").strip(),
        "url": str(raw.get("url") or "").strip(),
        "location": raw.get("location") or None,
        "remote_mode": raw.get("remote_mode") or "unknown",
        "salary_min": raw.get("salary_min"),
        "salary_max": raw.get("salary_max"),
        "salary_currency": raw.get("salary_currency"),
    }
