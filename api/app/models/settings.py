from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AppSettings(Base):
    """Single-row settings table. Insert row id=1 on first access."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    discord_webhook: Mapped[str | None] = mapped_column(String)
    score_threshold: Mapped[float] = mapped_column(Float, default=0.65)
    scrape_interval: Mapped[int] = mapped_column(Integer, default=60)
    ollama_model: Mapped[str | None] = mapped_column(String, nullable=True)
    ollama_scoring_model: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
