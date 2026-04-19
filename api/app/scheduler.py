"""
APScheduler setup. Registers periodic scrape jobs.
Scheduler is started and stopped in the FastAPI lifespan.
"""
import logging
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.config import get_settings

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduler() -> None:
    settings = get_settings()
    interval_minutes = settings.scrape_interval_minutes

    from app.services.scraper import run_all_scrapers

    # Stagger first runs so all sources don't fire simultaneously on startup
    scheduler.add_job(
        run_all_scrapers,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="scrape_all",
        name="Scrape all job sources",
        replace_existing=True,
        misfire_grace_time=300,
    )

    logger.info(f"Scheduler configured: scraping every {interval_minutes} minutes")
