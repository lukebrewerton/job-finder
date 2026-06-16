"""CV parsing: raw text → structured summary used by the scoring rubric.

This is a 4th LLM use beyond the spec's three named lanes — included because deterministic
extraction of skills, roles, and years_experience from free-form CV text is not feasible.
"""

from __future__ import annotations

from app.core.llm.provider import LLMProvider

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
            "description": "Job titles held, most recent first.",
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
}

_MAX_CHARS = 8000


def parse_cv(raw_text: str, provider: LLMProvider) -> dict:
    excerpt = raw_text[:_MAX_CHARS]
    prompt = (
        f"Parse the following CV and extract structured information.\n\n"
        f"CV text:\n{excerpt}\n\n"
        f"Extract: all technical and professional skills; all job titles held (most recent first); "
        f"total years of professional experience (approximate integer or half-year); "
        f"and a 2–3 sentence professional summary in British English."
    )
    return provider.generate_json(prompt, _SCHEMA)
