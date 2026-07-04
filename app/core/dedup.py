# Copyright (C) 2026 Luke Brewerton
# SPDX-License-Identifier: AGPL-3.0-or-later
import hashlib
import re


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def make_content_hash(title: str, company: str, location: str | None) -> str:
    parts = f"{title.lower().strip()}|{company.lower().strip()}|{(location or '').lower().strip()}"
    return hashlib.sha256(parts.encode()).hexdigest()


def make_dedup_key(title: str, company: str, location: str | None) -> str:
    return f"{_slug(company)}::{_slug(title)}::{_slug(location or '')}"
