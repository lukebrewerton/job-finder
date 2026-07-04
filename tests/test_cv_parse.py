# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for CV parsing — uses a stub LLMProvider, no live network."""

from __future__ import annotations

from app.core.llm.cv_parse import parse_cv


class _StubProvider:
    def generate_json(self, prompt: str, schema: dict) -> dict:
        return {
            "skills": ["Python", "Kubernetes", "Terraform", "AWS", "PostgreSQL"],
            "roles": ["Senior Platform Engineer", "Cloud Engineer", "DevOps Engineer"],
            "years_experience": 8,
            "summary": (
                "Experienced platform engineer with eight years building cloud infrastructure. "
                "Strong background in Kubernetes, Terraform, and AWS. "
                "Comfortable leading technical teams and delivering at scale."
            ),
        }


_SAMPLE_CV = """
John Smith
john@example.com

EXPERIENCE

Senior Platform Engineer — Acme Corp (2020–present)
Cloud Engineer — Beta Ltd (2018–2020)
DevOps Engineer — Gamma Inc (2016–2018)

SKILLS
Python, Kubernetes, Terraform, AWS, PostgreSQL, Linux, CI/CD
"""


def test_parse_cv_returns_required_keys():
    result = parse_cv(_SAMPLE_CV, _StubProvider())
    assert "skills" in result
    assert "roles" in result
    assert "years_experience" in result
    assert "summary" in result


def test_parse_cv_skills_is_list():
    result = parse_cv(_SAMPLE_CV, _StubProvider())
    assert isinstance(result["skills"], list)
    assert len(result["skills"]) > 0


def test_parse_cv_roles_most_recent_first():
    result = parse_cv(_SAMPLE_CV, _StubProvider())
    assert result["roles"][0] == "Senior Platform Engineer"


def test_parse_cv_years_experience_numeric():
    result = parse_cv(_SAMPLE_CV, _StubProvider())
    assert isinstance(result["years_experience"], (int, float))
    assert result["years_experience"] > 0


def test_parse_cv_truncates_long_text():
    """Verify very long CVs don't blow up (truncation is internal to parse_cv)."""
    long_cv = "A" * 20_000
    result = parse_cv(long_cv, _StubProvider())
    assert "skills" in result


def test_parse_cv_prompt_contains_excerpt():
    """The prompt should include at most _MAX_CHARS characters of CV text."""
    captured: list[str] = []

    class _CapturingProvider:
        def generate_json(self, prompt: str, schema: dict) -> dict:
            captured.append(prompt)
            return {
                "skills": [],
                "roles": [],
                "years_experience": 0,
                "summary": "",
            }

    long_cv = "X" * 20_000
    parse_cv(long_cv, _CapturingProvider())
    assert len(captured) == 1
    assert "X" * 8001 not in captured[0]
