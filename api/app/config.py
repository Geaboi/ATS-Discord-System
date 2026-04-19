from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://ats:changeme@db:5432/ats"

    # Auth
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    auth_email: str = "admin@example.com"
    auth_password_hash: str = ""

    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout: int = 90

    # Scrapers
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    simplify_url: str = "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json"

    # Discord
    discord_webhook_url: str = ""

    # App behavior
    scrape_interval_minutes: int = 60
    relevance_score_threshold: float = 0.65
    upload_dir: str = "/app/uploads"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
