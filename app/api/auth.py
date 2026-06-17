"""OIDC relying-party auth endpoints.

Flow: /api/auth/login → OIDC provider → /api/auth/callback → signed HTTP-only
session cookie → SPA.  All tokens from the provider are consumed server-side;
the browser only ever sees the opaque session cookie.
"""

from __future__ import annotations

import hmac
import secrets
import urllib.parse
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DbSession
from app.config import get_settings
from app.core.session import SESSION_DAYS, sign_session, verify_session
from app.models.user import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

SESSION_COOKIE = "session"
STATE_COOKIE = "oauth_state"
NONCE_COOKIE = "oauth_nonce"

_oidc_config_cache: dict[str, Any] | None = None


async def _get_oidc_config() -> dict[str, Any]:
    global _oidc_config_cache
    if _oidc_config_cache is None:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.oidc_issuer.rstrip('/')}/.well-known/openid-configuration",
                timeout=10,
            )
            resp.raise_for_status()
            _oidc_config_cache = resp.json()
    return _oidc_config_cache


class AuthUser(BaseModel):
    id: str
    email: str
    name: str


@router.get("/login")
async def login() -> RedirectResponse:
    settings = get_settings()
    if not settings.oidc_issuer:
        raise HTTPException(status_code=501, detail="OIDC not configured.")

    oidc = await _get_oidc_config()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
    }
    url = oidc["authorization_endpoint"] + "?" + urllib.parse.urlencode(params)

    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(STATE_COOKIE, state, max_age=300, httponly=True, samesite="lax")
    resp.set_cookie(NONCE_COOKIE, nonce, max_age=300, httponly=True, samesite="lax")
    return resp


@router.get("/callback")
async def callback(
    code: str,
    state: str,
    request: Request,
    session: DbSession,
) -> RedirectResponse:
    settings = get_settings()

    expected_state = request.cookies.get(STATE_COOKIE)
    if not expected_state or not hmac.compare_digest(state, expected_state):
        raise HTTPException(status_code=400, detail="Invalid state parameter.")

    oidc = await _get_oidc_config()

    async with httpx.AsyncClient() as http:
        token_resp = await http.post(
            oidc["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.oidc_redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
            timeout=15,
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        userinfo_resp = await http.get(
            oidc["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
            timeout=10,
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()

    sub: str = userinfo["sub"]
    email: str = userinfo.get("email", "")
    name: str = userinfo.get("name", email)

    allowed = [e.strip() for e in settings.oidc_allowed_emails.split(",") if e.strip()]
    if allowed and email not in allowed:
        raise HTTPException(status_code=403, detail="Email address not permitted.")

    # Provision or update the user record.
    user = session.scalar(select(User).where(User.oidc_sub == sub))
    if user is None:
        user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name, oidc_sub=sub)
        session.add(user)
    else:
        user.oidc_sub = sub
        if not user.name and name:
            user.name = name
    session.commit()

    token = sign_session(user.id)
    resp = RedirectResponse("/", status_code=302)
    resp.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
    )
    resp.delete_cookie(STATE_COOKIE)
    resp.delete_cookie(NONCE_COOKIE)
    return resp


@router.get("/me", response_model=AuthUser)
async def me(request: Request, session: DbSession) -> AuthUser:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user_id = verify_session(token)
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found.")
    return AuthUser(id=str(user.id), email=user.email, name=user.name)


@router.post("/logout")
async def logout() -> JSONResponse:
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax")
    return resp
