"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.user import User

DbSession = Annotated[Session, Depends(get_session)]


def _get_current_user(session: DbSession) -> User:
    """Return the seeded user. Replaced by real auth in Phase 6."""
    user = session.scalars(select(User)).first()
    if user is None:
        raise HTTPException(status_code=503, detail="No user found. Run `make seed` first.")
    return user


CurrentUser = Annotated[User, Depends(_get_current_user)]
