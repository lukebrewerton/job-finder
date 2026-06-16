"""Unit tests for the Adzuna adapter — no live network, runs against the recorded fixture."""

import json
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.sources.adzuna import AdzunaAdapter, _infer_remote_mode, _map_item
from app.core.sources.base import FetchContext, RemoteMode

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "adzuna" / "search_response.json"


@pytest.fixture()
def fixture_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


def test_salary_disclosed_when_predicted_zero(fixture_data: dict) -> None:
    """salary_disclosed=True only when salary_is_predicted is "0" and salary is present."""
    disclosed_items = [r for r in fixture_data["results"] if r.get("salary_is_predicted") == "0"]
    assert disclosed_items, "fixture must contain at least one non-predicted salary"
    for item in disclosed_items:
        raw = _map_item(item)
        assert raw.salary_disclosed is True, f"expected disclosed for {item['id']}"


def test_salary_not_disclosed_when_predicted_one(fixture_data: dict) -> None:
    """salary_disclosed=False when salary_is_predicted is "1" (estimated figure)."""
    predicted_items = [r for r in fixture_data["results"] if r.get("salary_is_predicted") == "1"]
    assert predicted_items, "fixture must contain at least one predicted salary"
    for item in predicted_items:
        raw = _map_item(item)
        assert raw.salary_disclosed is False, f"expected not-disclosed for {item['id']}"


def test_salary_floats_cast_to_int(fixture_data: dict) -> None:
    """Float salary values (e.g. 57568.38) are cast to int."""
    float_items = [
        r
        for r in fixture_data["results"]
        if isinstance(r.get("salary_min"), float) or isinstance(r.get("salary_max"), float)
    ]
    assert float_items, "fixture must contain at least one float salary"
    for item in float_items:
        raw = _map_item(item)
        if raw.salary_min is not None:
            assert isinstance(raw.salary_min, int)
        if raw.salary_max is not None:
            assert isinstance(raw.salary_max, int)


def test_external_id_is_string(fixture_data: dict) -> None:
    for item in fixture_data["results"]:
        raw = _map_item(item)
        assert isinstance(raw.external_id, str)


def test_posted_at_timezone_aware(fixture_data: dict) -> None:
    for item in fixture_data["results"]:
        raw = _map_item(item)
        if raw.posted_at is not None:
            assert raw.posted_at.tzinfo is not None
            assert raw.posted_at.tzinfo == UTC


_BARE_ITEM: dict = {
    "id": "99999",
    "title": "DevOps Engineer",
    "company": {"display_name": "Test Co"},
    "redirect_url": "https://example.com",
    "description": "",
    "salary_is_predicted": "1",
    "salary_min": None,
    "salary_max": None,
    "created": "2024-01-01T00:00:00Z",
    "location": {"display_name": "London"},
}


def _item(**kwargs: object) -> dict:
    return {**_BARE_ITEM, **kwargs}


def test_remote_mode_hybrid_in_fixture(fixture_data: dict) -> None:
    """Fixture item 0 mentions 'Hybrid' in its description — must map to HYBRID."""
    raw = _map_item(fixture_data["results"][0])
    assert raw.remote_mode == RemoteMode.HYBRID


def test_remote_mode_onsite_in_fixture(fixture_data: dict) -> None:
    """Fixture item 3 says 'fully on site' — must map to ONSITE."""
    raw = _map_item(fixture_data["results"][3])
    assert raw.remote_mode == RemoteMode.ONSITE


def test_infer_fully_remote() -> None:
    assert _infer_remote_mode("DevOps Engineer", "This is a fully remote position.") == (
        RemoteMode.REMOTE
    )


def test_infer_remote_first() -> None:
    assert _infer_remote_mode("SRE", "We are a remote-first company.") == RemoteMode.REMOTE_FIRST


def test_infer_hybrid_beats_remote() -> None:
    assert _infer_remote_mode("Platform Eng", "Hybrid remote, 2 days in office.") == (
        RemoteMode.HYBRID
    )


def test_infer_remote_keyword() -> None:
    assert _infer_remote_mode("Engineer", "Remote position, UK-wide.") == RemoteMode.REMOTE


def test_infer_onsite() -> None:
    assert _infer_remote_mode("Engineer", "Fully on-site in Glasgow.") == RemoteMode.ONSITE


def test_infer_unknown_when_no_signal() -> None:
    assert _infer_remote_mode("Engineer", "Great benefits and a friendly team.") == (
        RemoteMode.UNKNOWN
    )


def test_map_item_remote_mode_from_description() -> None:
    raw = _map_item(_item(description="This is a hybrid role, 3 days per week in office."))
    assert raw.remote_mode == RemoteMode.HYBRID


def test_fetch_uses_fixture_without_network(fixture_data: dict) -> None:
    """The adapter maps fixture data to RawJob without touching the network."""
    mock_response = MagicMock()
    mock_response.json.return_value = fixture_data
    mock_response.raise_for_status.return_value = None

    ctx = FetchContext(
        titles=["cloud engineer"],
        locations=None,
        remote_modes=list(RemoteMode),
        config={},
        since=None,
    )

    with patch("app.core.sources.adzuna.httpx.get", return_value=mock_response):
        results = list(AdzunaAdapter().fetch(ctx))

    assert len(results) == len(fixture_data["results"])
    assert all(r.external_id for r in results)
