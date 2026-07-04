# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the Himalayas adapter — no live network, runs against the recorded fixture."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.himalayas import HimalayasAdapter, _map_item

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "himalayas" / "search_response.json"


@pytest.fixture()
def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_external_id_is_string(fixture_data: dict) -> None:
    for item in fixture_data["jobs"]:
        raw = _map_item(item)
        assert isinstance(raw.external_id, str)
        assert raw.external_id  # non-empty


def test_remote_mode_is_remote(fixture_data: dict) -> None:
    """Himalayas is a remote board — all jobs should be REMOTE."""
    for item in fixture_data["jobs"]:
        raw = _map_item(item)
        assert raw.remote_mode == RemoteMode.REMOTE


def test_salary_disclosed_false_when_null(fixture_data: dict) -> None:
    """First fixture job has null minSalary/maxSalary."""
    item = fixture_data["jobs"][0]
    assert item.get("minSalary") is None
    assert item.get("maxSalary") is None
    raw = _map_item(item)
    assert raw.salary_disclosed is False
    assert raw.salary_min is None
    assert raw.salary_max is None


def test_salary_disclosed_true_when_present() -> None:
    item = {
        "guid": "https://himalayas.app/test",
        "applicationLink": "https://himalayas.app/test",
        "title": "Platform Engineer",
        "companyName": "Acme",
        "description": "desc",
        "minSalary": 100000,
        "maxSalary": 150000,
        "currency": "USD",
        "salaryPeriod": "annual",
        "pubDate": 1781527868,
        "locationRestrictions": ["United States"],
    }
    raw = _map_item(item)
    assert raw.salary_disclosed is True
    assert raw.salary_min == 100000
    assert raw.salary_max == 150000
    assert raw.salary_currency == "USD"
    assert raw.salary_period == "year"


def test_location_from_restrictions(fixture_data: dict) -> None:
    item = fixture_data["jobs"][0]
    restrictions = item.get("locationRestrictions") or []
    raw = _map_item(item)
    if restrictions:
        assert raw.location == restrictions[0]
    else:
        assert raw.location is None


def test_posted_at_is_timezone_aware(fixture_data: dict) -> None:
    for item in fixture_data["jobs"]:
        raw = _map_item(item)
        if raw.posted_at is not None:
            assert raw.posted_at.tzinfo is not None


def test_fetch_deduplicates_across_queries(fixture_data: dict) -> None:
    """If the same job appears for two title queries, it should only be yielded once."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = fixture_data
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=["cloud engineer", "platform engineer"],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )

    with patch("app.core.sources.himalayas.httpx.get", return_value=mock_resp):
        results = list(HimalayasAdapter().fetch(ctx))

    unique_ids = {r.external_id for r in results}
    assert len(results) == len(unique_ids)
