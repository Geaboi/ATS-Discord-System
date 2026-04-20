import math
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Job, ScrapeRun
from app.schemas.job import JobListOut, JobOut, JobUpdate, ScrapeStatusOut, ScrapeRunOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

# Flag to indicate a scrape is currently running (simple in-process guard)
_scraping_now: bool = False


@router.get("", response_model=JobListOut)
async def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    min_score: Optional[float] = Query(None),
    q: Optional[str] = Query(None),
    experience_level: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    stmt = select(Job)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if min_score is not None:
        stmt = stmt.where(Job.relevance_score >= min_score)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            Job.title.ilike(like) | Job.company.ilike(like) | Job.description.ilike(like)
        )
    _VALID_LEVELS = {"intern", "entry", "mid", "senior", "unknown"}
    if experience_level:
        if experience_level not in _VALID_LEVELS:
            raise HTTPException(status_code=422, detail=f"experience_level must be one of {sorted(_VALID_LEVELS)}")
        stmt = stmt.where(Job.experience_level == experience_level)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.order_by(Job.relevance_score.desc().nullslast(), Job.scraped_at.desc())
    stmt = stmt.offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    jobs = result.scalars().all()

    return JobListOut(
        items=jobs,
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total else 0,
    )


@router.get("/scrape/status", response_model=ScrapeStatusOut)
async def scrape_status(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    # Get the most recent run per source
    stmt = (
        select(ScrapeRun)
        .order_by(ScrapeRun.started_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    runs = result.scalars().all()
    return ScrapeStatusOut(runs=runs, scraping_now=_scraping_now)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: UUID,
    body: JobUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    if body.status is not None:
        valid = {"new", "bookmarked", "dismissed"}
        if body.status not in valid:
            raise HTTPException(status_code=400, detail=f"status must be one of {valid}")
        job.status = body.status

    await db.commit()
    await db.refresh(job)
    return job


@router.post("/scrape", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    from app.services.scraper import run_all_scrapers
    background_tasks.add_task(run_all_scrapers)
    return {"message": "Scrape started in background"}
