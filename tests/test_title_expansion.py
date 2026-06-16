"""Unit tests for title expansion — uses a stub LLMProvider, no live network."""

from __future__ import annotations

from app.core.llm.titles import expand_titles


class _StubProvider:
    """Returns a canned response matching the expected schema."""

    def generate_json(self, prompt: str, schema: dict) -> dict:
        return {
            "titles": [
                "Platform Engineer",
                "Cloud Engineer",
                "DevOps Engineer",
                "Site Reliability Engineer",
                "Infrastructure Engineer",
                "Senior Platform Engineer",
            ]
        }


def test_expand_titles_returns_list():
    provider = _StubProvider()
    result = expand_titles("Cloud Platform Engineer", "senior", provider)
    assert isinstance(result, list)
    assert len(result) > 0


def test_expand_titles_all_strings():
    provider = _StubProvider()
    result = expand_titles("Cloud Platform Engineer", "senior", provider)
    assert all(isinstance(t, str) for t in result)


def test_expand_titles_filters_empty():
    class _EmptyProvider:
        def generate_json(self, prompt: str, schema: dict) -> dict:
            return {"titles": ["Valid Title", "", "  ", "Another Title"]}

    # Empty strings should be filtered out (falsy check in expand_titles).
    result = expand_titles("Cloud Platform Engineer", "senior", _EmptyProvider())
    assert "" not in result
    assert "  " not in result


def test_expand_titles_missing_key():
    class _BadProvider:
        def generate_json(self, prompt: str, schema: dict) -> dict:
            return {}  # Missing 'titles' key

    result = expand_titles("Cloud Platform Engineer", "senior", _BadProvider())
    assert result == []
