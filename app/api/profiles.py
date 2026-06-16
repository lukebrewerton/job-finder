from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.llm.provider import get_llm_provider
from app.core.llm.titles import expand_titles
from app.models.profile import SearchProfile

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ProfileOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    canonical_role: str
    seniority: str
    title_variations: list
    remote_modes: list
    require_salary: bool
    min_salary: int | None
    currency: str
    locations: list | None
    active: bool

    model_config = {"from_attributes": True}


class ProfileCreate(BaseModel):
    name: str
    canonical_role: str
    seniority: str
    remote_modes: list[str] = []
    require_salary: bool = False
    min_salary: int | None = None
    currency: str = "GBP"
    locations: list[str] | None = None
    active: bool = True


class ProfileUpdate(BaseModel):
    name: str | None = None
    canonical_role: str | None = None
    seniority: str | None = None
    # Explicit title_variations in the request body → persist as-is (user edit).
    # Absent → re-expand if canonical_role or seniority changed.
    title_variations: list[str] | None = None
    remote_modes: list[str] | None = None
    require_salary: bool | None = None
    min_salary: int | None = None
    currency: str | None = None
    locations: list[str] | None = None
    active: bool | None = None


@router.get("", response_model=list[ProfileOut])
def list_profiles(
    session: DbSession,
    user: CurrentUser,
    active_only: Annotated[bool, Query()] = False,
) -> list[SearchProfile]:
    q = select(SearchProfile).where(SearchProfile.user_id == user.id)
    if active_only:
        q = q.where(SearchProfile.active.is_(True))
    return list(session.scalars(q).all())


@router.post("", response_model=ProfileOut, status_code=201)
def create_profile(
    body: ProfileCreate,
    session: DbSession,
    user: CurrentUser,
) -> SearchProfile:
    provider = get_llm_provider()
    variations = expand_titles(body.canonical_role, body.seniority, provider)

    profile = SearchProfile(
        user_id=user.id,
        name=body.name,
        canonical_role=body.canonical_role,
        seniority=body.seniority,
        title_variations=variations,
        remote_modes=body.remote_modes,
        require_salary=body.require_salary,
        min_salary=body.min_salary,
        currency=body.currency,
        locations=body.locations,
        active=body.active,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.get("/{profile_id}", response_model=ProfileOut)
def get_profile(
    profile_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
) -> SearchProfile:
    profile = session.get(SearchProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@router.put("/{profile_id}", response_model=ProfileOut)
def update_profile(
    profile_id: uuid.UUID,
    body: ProfileUpdate,
    session: DbSession,
    user: CurrentUser,
) -> SearchProfile:
    profile = session.get(SearchProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(status_code=404, detail="Profile not found.")

    role_changed = body.canonical_role is not None and body.canonical_role != profile.canonical_role
    seniority_changed = body.seniority is not None and body.seniority != profile.seniority

    if body.name is not None:
        profile.name = body.name
    if body.canonical_role is not None:
        profile.canonical_role = body.canonical_role
    if body.seniority is not None:
        profile.seniority = body.seniority
    if body.remote_modes is not None:
        profile.remote_modes = body.remote_modes
    if body.require_salary is not None:
        profile.require_salary = body.require_salary
    if body.min_salary is not None:
        profile.min_salary = body.min_salary
    if body.currency is not None:
        profile.currency = body.currency
    if body.locations is not None:
        profile.locations = body.locations
    if body.active is not None:
        profile.active = body.active

    if body.title_variations is not None:
        # Explicit edit from user — persist without re-expanding.
        profile.title_variations = body.title_variations
    elif role_changed or seniority_changed:
        # Role or seniority changed without explicit variations → re-expand.
        provider = get_llm_provider()
        profile.title_variations = expand_titles(
            profile.canonical_role, profile.seniority, provider
        )

    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: uuid.UUID,
    session: DbSession,
    user: CurrentUser,
) -> None:
    profile = session.get(SearchProfile, profile_id)
    if profile is None or profile.user_id != user.id:
        raise HTTPException(status_code=404, detail="Profile not found.")
    session.delete(profile)
    session.commit()
