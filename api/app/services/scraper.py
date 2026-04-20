"""
Orchestrates all job source scrapers. Handles deduplication, scoring, DB inserts,
and Discord notifications.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Job, ScrapeRun
from app.services.llm import score_job
from app.services.discord_notifier import notify_new_job

logger = logging.getLogger(__name__)

_SOURCES = [
    ("adzuna", "app.services.sources.adzuna", "fetch_jobs"),
    ("simplify", "app.services.sources.simplify", "fetch_jobs"),
    ("linkedin_rss", "app.services.sources.linkedin_rss", "fetch_jobs"),
    ("indeed_rss", "app.services.sources.indeed_rss", "fetch_jobs"),
]


async def run_all_scrapers() -> None:
    """Run all scrapers sequentially and persist results."""
    for source_name, module_path, func_name in _SOURCES:
        await _run_source(source_name, module_path, func_name)


async def _run_source(source_name: str, module_path: str, func_name: str) -> None:
    import importlib
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        run = ScrapeRun(source=source_name, started_at=datetime.now(timezone.utc))
        db.add(run)
        await db.commit()
        await db.refresh(run)

        try:
            module = importlib.import_module(module_path)
            fetch = getattr(module, func_name)
            raw_jobs: list[dict] = await fetch()

            run.jobs_found = len(raw_jobs)
            new_count = 0
            BATCH_SIZE = 10

            for job_data in raw_jobs:
                # Skip entries with no URL
                if not job_data.get("url") or not job_data.get("title"):
                    continue

                # Check for existing job by external_id
                existing = await db.execute(
                    select(Job).where(Job.external_id == job_data["external_id"])
                )
                if existing.scalar_one_or_none():
                    continue

                # Score with LLM
                score_result = await score_job(
                    title=job_data["title"],
                    company=job_data["company"],
                    description=job_data.get("description") or "",
                )

                job = Job(
                    external_id=job_data["external_id"],
                    source=job_data["source"],
                    title=job_data["title"],
                    company=job_data["company"],
                    location=job_data.get("location"),
                    remote=job_data.get("remote", False),
                    url=job_data["url"],
                    description=job_data.get("description"),
                    salary_min=job_data.get("salary_min"),
                    salary_max=job_data.get("salary_max"),
                    posted_at=job_data.get("posted_at"),
                    tags=score_result["tags"],
                    relevance_score=score_result["score"],
                    score_reasoning=score_result["reasoning"],
                    experience_level=score_result.get("experience_level", "unknown"),
                    status="new",
                    notified=False,
                )

                try:
                    db.add(job)
                    await db.flush()
                    new_count += 1
                except IntegrityError:
                    await db.rollback()
                    continue

                # Send Discord notification for high-relevance jobs
                if score_result["score"] >= settings.relevance_score_threshold:
                    await notify_new_job(
                        job_id=str(job.id),
                        title=job.title,
                        company=job.company,
                        location=job.location,
                        url=job.url,
                        score=job.relevance_score,
                        reasoning=job.score_reasoning,
                        tags=job.tags or [],
                        source=job.source,
                    )
                    job.notified = True

                # Commit every BATCH_SIZE jobs so they appear in the dashboard progressively
                if new_count % BATCH_SIZE == 0:
                    run.jobs_added = new_count
                    await db.commit()

            run.jobs_added = new_count
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()

            logger.info(f"[{source_name}] Found {len(raw_jobs)}, added {new_count} new jobs")

        except Exception as e:
            logger.error(f"[{source_name}] Scraper error: {e}", exc_info=True)
            run.error = str(e)
            run.finished_at = datetime.now(timezone.utc)
            await db.commit()
