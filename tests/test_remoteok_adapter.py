# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the RemoteOK adapter — no live network, runs against the recorded fixture."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.remoteok import RemoteOKAdapter, _map_item

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "remoteok" / "jobs_response.json"


@pytest.fixture()
def fixture_data() -> list:
    return json.loads(FIXTURE_PATH.read_text())


def test_header_element_skipped(fixture_data: list) -> None:
    """First element is a legal header — it must not appear in results."""
    assert "last_updated" in fixture_data[0], "fixture[0] must be the header"
    mock_resp = MagicMock()
    mock_resp.json.return_value = fixture_data
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )

    with patch("app.core.sources.remoteok.httpx.get", return_value=mock_resp):
        results = list(RemoteOKAdapter().fetch(ctx))

    # Should have fixture_data length minus 1 (header skipped)
    assert len(results) == len(fixture_data) - 1


def test_external_id_is_string(fixture_data: list) -> None:
    for item in fixture_data[1:]:
        if "id" in item:
            raw = _map_item(item)
            assert isinstance(raw.external_id, str)


def test_remote_mode_is_remote(fixture_data: list) -> None:
    for item in fixture_data[1:]:
        if "id" in item:
            raw = _map_item(item)
            assert raw.remote_mode == RemoteMode.REMOTE


def test_salary_not_disclosed_when_zero(fixture_data: list) -> None:
    """salary_disclosed=False when salary_min and salary_max are both 0."""
    item = fixture_data[1]
    assert item.get("salary_min") == 0
    assert item.get("salary_max") == 0
    raw = _map_item(item)
    assert raw.salary_disclosed is False
    assert raw.salary_min is None
    assert raw.salary_max is None


def test_salary_disclosed_when_nonzero() -> None:
    item = {
        "id": "9999",
        "slug": "remote-engineer-9999",
        "date": "2026-06-01T00:00:00+00:00",
        "company": "Acme",
        "position": "Cloud Engineer",
        "description": "desc",
        "location": "Remote",
        "apply_url": "https://example.com/apply",
        "url": "https://remoteok.com/remote-jobs/9999",
        "salary_min": 120000,
        "salary_max": 160000,
    }
    raw = _map_item(item)
    assert raw.salary_disclosed is True
    assert raw.salary_min == 120000
    assert raw.salary_max == 160000
    assert raw.salary_currency == "USD"


def test_title_from_position_field(fixture_data: list) -> None:
    item = fixture_data[1]
    raw = _map_item(item)
    assert raw.title == item["position"]


def test_posted_at_timezone_aware(fixture_data: list) -> None:
    for item in fixture_data[1:]:
        if "id" in item and "date" in item:
            raw = _map_item(item)
            if raw.posted_at is not None:
                assert raw.posted_at.tzinfo is not None
