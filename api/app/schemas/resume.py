import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    file_type: str
    is_master: bool
    tailored_for: Optional[uuid.UUID]
    parent_id: Optional[uuid.UUID]
    created_at: datetime


class TailorRequest(BaseModel):
    job_id: uuid.UUID


class TailorStatus(BaseModel):
    task_id: str
    status: str  # 'pending' | 'processing' | 'complete' | 'error'
    download_url: Optional[str] = None
    error: Optional[str] = None


class ResumeAnalysis(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
