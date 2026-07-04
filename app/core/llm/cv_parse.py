# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CV parsing: raw text → structured summary used by the scoring rubric.

This is a 4th LLM use beyond the spec's three named lanes — included because deterministic
extraction of skills, roles, and years_experience from free-form CV text is not feasible.
"""

from __future__ import annotations

from app.core.llm.provider import LLMProvider

# additionalProperties: false keeps Claude from inventing field names like
# "job_titles" or "total_experience_years" instead of "roles"/"years_experience".
_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Technical and professional skills extracted from the CV.",
        },
        "roles": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Job titles held as plain strings (e.g. 'Senior Platform Engineer'), "
                "most recent first. Return only the job title string, not company or dates."
            ),
        },
        "years_experience": {
            "type": "number",
            "description": "Total years of professional experience (approximate).",
        },
        "summary": {
            "type": "string",
            "description": "2–3 sentence professional summary in British English.",
        },
    },
    "required": ["skills", "roles", "years_experience", "summary"],
    "additionalProperties": False,
}

_MAX_CHARS = 8000


def _normalise(raw: dict) -> dict:
    """Coerce LLM output to the exact shape Phase 3 scoring expects.

    Tolerates common field-name drift (job_titles, total_experience_years).
    """
    skills = raw.get("skills") or []
    roles = raw.get("roles") or []

    if not roles:
        # Claude occasionally returns job_titles as [{title, company, ...}] objects.
        for item in raw.get("job_titles") or []:
            if isinstance(item, dict):
                roles.append(item.get("title", ""))
            else:
                roles.append(str(item))

    years = raw.get("years_experience") or raw.get("total_experience_years") or 0

    return {
        "skills": [str(s).strip() for s in skills if str(s).strip()],
        "roles": [str(r).strip() for r in roles if str(r).strip()],
        "years_experience": float(years),
        "summary": str(raw.get("summary") or ""),
    }


def parse_cv(raw_text: str, provider: LLMProvider) -> dict:
    excerpt = raw_text[:_MAX_CHARS]
    prompt = (
        "Parse the following CV and extract structured information.\n\n"
        f"CV text:\n{excerpt}\n\n"
        "Return:\n"
        "- skills: a flat list of skill strings\n"
        "- roles: a flat list of job title strings only (not objects), most recent first\n"
        "- years_experience: total years of professional experience as a number\n"
        "- summary: 2–3 sentence professional summary in British English"
    )
    raw = provider.generate_json(prompt, _SCHEMA)
    return _normalise(raw)
