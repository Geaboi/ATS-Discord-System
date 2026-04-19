from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Application, ApplicationNote
from app.models.application import VALID_STAGES
from app.schemas.application import (
    ApplicationCreate,
    ApplicationOut,
    ApplicationUpdate,
    NoteCreate,
    NoteOut,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
async def list_applications(
    stage: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    stmt = select(Application)
    if stage:
        stmt = stmt.where(Application.stage == stage)
    stmt = stmt.order_by(Application.updated_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    body: ApplicationCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    if body.stage not in VALID_STAGES:
        raise HTTPException(status_code=400, detail=f"Invalid stage. Valid: {VALID_STAGES}")

    # Check no duplicate application for same job
    existing = await db.execute(
        select(Application).where(Application.job_id == body.job_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Application for this job already exists")

    app = Application(job_id=body.job_id, stage=body.stage, notes=body.notes)
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


@router.get("/{app_id}", response_model=ApplicationOut)
async def get_application(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@router.patch("/{app_id}", response_model=ApplicationOut)
async def update_application(
    app_id: UUID,
    body: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    if body.stage is not None:
        if body.stage not in VALID_STAGES:
            raise HTTPException(status_code=400, detail=f"Invalid stage. Valid: {VALID_STAGES}")
        app.stage = body.stage
    if body.applied_date is not None:
        app.applied_date = body.applied_date
    if body.next_action is not None:
        app.next_action = body.next_action
    if body.notes is not None:
        app.notes = body.notes

    await db.commit()
    await db.refresh(app)
    return app


@router.delete("/{app_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    await db.delete(app)
    await db.commit()


@router.post("/{app_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def add_note(
    app_id: UUID,
    body: NoteCreate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    app = await db.get(Application, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    note = ApplicationNote(application_id=app_id, content=body.content)
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.get("/{app_id}/notes", response_model=list[NoteOut])
async def list_notes(
    app_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    result = await db.execute(
        select(ApplicationNote)
        .where(ApplicationNote.application_id == app_id)
        .order_by(ApplicationNote.created_at)
    )
    return result.scalars().all()
