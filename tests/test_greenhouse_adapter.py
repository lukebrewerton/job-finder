# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the Greenhouse adapter — no live network."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.greenhouse import GreenhouseAdapter, _map_item

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "greenhouse" / "jobs_response.json"


def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_salary_not_disclosed() -> None:
    data = fixture_data()
    raw = _map_item(data["jobs"][0], "Tailscale")
    assert raw.salary_disclosed is False
    assert raw.salary_min is None
    assert raw.salary_max is None


def test_external_id_is_string() -> None:
    data = fixture_data()
    for job in data["jobs"]:
        raw = _map_item(job, "Tailscale")
        assert isinstance(raw.external_id, str)


def test_company_from_company_name_field() -> None:
    data = fixture_data()
    raw = _map_item(data["jobs"][0], "fallback")
    assert raw.company == "Tailscale"


def test_remote_location_yields_remote_mode() -> None:
    item = {
        "id": 99999,
        "title": "Engineer",
        "company_name": "Test",
        "location": {"name": "Remote (United States)"},
        "content": "",
        "absolute_url": "https://example.com",
        "updated_at": None,
        "first_published": None,
    }
    raw = _map_item(item, "Test")
    assert raw.remote_mode == RemoteMode.REMOTE


def test_onsite_location_falls_back_to_inference() -> None:
    item = {
        "id": 99998,
        "title": "Office-based Engineer",
        "company_name": "Test",
        "location": {"name": "San Francisco, CA"},
        "content": "This is an in-office position.",
        "absolute_url": "https://example.com",
        "updated_at": None,
        "first_published": None,
    }
    raw = _map_item(item, "Test")
    assert raw.remote_mode == RemoteMode.ONSITE


def test_html_entities_decoded_in_description() -> None:
    item = {
        "id": 99997,
        "title": "Engineer",
        "company_name": "Test",
        "location": {"name": "Remote"},
        "content": "&lt;p&gt;Hello &amp; welcome&lt;/p&gt;",
        "absolute_url": "https://example.com",
        "updated_at": None,
        "first_published": None,
    }
    raw = _map_item(item, "Test")
    assert "<p>" in raw.description
    assert "&amp;" not in raw.description


def test_posted_at_parsed_from_first_published() -> None:
    data = fixture_data()
    for job in data["jobs"]:
        if job.get("first_published"):
            raw = _map_item(job, "Test")
            assert raw.posted_at is not None
            break


def test_fetch_uses_fixture_without_network() -> None:
    data = fixture_data()
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=["platform engineer"],
        locations=None,
        remote_modes=list(RemoteMode),
        config={"board_token": "tailscale"},
        since=None,
    )

    with patch("app.core.sources.greenhouse.httpx.get", return_value=mock_resp):
        results = list(GreenhouseAdapter().fetch(ctx))

    assert len(results) == len(data["jobs"])
    assert all(r.salary_disclosed is False for r in results)


def test_fetch_raises_when_no_token() -> None:
    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )
    import pytest

    with pytest.raises(ValueError, match="board_token"):
        list(GreenhouseAdapter().fetch(ctx))
