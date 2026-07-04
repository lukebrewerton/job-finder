# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for job scoring — uses a stub LLMProvider, no live network."""

from __future__ import annotations

from app.core.llm.scoring import _normalise, score_job

_CV = {
    "skills": ["Python", "Kubernetes", "Terraform", "AWS", "PostgreSQL"],
    "roles": ["Senior Platform Engineer", "Cloud Engineer"],
    "years_experience": 8,
    "summary": "Experienced platform engineer with eight years building cloud infrastructure.",
}

_JOB_TITLE = "Platform Engineer"
_JOB_COMPANY = "Acme Corp"
_JOB_DESC = "We need a platform engineer with Python, Kubernetes, and cloud experience."


class _StubProvider:
    def generate_json(self, prompt: str, schema: dict) -> dict:
        return {
            "fit_score": 85,
            "matched_skills": ["Python", "Kubernetes", "AWS"],
            "gaps": ["Helm", "ArgoCD"],
            "flags": ["stretch_role"],
            "rationale": "Strong match on core skills with minor gaps in GitOps tooling.",
            "summary": "A platform engineering role building cloud infrastructure.",
        }


def test_score_job_returns_required_keys():
    result = score_job(_JOB_TITLE, _JOB_COMPANY, _JOB_DESC, _CV, _StubProvider())
    assert "fit_score" in result
    assert "matched_skills" in result
    assert "gaps" in result
    assert "flags" in result
    assert "rationale" in result
    assert "summary" in result


def test_score_job_fit_score_range():
    result = score_job(_JOB_TITLE, _JOB_COMPANY, _JOB_DESC, _CV, _StubProvider())
    assert 0 <= result["fit_score"] <= 100


def test_score_job_matched_skills_is_list():
    result = score_job(_JOB_TITLE, _JOB_COMPANY, _JOB_DESC, _CV, _StubProvider())
    assert isinstance(result["matched_skills"], list)


def test_score_job_flags_only_valid_enum():
    result = score_job(_JOB_TITLE, _JOB_COMPANY, _JOB_DESC, _CV, _StubProvider())
    valid = {
        "stretch_role",
        "missing_must_have",
        "below_salary_target",
        "seniority_mismatch",
        "remote_mismatch",
    }
    assert all(f in valid for f in result["flags"])


def test_normalise_clamps_fit_score_above_100():
    raw = {"fit_score": 150, "matched_skills": [], "gaps": [], "flags": [], "rationale": ""}
    assert _normalise(raw)["fit_score"] == 100


def test_normalise_clamps_fit_score_below_0():
    raw = {"fit_score": -10, "matched_skills": [], "gaps": [], "flags": [], "rationale": ""}
    assert _normalise(raw)["fit_score"] == 0


def test_normalise_strips_invalid_flags():
    result = _normalise(
        {
            "fit_score": 70,
            "matched_skills": [],
            "gaps": [],
            "flags": ["stretch_role", "invented_flag", "missing_must_have"],
            "rationale": "",
        }
    )
    assert "invented_flag" not in result["flags"]
    assert "stretch_role" in result["flags"]
    assert "missing_must_have" in result["flags"]


def test_normalise_strips_empty_skills():
    result = _normalise(
        {
            "fit_score": 60,
            "matched_skills": ["Python", "", "  ", "AWS"],
            "gaps": [],
            "flags": [],
            "rationale": "Good.",
        }
    )
    assert "" not in result["matched_skills"]
    assert "  " not in result["matched_skills"]
    assert "Python" in result["matched_skills"]


def test_normalise_missing_fields_defaults():
    result = _normalise({})
    assert result["fit_score"] == 0
    assert result["matched_skills"] == []
    assert result["gaps"] == []
    assert result["flags"] == []
    assert result["rationale"] == ""
    assert result["summary"] == ""


def test_score_job_prompt_contains_job_title():
    captured: list[str] = []

    class _CapturingProvider:
        def generate_json(self, prompt: str, schema: dict) -> dict:
            captured.append(prompt)
            return {
                "fit_score": 50,
                "matched_skills": [],
                "gaps": [],
                "flags": [],
                "rationale": "Test.",
                "summary": "Test summary.",
            }

    score_job("Unique Job Title XYZ", _JOB_COMPANY, _JOB_DESC, _CV, _CapturingProvider())
    assert len(captured) == 1
    assert "Unique Job Title XYZ" in captured[0]
