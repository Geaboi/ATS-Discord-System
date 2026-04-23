"""
Orchestrates all job source scrapers. Handles deduplication, scoring, DB inserts,
and Discord notifications.
"""
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Job, ScrapeRun, Resume
from app.models.settings import AppSettings
from app.models.resume_score import ResumeScore
from app.services.llm import score_job, rate_resume
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

        db_settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        db_settings = db_settings_result.scalar_one_or_none()
        scoring_model = db_settings.ollama_scoring_model if db_settings else None

        try:
            module = importlib.import_module(module_path)
            fetch = getattr(module, func_name)
            raw_jobs: list[dict] = await fetch()

            run.jobs_found = len(raw_jobs)

            # Fetch master resumes once for the entire run (not per job)
            master_resumes_result = await db.execute(
                select(Resume).where(Resume.is_master == True, Resume.extracted_text.isnot(None))
            )
            master_resumes = master_resumes_result.scalars().all()

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
                    model=scoring_model,
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

                # Score against master resumes
                for resume in master_resumes:
                    try:
                        rating = await rate_resume(
                            resume_text=resume.extracted_text,
                            job_title=job.title,
                            company=job.company,
                            job_description=job_data.get("description") or "",
                            model=scoring_model,
                        )
                        upsert_stmt = pg_insert(ResumeScore).values(
                            id=uuid.uuid4(),
                            resume_id=resume.id,
                            job_id=job.id,
                            score=rating["score"],
                            strengths=rating["strengths"],
                            weaknesses=rating["weaknesses"],
                            created_at=datetime.now(timezone.utc),
                        ).on_conflict_do_update(
                            constraint="uq_resume_scores_resume_job",
                            set_={
                                "score": rating["score"],
                                "strengths": rating["strengths"],
                                "weaknesses": rating["weaknesses"],
                                "created_at": datetime.now(timezone.utc),
                            }
                        )
                        await db.execute(upsert_stmt)
                    except Exception as e:
                        logger.warning(f"Resume scoring failed for job '{job.title}': {e}")

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
