import asyncio
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import Resume
from app.schemas.resume import ResumeOut, TailorRequest, TailorStatus

router = APIRouter(prefix="/resumes", tags=["resumes"])

# In-memory task state: task_id -> { status, download_url, error }
_tailor_tasks: dict[str, dict] = {}


@router.get("", response_model=list[ResumeOut])
async def list_resumes(
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    result = await db.execute(select(Resume).order_by(Resume.created_at.desc()))
    return result.scalars().all()


@router.post("/upload", response_model=ResumeOut, status_code=status.HTTP_201_CREATED)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
    _: dict = Depends(get_current_user),
):
    allowed = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are accepted")

    ext = "pdf" if "pdf" in file.content_type else "docx"
    upload_dir = Path(settings.upload_dir) / "master"
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4()
    file_path = upload_dir / f"{file_id}.{ext}"
    content = await file.read()
    file_path.write_bytes(content)

    # Extract text
    from app.services.resume import extract_text
    extracted = extract_text(str(file_path), ext)

    resume = Resume(
        id=file_id,
        name=file.filename or f"resume.{ext}",
        file_path=str(file_path),
        file_type=ext,
        extracted_text=extracted,
        is_master=True,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("/tailor/{task_id}", response_model=TailorStatus)
async def get_tailor_status(
    task_id: str,
    _: dict = Depends(get_current_user),
):
    task = _tailor_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TailorStatus(task_id=task_id, **task)


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = Path(resume.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    return FileResponse(str(path), filename=resume.name)


@router.delete("/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_resume(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    path = Path(resume.file_path)
    if path.exists():
        path.unlink()
    await db.delete(resume)
    await db.commit()


@router.post("/{resume_id}/tailor", response_model=TailorStatus, status_code=status.HTTP_202_ACCEPTED)
async def tailor_resume(
    resume_id: UUID,
    body: TailorRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    settings=Depends(get_settings),
    _: dict = Depends(get_current_user),
):
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    if not resume.extracted_text:
        raise HTTPException(status_code=400, detail="Resume has no extracted text; re-upload the file")

    from app.models import Job
    job = await db.get(Job, body.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.description:
        raise HTTPException(status_code=400, detail="Job has no description for tailoring")

    task_id = str(uuid.uuid4())
    _tailor_tasks[task_id] = {"status": "pending", "download_url": None, "error": None}

    background_tasks.add_task(
        _run_tailoring,
        task_id=task_id,
        resume_id=str(resume_id),
        resume_text=resume.extracted_text,
        resume_name=resume.name,
        job_id=str(body.job_id),
        job_description=job.description,
        job_title=job.title,
        company=job.company,
        upload_dir=settings.upload_dir,
    )

    return TailorStatus(task_id=task_id, status="pending")


async def _run_tailoring(
    task_id: str,
    resume_id: str,
    resume_text: str,
    resume_name: str,
    job_id: str,
    job_description: str,
    job_title: str,
    company: str,
    upload_dir: str,
):
    from app.services.llm import tailor_resume as llm_tailor
    from app.database import AsyncSessionLocal
    import uuid

    _tailor_tasks[task_id]["status"] = "processing"
    try:
        tailored_text = await llm_tailor(resume_text, job_description, job_title, company)

        # Save tailored resume as a text file
        out_dir = Path(upload_dir) / "tailored"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_id = uuid.uuid4()
        out_path = out_dir / f"{file_id}.txt"
        out_path.write_text(tailored_text, encoding="utf-8")

        # Store in DB
        async with AsyncSessionLocal() as db:
            tailored = Resume(
                id=file_id,
                name=f"tailored_{resume_name.rsplit('.', 1)[0]}__{company}.txt",
                file_path=str(out_path),
                file_type="txt",
                extracted_text=tailored_text,
                is_master=False,
                tailored_for=uuid.UUID(job_id),
                parent_id=uuid.UUID(resume_id),
            )
            db.add(tailored)
            await db.commit()

        _tailor_tasks[task_id]["status"] = "complete"
        _tailor_tasks[task_id]["download_url"] = f"/api/resumes/{file_id}/download"
    except Exception as e:
        _tailor_tasks[task_id]["status"] = "error"
        _tailor_tasks[task_id]["error"] = str(e)
