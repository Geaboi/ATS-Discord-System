import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    relevance_score: Mapped[float | None] = mapped_column(Float)
    score_reasoning: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="new")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    experience_level: Mapped[str | None] = mapped_column(String, nullable=True)

    applications: Mapped[list["Application"]] = relationship(  # noqa: F821
        back_populates="job", cascade="all, delete-orphan"
    )
    resumes: Mapped[list["Resume"]] = relationship(  # noqa: F821
        back_populates="tailored_job", foreign_keys="Resume.tailored_for"
    )


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    jobs_found: Mapped[int] = mapped_column(Integer, default=0)
    jobs_added: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
