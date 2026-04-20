from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models.settings import AppSettings
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_or_create_settings(db: AsyncSession) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if not row:
        row = AppSettings(id=1)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


@router.get("", response_model=SettingsOut)
async def get_settings_row(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    return await _get_or_create_settings(db)


@router.patch("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    row = await _get_or_create_settings(db)
    if body.discord_webhook is not None:
        row.discord_webhook = body.discord_webhook
    if body.score_threshold is not None:
        row.score_threshold = body.score_threshold
    if body.scrape_interval is not None:
        row.scrape_interval = body.scrape_interval
    if body.ollama_model is not None:
        row.ollama_model = body.ollama_model
    if body.ollama_scoring_model is not None:
        row.ollama_scoring_model = body.ollama_scoring_model
    await db.commit()
    await db.refresh(row)
    return row


@router.get("/health")
async def health(
    db: AsyncSession = Depends(get_db),
    config=Depends(get_settings),
):
    import httpx

    health_status = {"db": "ok", "ollama": "unknown", "discord": "unknown"}

    # DB check
    try:
        await db.execute(select(AppSettings))
        health_status["db"] = "ok"
    except Exception as e:
        health_status["db"] = f"error: {e}"

    # Ollama check
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{config.ollama_base_url}/api/tags")
            health_status["ollama"] = "ok" if r.status_code == 200 else f"error: {r.status_code}"
    except Exception as e:
        health_status["ollama"] = f"error: {e}"

    # Discord check (just verify webhook URL is set)
    if config.discord_webhook_url and config.discord_webhook_url.startswith("https://discord.com"):
        health_status["discord"] = "configured"
    else:
        health_status["discord"] = "not configured"

    return health_status
