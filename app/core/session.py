"""JWT session cookie helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from fastapi import HTTPException

from app.config import get_settings

SESSION_DAYS = 30


def sign_session(user_id: uuid.UUID) -> str:
    """Sign a session JWT containing the user's id as `sub`."""
    settings = get_settings()
    exp = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    return pyjwt.encode(
        {"sub": str(user_id), "exp": exp},
        settings.session_secret,
        algorithm="HS256",
    )


def verify_session(token: str) -> uuid.UUID:
    """Decode a session JWT and return the user_id, raising 401 on failure."""
    settings = get_settings()
    try:
        payload = pyjwt.decode(token, settings.session_secret, algorithms=["HS256"])
        return uuid.UUID(payload["sub"])
    except (pyjwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired session.") from exc
