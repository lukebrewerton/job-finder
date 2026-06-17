"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.session import verify_session
from app.db import get_session
from app.models.user import User

DbSession = Annotated[Session, Depends(get_session)]


def _get_current_user(request: Request, session: DbSession) -> User:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user_id = verify_session(token)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    return user


CurrentUser = Annotated[User, Depends(_get_current_user)]
