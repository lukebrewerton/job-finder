"""Shared utilities for source adapters."""

from __future__ import annotations

import re

from app.core.sources.base import RemoteMode

# Checked in priority order: most-specific pattern wins.
# "Hybrid" beats bare "remote" because "hybrid remote" should map to HYBRID, not REMOTE.
_RE_FULLY_REMOTE = re.compile(r"\b(fully\s+remote|100\s*%\s*remote|remote\s+only)\b", re.IGNORECASE)
_RE_REMOTE_FIRST = re.compile(r"\bremote[\s-]first\b", re.IGNORECASE)
_RE_HYBRID = re.compile(r"\bhybrid\b", re.IGNORECASE)
_RE_REMOTE = re.compile(r"\bremote\b", re.IGNORECASE)
_RE_ONSITE = re.compile(r"\b(onsite|on[\s-]site|in[\s-]office|office[\s-]based)\b", re.IGNORECASE)


def infer_remote_mode(title: str, description: str) -> RemoteMode:
    """Infer remote working mode from job title and description text."""
    text = f"{title} {description}"
    if _RE_FULLY_REMOTE.search(text):
        return RemoteMode.REMOTE
    if _RE_REMOTE_FIRST.search(text):
        return RemoteMode.REMOTE_FIRST
    if _RE_HYBRID.search(text):
        return RemoteMode.HYBRID
    if _RE_REMOTE.search(text):
        return RemoteMode.REMOTE
    if _RE_ONSITE.search(text):
        return RemoteMode.ONSITE
    return RemoteMode.UNKNOWN
