from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models.source import Source

router = APIRouter(prefix="/api/sources", tags=["sources"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


class SourceOut(BaseModel):
    id: uuid.UUID
    type: str
    name: str
    config: dict
    enabled: bool
    cadence_minutes: int
    authority: int
    last_run_at: str | None = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_source(cls, s: Source) -> SourceOut:
        return cls(
            id=s.id,
            type=s.type,
            name=s.name,
            config=s.config,
            enabled=s.enabled,
            cadence_minutes=s.cadence_minutes,
            authority=s.authority,
            last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
        )


class SourceCreate(BaseModel):
    type: str
    name: str
    config: dict = {}
    enabled: bool = True
    cadence_minutes: int = 60
    authority: int = 0


class SourceUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None
    enabled: bool | None = None
    cadence_minutes: int | None = None
    authority: int | None = None


DbSession = Annotated[Session, Depends(get_session)]


@router.get("", response_model=list[SourceOut])
def list_sources(session: DbSession) -> list[SourceOut]:
    sources = session.scalars(select(Source).order_by(Source.type, Source.name)).all()
    return [SourceOut.from_orm_source(s) for s in sources]


@router.post("", response_model=SourceOut, status_code=201)
def create_source(body: SourceCreate, session: DbSession) -> SourceOut:
    source = Source(
        type=body.type,
        name=body.name,
        config=body.config,
        enabled=body.enabled,
        cadence_minutes=body.cadence_minutes,
        authority=body.authority,
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return SourceOut.from_orm_source(source)


@router.put("/{source_id}", response_model=SourceOut)
def update_source(source_id: uuid.UUID, body: SourceUpdate, session: DbSession) -> SourceOut:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    if body.name is not None:
        source.name = body.name
    if body.config is not None:
        source.config = body.config
    if body.enabled is not None:
        source.enabled = body.enabled
    if body.cadence_minutes is not None:
        source.cadence_minutes = body.cadence_minutes
    if body.authority is not None:
        source.authority = body.authority
    session.commit()
    session.refresh(source)
    return SourceOut.from_orm_source(source)


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: uuid.UUID, session: DbSession) -> None:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    session.delete(source)
    session.commit()


@admin_router.post("/sources/{source_id}/run", status_code=202)
def run_source_now(source_id: uuid.UUID, session: DbSession) -> dict:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")

    from app.tasks.fetch import fetch_source_by_id

    task = fetch_source_by_id.delay(str(source_id))
    return {"task_id": task.id, "source_id": str(source_id), "source_name": source.name}
