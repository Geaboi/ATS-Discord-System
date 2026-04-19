import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    company: str
    location: Optional[str]
    remote: bool
    url: str
    description: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    source: str
    tags: list[str]
    relevance_score: Optional[float]
    score_reasoning: Optional[str]
    status: str
    posted_at: Optional[datetime]
    scraped_at: datetime
    notified: bool


class JobListOut(BaseModel):
    items: list[JobOut]
    total: int
    page: int
    limit: int
    pages: int


class JobUpdate(BaseModel):
    status: Optional[str] = None  # 'new' | 'bookmarked' | 'dismissed'


class ScrapeRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    started_at: datetime
    finished_at: Optional[datetime]
    jobs_found: int
    jobs_added: int
    error: Optional[str]


class ScrapeStatusOut(BaseModel):
    runs: list[ScrapeRunOut]
    scraping_now: bool
