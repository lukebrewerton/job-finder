"""Unit tests for the HN Who is Hiring adapter — stub LLM and network, no live calls."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.llm.normalise import _clean_html, normalise_hn_comment
from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.hn_whoishiring import HNWhoIsHiringAdapter, _matches_titles

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "hn_whoishiring" / "comments_response.json"


@pytest.fixture()
def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


class _StubProvider:
    def generate_json(self, prompt: str, schema: dict) -> dict:
        return {
            "is_job_posting": True,
            "title": "Platform Engineer",
            "company": "SafetyWing",
            "url": "https://example.com/apply",
            "location": "Remote",
            "remote_mode": "remote",
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_currency": "USD",
        }


class _NotAJobProvider:
    def generate_json(self, prompt: str, schema: dict) -> dict:
        return {
            "is_job_posting": False,
            "title": "",
            "company": "",
            "url": "",
            "location": None,
            "remote_mode": "unknown",
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
        }


def test_clean_html_strips_tags() -> None:
    html = "<p>Hello <strong>world</strong></p>"
    assert _clean_html(html) == "Hello world"


def test_clean_html_decodes_entities() -> None:
    html = "Fish &amp; Chips"
    assert _clean_html(html) == "Fish & Chips"


def test_normalise_returns_dict_for_job_posting() -> None:
    result = normalise_hn_comment("<p>ACME | Engineer | Remote</p>", _StubProvider())
    assert result is not None
    assert result["title"] == "Platform Engineer"
    assert result["company"] == "SafetyWing"
    assert result["remote_mode"] == "remote"
    assert result["salary_min"] == 130000


def test_normalise_returns_none_for_non_posting() -> None:
    result = normalise_hn_comment("Just a comment, not a job.", _NotAJobProvider())
    assert result is None


def test_matches_titles_with_keyword() -> None:
    assert _matches_titles("We need a Platform Engineer to join us", ["platform engineer"]) is True


def test_matches_titles_no_match() -> None:
    assert _matches_titles("Hiring a sales manager", ["platform engineer"]) is False


def test_matches_titles_empty_list() -> None:
    """Empty title list means no filter — everything matches."""
    assert _matches_titles("any text", []) is True


def test_fetch_yields_jobs_from_fixture(fixture_data: dict) -> None:
    ctx = FetchContext(
        titles=["platform engineer", "cloud engineer"],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )

    stub_provider = _StubProvider()

    # All comments in fixture match; stub provider says they're all job postings
    with (
        patch("app.core.sources.hn_whoishiring._find_thread_id", return_value="48357725"),
        patch(
            "app.core.sources.hn_whoishiring._fetch_top_level_comments",
            return_value=fixture_data["hits"],
        ),
        patch("app.core.llm.provider.get_llm_provider", return_value=stub_provider),
        patch("app.core.llm.normalise.normalise_hn_comment") as mock_norm,
    ):
        mock_norm.return_value = {
            "title": "Platform Engineer",
            "company": "SafetyWing",
            "url": "https://example.com/apply",
            "location": "Remote",
            "remote_mode": "remote",
            "salary_min": 130000,
            "salary_max": 160000,
            "salary_currency": "USD",
        }
        results = list(HNWhoIsHiringAdapter().fetch(ctx))

    assert len(results) == len(fixture_data["hits"])
    for raw in results:
        assert raw.remote_mode == RemoteMode.REMOTE
        assert raw.salary_disclosed is True
        assert raw.salary_currency == "USD"


def test_fetch_skips_when_no_thread() -> None:
    ctx = FetchContext(
        titles=["engineer"],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )
    with (
        patch("app.core.sources.hn_whoishiring._find_thread_id", return_value=None),
        patch("app.core.llm.provider.get_llm_provider", return_value=None),
    ):
        results = list(HNWhoIsHiringAdapter().fetch(ctx))
    assert results == []
