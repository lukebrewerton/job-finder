# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class RemoteMode(StrEnum):
    REMOTE = "remote"
    REMOTE_FIRST = "remote_first"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class RawJob:
    external_id: str
    title: str
    company: str
    url: str
    description: str
    remote_mode: RemoteMode = RemoteMode.UNKNOWN
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    salary_period: str | None = None
    salary_disclosed: bool = False
    posted_at: datetime | None = None
    raw: dict = field(default_factory=dict)


@dataclass(slots=True)
class FetchContext:
    titles: list[str]
    locations: list[str] | None
    remote_modes: list[RemoteMode]
    config: dict
    since: datetime | None


class SourceAdapter(Protocol):
    key: str
    requires_config: bool

    def fetch(self, ctx: FetchContext) -> Iterable[RawJob]: ...


_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    _REGISTRY[cls.key] = cls  # type: ignore[attr-defined]
    return cls


def get_adapter(key: str) -> SourceAdapter:
    try:
        return _REGISTRY[key]()
    except KeyError:
        raise ValueError(f"No adapter registered for source key {key!r}") from None
