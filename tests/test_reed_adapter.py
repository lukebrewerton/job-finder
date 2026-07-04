# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the Reed adapter — no live network, runs against the recorded fixture."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.reed import ReedAdapter, _map_item

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "reed" / "search_response.json"


@pytest.fixture()
def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_salary_disclosed_when_salary_present(fixture_data: dict) -> None:
    """salary_disclosed=True when minimumSalary or maximumSalary is present."""
    item = fixture_data["results"][0]
    assert item["minimumSalary"] is not None
    raw = _map_item(item)
    assert raw.salary_disclosed is True


def test_salary_not_disclosed_when_null(fixture_data: dict) -> None:
    """salary_disclosed=False when both salary fields are null."""
    item = fixture_data["results"][1]
    assert item["minimumSalary"] is None
    assert item["maximumSalary"] is None
    raw = _map_item(item)
    assert raw.salary_disclosed is False


def test_salary_floats_cast_to_int(fixture_data: dict) -> None:
    item = fixture_data["results"][0]
    raw = _map_item(item)
    if raw.salary_min is not None:
        assert isinstance(raw.salary_min, int)
    if raw.salary_max is not None:
        assert isinstance(raw.salary_max, int)


def test_external_id_is_string(fixture_data: dict) -> None:
    for item in fixture_data["results"]:
        raw = _map_item(item)
        assert isinstance(raw.external_id, str)


def test_remote_mode_hybrid_inferred(fixture_data: dict) -> None:
    """Fixture item 0 mentions 'hybrid' in its description."""
    raw = _map_item(fixture_data["results"][0])
    assert raw.remote_mode == RemoteMode.HYBRID


def test_remote_mode_onsite_inferred(fixture_data: dict) -> None:
    """Fixture item 1 mentions 'Office-based'."""
    raw = _map_item(fixture_data["results"][1])
    assert raw.remote_mode == RemoteMode.ONSITE


def test_currency_defaults_to_gbp(fixture_data: dict) -> None:
    """When currency field is null, defaults to GBP."""
    item = fixture_data["results"][1]
    assert item.get("currency") is None
    raw = _map_item(item)
    assert raw.salary_currency == "GBP"


def test_fetch_uses_fixture_without_network(fixture_data: dict) -> None:
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

    mock_settings = MagicMock()
    mock_settings.reed_api_key = ""

    with (
        patch("app.core.sources.reed.httpx.get", return_value=mock_resp),
        patch("app.config.get_settings", return_value=mock_settings),
    ):
        results = list(ReedAdapter().fetch(ctx))

    assert len(results) == len(fixture_data["results"])
    assert all(r.external_id for r in results)
