# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CV-to-job fit scoring via LLM rubric.

Returns a capability fit score (0–100) with evidence — no probability metrics.
"""

from __future__ import annotations

from app.core.llm.provider import LLMProvider

_VALID_FLAGS = frozenset(
    {
        "stretch_role",
        "missing_must_have",
        "below_salary_target",
        "seniority_mismatch",
        "remote_mismatch",
    }
)

_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "fit_score": {
            "type": "integer",
            "description": (
                "Capability fit score 0–100. 80+ means strong match; 50–79 means "
                "workable with gaps; below 50 means significant gaps. "
                "Do NOT factor in job-hunting probability — score capability only."
            ),
        },
        "matched_skills": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills from the CV that directly match the job requirements.",
        },
        "gaps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Skills or experience the job asks for that are absent from the CV.",
        },
        "flags": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "stretch_role",
                    "missing_must_have",
                    "below_salary_target",
                    "seniority_mismatch",
                    "remote_mismatch",
                ],
            },
            "description": (
                "Zero or more flags from the allowed enum. "
                "stretch_role: role is above candidate's current seniority. "
                "missing_must_have: a hard requirement from the JD is absent from CV. "
                "below_salary_target: advertised salary is below candidate's range. "
                "seniority_mismatch: seniority level does not match. "
                "remote_mismatch: remote/office arrangement conflicts with CV preference."
            ),
        },
        "rationale": {
            "type": "string",
            "description": "2–4 sentences explaining the score in British English.",
        },
        "summary": {
            "type": "string",
            "description": (
                "2–3 sentences in plain British English summarising what the role "
                "actually involves — the team, day-to-day responsibilities, and key "
                "technologies. Omit all marketing language, filler phrases, and "
                "company sales copy."
            ),
        },
    },
    "required": ["fit_score", "matched_skills", "gaps", "flags", "rationale", "summary"],
    "additionalProperties": False,
}


def _normalise(raw: dict) -> dict:
    """Clamp and coerce LLM output to the canonical shape."""
    fit_score = max(0, min(100, int(raw.get("fit_score") or 0)))
    matched_skills = [str(s).strip() for s in (raw.get("matched_skills") or []) if str(s).strip()]
    gaps = [str(g).strip() for g in (raw.get("gaps") or []) if str(g).strip()]
    flags = [f for f in (raw.get("flags") or []) if f in _VALID_FLAGS]
    rationale = str(raw.get("rationale") or "")
    summary = str(raw.get("summary") or "")
    return {
        "fit_score": fit_score,
        "matched_skills": matched_skills,
        "gaps": gaps,
        "flags": flags,
        "rationale": rationale,
        "summary": summary,
    }


def score_job(
    job_title: str,
    job_company: str,
    job_description: str,
    cv_parsed: dict,
    provider: LLMProvider,
) -> dict:
    """Return normalised scoring dict for one job against one CV."""
    skills_str = ", ".join(cv_parsed.get("skills") or []) or "none listed"
    roles_str = ", ".join(cv_parsed.get("roles") or []) or "none listed"
    years = cv_parsed.get("years_experience") or 0
    summary = cv_parsed.get("summary") or ""

    desc_excerpt = job_description[:4000] if job_description else ""

    prompt = (
        f"Score how well the following candidate's CV matches a job posting.\n\n"
        f"JOB POSTING\n"
        f"Title: {job_title}\n"
        f"Company: {job_company}\n"
        f"Description:\n{desc_excerpt}\n\n"
        f"CANDIDATE CV SUMMARY\n"
        f"Professional summary: {summary}\n"
        f"Years of experience: {years}\n"
        f"Recent roles: {roles_str}\n"
        f"Skills: {skills_str}\n\n"
        f"Assess capability fit only — do not factor in job-hunting probability, "
        f"employer preferences, or likelihood of getting an interview.\n\n"
        f"Return a JSON object with exactly these fields:\n"
        f"- fit_score: integer 0-100 (80+ strong match, 50-79 workable, <50 significant gaps)\n"
        f"- matched_skills: flat list of skill strings from the CV that match the job\n"
        f"- gaps: flat list of strings, skills the job requires that are absent from the CV\n"
        f"- flags: list of zero or more strings, each must be one of: "
        f"stretch_role, missing_must_have, below_salary_target, "
        f"seniority_mismatch, remote_mismatch\n"
        f"- rationale: string, 2-4 sentences in British English explaining the score\n"
        f"- summary: string, 2-3 sentences in plain British English describing what the role "
        f"actually involves — the team, responsibilities, and key technologies. "
        f"Omit all marketing language and filler."
    )

    raw = provider.generate_json(prompt, _SCHEMA)
    return _normalise(raw)
