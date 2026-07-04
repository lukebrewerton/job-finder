# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the Remotive adapter — no live network, runs against the recorded fixture."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.remotive import RemotiveAdapter, _map_item

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "remotive" / "search_response.json"


@pytest.fixture()
def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_external_id_is_string(fixture_data: dict) -> None:
    for item in fixture_data["jobs"]:
        raw = _map_item(item)
        assert isinstance(raw.external_id, str)


def test_remote_mode_is_remote(fixture_data: dict) -> None:
    """Remotive is a remote board — all jobs are REMOTE."""
    for item in fixture_data["jobs"]:
        raw = _map_item(item)
        assert raw.remote_mode == RemoteMode.REMOTE


def test_salary_disclosed_when_salary_string_present(fixture_data: dict) -> None:
    """salary_disclosed=True when salary is a non-empty string."""
    item = fixture_data["jobs"][0]
    assert item.get("salary"), "fixture job 0 must have a salary string"
    raw = _map_item(item)
    assert raw.salary_disclosed is True


def test_salary_min_max_none_for_string_salary(fixture_data: dict) -> None:
    """Salary is a free-form string; salary_min/max remain None."""
    item = fixture_data["jobs"][0]
    raw = _map_item(item)
    assert raw.salary_min is None
    assert raw.salary_max is None


def test_salary_not_disclosed_when_empty() -> None:
    item = {
        "id": 999,
        "url": "https://remotive.com/job/999",
        "title": "Engineer",
        "company_name": "Acme",
        "description": "",
        "salary": "",
        "publication_date": "2026-01-01T00:00:00",
        "candidate_required_location": "",
    }
    raw = _map_item(item)
    assert raw.salary_disclosed is False


def test_posted_at_is_utc(fixture_data: dict) -> None:
    from datetime import UTC

    for item in fixture_data["jobs"]:
        raw = _map_item(item)
        if raw.posted_at is not None:
            assert raw.posted_at.tzinfo == UTC


def test_fetch_without_network(fixture_data: dict) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = fixture_data
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=["cloud engineer"],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )

    with patch("app.core.sources.remotive.httpx.get", return_value=mock_resp):
        results = list(RemotiveAdapter().fetch(ctx))

    assert len(results) == len(fixture_data["jobs"])
