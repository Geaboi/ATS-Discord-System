import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ApplicationCreate(BaseModel):
    job_id: uuid.UUID
    notes: Optional[str] = None
    stage: str = "interested"


class ApplicationUpdate(BaseModel):
    stage: Optional[str] = None
    applied_date: Optional[date] = None
    next_action: Optional[date] = None
    notes: Optional[str] = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    stage: str
    applied_date: Optional[date]
    next_action: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    content: str


class NoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    content: str
    created_at: datetime
