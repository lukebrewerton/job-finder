# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Unit tests for the Lever adapter — no live network."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.base import FetchContext, RemoteMode
from app.core.sources.lever import LeverAdapter, _map_item

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "lever" / "postings_response.json"


def fixture_data() -> list:
    return json.loads(FIXTURE_PATH.read_text())


def test_salary_not_disclosed() -> None:
    for item in fixture_data():
        raw = _map_item(item, "acme-corp")
        assert raw.salary_disclosed is False
        assert raw.salary_min is None


def test_external_id_is_string() -> None:
    for item in fixture_data():
        raw = _map_item(item, "acme-corp")
        assert isinstance(raw.external_id, str)


def test_remote_workplace_type_mapped() -> None:
    item = fixture_data()[0]
    assert item["workplaceType"] == "remote"
    raw = _map_item(item, "acme-corp")
    assert raw.remote_mode == RemoteMode.REMOTE


def test_hybrid_workplace_type_mapped() -> None:
    item = fixture_data()[1]
    assert item["workplaceType"] == "hybrid"
    raw = _map_item(item, "acme-corp")
    assert raw.remote_mode == RemoteMode.HYBRID


def test_location_from_categories() -> None:
    item = fixture_data()[1]
    raw = _map_item(item, "acme-corp")
    assert raw.location == "London, UK"


def test_posted_at_parsed_from_created_at_ms() -> None:
    item = fixture_data()[0]
    raw = _map_item(item, "acme-corp")
    assert raw.posted_at is not None
    assert raw.posted_at.year == 2024  # 1718000000000 ms = June 2024


def test_company_from_item_field() -> None:
    item = fixture_data()[0]
    raw = _map_item(item, "fallback-token")
    assert raw.company == "Acme Corp"


def test_fetch_uses_fixture_without_network() -> None:
    data = fixture_data()
    mock_resp = MagicMock()
    mock_resp.json.return_value = data
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=["platform engineer"],
        locations=None,
        remote_modes=list(RemoteMode),
        config={"board_token": "acme-corp"},
        since=None,
    )

    with patch("app.core.sources.lever.httpx.get", return_value=mock_resp):
        results = list(LeverAdapter().fetch(ctx))

    assert len(results) == len(data)


def test_fetch_raises_when_no_token() -> None:
    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )
    with pytest.raises(ValueError, match="board_token"):
        list(LeverAdapter().fetch(ctx))


def test_api_error_response_raises() -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"ok": False, "error": "Document not found"}
    mock_resp.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=[],
        locations=None,
        remote_modes=list(RemoteMode),
        config={"board_token": "unknown-company"},
        since=None,
    )
    with (
        patch("app.core.sources.lever.httpx.get", return_value=mock_resp),
        pytest.raises(ValueError, match="Document not found"),
    ):
        list(LeverAdapter().fetch(ctx))
