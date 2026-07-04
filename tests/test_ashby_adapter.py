# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the Ashby adapter — no live network."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.ashby import AshbyAdapter, _map_item
from app.core.sources.base import FetchContext, RemoteMode

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "ashby" / "jobs_response.json"


def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_remote_mode_from_workplace_type() -> None:
    item = fixture_data()["jobs"][0]
    assert item["workplaceType"] == "Remote"
    raw = _map_item(item, "linear")
    assert raw.remote_mode == RemoteMode.REMOTE


def test_is_remote_fallback() -> None:
    item = {"id": "abc", "title": "Eng", "isRemote": True, "workplaceType": ""}
    raw = _map_item(item, "test")
    assert raw.remote_mode == RemoteMode.REMOTE


def test_hybrid_workplace_type() -> None:
    item = {
        "id": "abc",
        "title": "Eng",
        "isRemote": False,
        "workplaceType": "Hybrid",
        "location": "London",
        "publishedAt": None,
    }
    raw = _map_item(item, "test")
    assert raw.remote_mode == RemoteMode.HYBRID


def test_salary_not_disclosed_when_no_compensation() -> None:
    data = fixture_data()
    for job in data["jobs"]:
        raw = _map_item(job, "linear")
        assert raw.salary_disclosed is False


def test_salary_disclosed_when_compensation_present() -> None:
    item = {
        "id": "abc",
        "title": "Eng",
        "isRemote": True,
        "workplaceType": "Remote",
        "location": "Remote",
        "publishedAt": None,
        "compensation": {
            "summaryComponents": [{"min": 100000, "max": 150000}],
            "currency": "USD",
            "interval": "Year",
        },
    }
    raw = _map_item(item, "test")
    assert raw.salary_disclosed is True
    assert raw.salary_min == 100000
    assert raw.salary_max == 150000
    assert raw.salary_currency == "USD"
    assert raw.salary_period == "year"


def test_location_from_address_when_location_empty() -> None:
    item = {
        "id": "abc",
        "title": "Eng",
        "isRemote": True,
        "workplaceType": "Remote",
        "location": "",
        "address": {"postalAddress": {"addressCountry": "United States"}},
        "publishedAt": None,
    }
    raw = _map_item(item, "test")
    assert raw.location == "United States"


def test_external_id_is_string() -> None:
    for job in fixture_data()["jobs"]:
        raw = _map_item(job, "linear")
        assert isinstance(raw.external_id, str)


def test_fetch_skips_unlisted_jobs() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "jobs": [
            {
                "id": "listed",
                "title": "Eng",
                "isListed": True,
                "isRemote": True,
                "workplaceType": "Remote",
                "location": "Remote",
                "jobUrl": "https://example.com",
            },
            {
                "id": "unlisted",
                "title": "Draft Job",
                "isListed": False,
                "isRemote": True,
                "workplaceType": "Remote",
                "location": "Remote",
            },
        ],
        "apiVersion": "1",
    }
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={"board_token": "test"},
        since=None,
    )
    with patch("app.core.sources.ashby.httpx.get", return_value=mock_resp):
        results = list(AshbyAdapter().fetch(ctx))

    assert len(results) == 1
    assert results[0].external_id == "listed"


def test_fetch_raises_when_no_token() -> None:
    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )
    with pytest.raises(ValueError, match="board_token"):
        list(AshbyAdapter().fetch(ctx))
