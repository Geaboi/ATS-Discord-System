from typing import Optional
from pydantic import BaseModel, ConfigDict


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    discord_webhook: Optional[str]
    score_threshold: float
    scrape_interval: int
    ollama_model: Optional[str]
    ollama_scoring_model: Optional[str]


class SettingsUpdate(BaseModel):
    discord_webhook: Optional[str] = None
    score_threshold: Optional[float] = None
    scrape_interval: Optional[int] = None
    ollama_model: Optional[str] = None
    ollama_scoring_model: Optional[str] = None
