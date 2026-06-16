"""Unit tests for the JSON-LD adapter — no live network."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.jsonld import JsonLdAdapter, _extract_job_postings, _map_posting

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jsonld" / "careers_page.html"


def fixture_html() -> str:
    return FIXTURE_PATH.read_text()


def test_extracts_two_job_postings() -> None:
    postings = _extract_job_postings(fixture_html())
    assert len(postings) == 2


def test_first_posting_telecommute_remote_mode() -> None:
    postings = _extract_job_postings(fixture_html())
    raw = _map_posting(postings[0], "")
    assert raw is not None
    assert raw.remote_mode == RemoteMode.REMOTE


def test_second_posting_hybrid_inferred_from_description() -> None:
    postings = _extract_job_postings(fixture_html())
    raw = _map_posting(postings[1], "")
    assert raw is not None
    assert raw.remote_mode == RemoteMode.HYBRID


def test_salary_disclosed_and_parsed() -> None:
    postings = _extract_job_postings(fixture_html())
    raw = _map_posting(postings[0], "")
    assert raw is not None
    assert raw.salary_disclosed is True
    assert raw.salary_min == 80000
    assert raw.salary_max == 110000
    assert raw.salary_currency == "GBP"
    assert raw.salary_period == "year"


def test_company_from_hiring_organisation() -> None:
    postings = _extract_job_postings(fixture_html())
    raw = _map_posting(postings[0], "fallback")
    assert raw is not None
    assert raw.company == "Acme Corp"


def test_company_from_fallback_when_missing() -> None:
    posting = {
        "@type": "JobPosting",
        "title": "Engineer",
        "url": "https://example.com",
    }
    raw = _map_posting(posting, "Fallback Corp")
    assert raw is not None
    assert raw.company == "Fallback Corp"


def test_returns_none_when_no_title() -> None:
    posting = {"@type": "JobPosting", "hiringOrganization": {"name": "Test"}}
    assert _map_posting(posting, "Test") is None


def test_posted_at_parsed() -> None:
    postings = _extract_job_postings(fixture_html())
    raw = _map_posting(postings[0], "")
    assert raw is not None
    assert raw.posted_at is not None
    assert raw.posted_at.year == 2026


def test_location_from_address() -> None:
    postings = _extract_job_postings(fixture_html())
    raw = _map_posting(postings[0], "")
    assert raw is not None
    assert "London" in (raw.location or "")


def test_at_graph_format() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "JobPosting",
          "title": "Graph Engineer",
          "hiringOrganization": {"name": "Graph Co"},
          "url": "https://example.com/graph"
        }
      ]
    }
    </script>
    """
    postings = _extract_job_postings(html)
    assert len(postings) == 1
    raw = _map_posting(postings[0], "")
    assert raw is not None
    assert raw.title == "Graph Engineer"


def test_fetch_uses_fixture_without_network() -> None:
    html_content = fixture_html()
    mock_resp = MagicMock()
    mock_resp.text = html_content
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={"url": "https://acme.example.com/careers", "company": "Acme Corp"},
        since=None,
    )
    with patch("app.core.sources.jsonld.httpx.get", return_value=mock_resp):
        results = list(JsonLdAdapter().fetch(ctx))

    assert len(results) == 2


def test_fetch_raises_when_no_url() -> None:
    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )
    with pytest.raises(ValueError, match="url"):
        list(JsonLdAdapter().fetch(ctx))
