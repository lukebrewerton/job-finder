"""Title expansion: canonical role + seniority → list of search-worthy title variations.

Called once on profile save. Never called per-fetch.
"""

from __future__ import annotations

from app.core.llm.provider import LLMProvider

_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "titles": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Equivalent and adjacent job title variations.",
        }
    },
    "required": ["titles"],
}


def expand_titles(canonical_role: str, seniority: str, provider: LLMProvider) -> list[str]:
    prompt = (
        f"Generate a list of equivalent and adjacent job title variations for a job search.\n\n"
        f"Canonical role: {canonical_role}\n"
        f"Seniority: {seniority}\n\n"
        f"Include:\n"
        f"- Direct synonyms and common alternative titles\n"
        f"- Adjacent titles held by people with the same skills\n"
        f"- Seniority permutations (e.g. Senior, Lead, Staff, Principal prefixes/suffixes)\n"
        f"- Do NOT include the canonical title itself\n"
        f"- Return 5–15 titles\n"
        f"- Use British job-title conventions"
    )
    result = provider.generate_json(prompt, _SCHEMA)
    titles = result.get("titles", [])
    return [str(t).strip() for t in titles if str(t).strip()]
