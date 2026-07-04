# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
"""LLM provider interface and concrete implementations.

Only one provider is active at a time, selected by LLM_PROVIDER env var.
get_llm_provider() raises ValueError immediately if the required key is absent.
"""

from __future__ import annotations

import json
from typing import Protocol


class LLMProvider(Protocol):
    def generate_json(self, prompt: str, schema: dict) -> dict: ...


class AnthropicProvider:
    def __init__(self, api_key: str, model: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def generate_json(self, prompt: str, schema: dict) -> dict:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            tools=[
                {
                    "name": "output",
                    "description": "Return the structured result.",
                    "input_schema": schema,
                }
            ],
            tool_choice={"type": "tool", "name": "output"},
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return dict(block.input)
        raise RuntimeError("Anthropic response contained no tool_use block")


class OpenAIProvider:
    def __init__(self, api_key: str, model: str) -> None:
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def generate_json(self, prompt: str, schema: dict) -> dict:
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": "Respond with valid JSON that matches the requested schema.",
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)


def get_llm_provider() -> LLMProvider:
    from app.config import get_settings

    s = get_settings()
    if s.llm_provider == "anthropic":
        if not s.anthropic_api_key:
            raise ValueError(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set. "
                "Add it to your .env or environment."
            )
        return AnthropicProvider(s.anthropic_api_key, s.llm_model)
    if s.llm_provider == "openai":
        if not s.openai_api_key:
            raise ValueError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "Add it to your .env or environment."
            )
        return OpenAIProvider(s.openai_api_key, s.llm_model)
    raise ValueError(f"Unknown LLM_PROVIDER={s.llm_provider!r}. Must be 'anthropic' or 'openai'.")
