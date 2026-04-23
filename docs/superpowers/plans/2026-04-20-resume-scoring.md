# Resume Scoring + Model Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add personalized resume-job match scoring using uploaded master resumes, shown on job cards and aggregated as strengths/weaknesses on the resumes page.

**Architecture:** A fast `llama3.2:3b` model scores jobs and resumes; `llama3.1:8b` is kept for tailoring. At scrape time, each new job is scored against all master resumes and results stored in a new `resume_scores` table. The job feed shows the best resume match per job via a batch subquery. The resumes page exposes aggregated strengths/weaknesses via a new API endpoint.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, Alembic, PostgreSQL, Ollama, Next.js/React, Tailwind CSS

---

## File Map

| File | Change |
|------|--------|
| `api/app/config.py` | Add `ollama_scoring_model` setting |
| `.env.example` | Add `OLLAMA_SCORING_MODEL=llama3.2:3b` |
| `ollama/entrypoint.sh` | Pull both models on startup |
| `api/app/services/llm.py` | Switch `score_job` to scoring model; add `rate_resume()` |
| `api/alembic/versions/003_add_resume_scores.py` | Create: migration |
| `api/app/models/resume_score.py` | Create: ResumeScore ORM model |
| `api/app/models/__init__.py` | Export ResumeScore |
| `api/app/services/scraper.py` | Score master resumes per new job |
| `api/app/schemas/job.py` | Add `resume_match` to JobOut |
| `api/app/schemas/resume.py` | Add `ResumeAnalysis` schema |
| `api/app/routers/jobs.py` | Attach resume_match via batch subquery |
| `api/app/routers/resumes.py` | Add analysis endpoint |
| `web/src/lib/types.ts` | Add `resume_match` to Job; add ResumeAnalysis |
| `web/src/app/dashboard/page.tsx` | Add resume match bar to job card |
| `web/src/app/dashboard/resumes/page.tsx` | Add Analysis button + inline panel |

---

### Task 1: Model Split — Config + Ollama + score_job

**Files:**
- Modify: `api/app/config.py`
- Modify: `.env.example`
- Modify: `ollama/entrypoint.sh`
- Modify: `api/app/services/llm.py`

- [ ] **Step 1: Add `ollama_scoring_model` to config**

In `api/app/config.py`, add after `ollama_model`:

```python
ollama_scoring_model: str = "llama3.2:3b"
```

- [ ] **Step 2: Add to `.env.example`**

In `.env.example`, add after `OLLAMA_MODEL=llama3.1:8b`:

```
# Fast model for job scoring and resume rating (smaller = faster)
OLLAMA_SCORING_MODEL=llama3.2:3b
```

- [ ] **Step 3: Update Ollama entrypoint to pull both models**

Replace the entire content of `ollama/entrypoint.sh`:

```sh
#!/bin/sh
# Start Ollama server, wait for readiness, then pull both models if not cached.

set -e

TAILORING_MODEL="${OLLAMA_MODEL:-llama3.1:8b}"
SCORING_MODEL="${OLLAMA_SCORING_MODEL:-llama3.2:3b}"

echo "[entrypoint] Starting Ollama server..."
ollama serve &
SERVER_PID=$!

echo "[entrypoint] Waiting for Ollama server to be ready..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done
echo "[entrypoint] Ollama server is ready."

for MODEL in "$TAILORING_MODEL" "$SCORING_MODEL"; do
    if ollama list | grep -q "^${MODEL}"; then
        echo "[entrypoint] Model '${MODEL}' already cached, skipping pull."
    else
        echo "[entrypoint] Pulling model '${MODEL}'..."
        ollama pull "${MODEL}"
        echo "[entrypoint] Model '${MODEL}' pulled successfully."
    fi
done

echo "[entrypoint] Ollama is ready."
wait $SERVER_PID
```

- [ ] **Step 4: Switch `score_job` to use `ollama_scoring_model`**

In `api/app/services/llm.py`, in `score_job()`, change line 76:

```python
"model": settings.ollama_scoring_model,
```

- [ ] **Step 5: Verify config loads**

```bash
docker compose exec api python3 -c "from app.config import get_settings; s = get_settings(); print(s.ollama_scoring_model)"
```

Expected output: `llama3.2:3b`

- [ ] **Step 6: Commit**

```bash
git add api/app/config.py .env.example ollama/entrypoint.sh api/app/services/llm.py
git commit -m "feat: add ollama_scoring_model config, switch score_job to fast model"
```

---

### Task 2: DB Migration — resume_scores table + ResumeScore model

**Files:**
- Create: `api/alembic/versions/003_add_resume_scores.py`
- Create: `api/app/models/resume_score.py`
- Modify: `api/app/models/__init__.py`

- [ ] **Step 1: Create the migration**

Create `api/alembic/versions/003_add_resume_scores.py`:

```python
"""Add resume_scores table

Revision ID: 003
Revises: 002
Create Date: 2026-04-20 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "resume_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("strengths", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("weaknesses", postgresql.ARRAY(sa.String()), nullable=True, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("resume_id", "job_id", name="uq_resume_scores_resume_job"),
    )
    op.create_index("idx_resume_scores_job_id", "resume_scores", ["job_id"])
    op.create_index("idx_resume_scores_resume_id", "resume_scores", ["resume_id"])


def downgrade() -> None:
    op.drop_index("idx_resume_scores_resume_id", "resume_scores")
    op.drop_index("idx_resume_scores_job_id", "resume_scores")
    op.drop_table("resume_scores")
```

- [ ] **Step 2: Create the SQLAlchemy model**

Create `api/app/models/resume_score.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class ResumeScore(Base):
    __tablename__ = "resume_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    weaknesses: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
```

- [ ] **Step 3: Export from models __init__**

In `api/app/models/__init__.py`, replace the entire file:

```python
from .job import Job, ScrapeRun
from .application import Application, ApplicationNote
from .resume import Resume
from .resume_score import ResumeScore
from .settings import AppSettings

__all__ = [
    "Job",
    "ScrapeRun",
    "Application",
    "ApplicationNote",
    "Resume",
    "ResumeScore",
    "AppSettings",
]
```

- [ ] **Step 4: Apply the migration**

```bash
docker compose exec api alembic upgrade head
```

Expected output ends with: `Running upgrade 002 -> 003, Add resume_scores table`

- [ ] **Step 5: Verify table exists**

```bash
docker compose exec db psql -U ats -d ats -c "\d resume_scores"
```

Expected: table with columns id, resume_id, job_id, score, strengths, weaknesses, created_at.

- [ ] **Step 6: Commit**

```bash
git add api/alembic/versions/003_add_resume_scores.py api/app/models/resume_score.py api/app/models/__init__.py
git commit -m "feat: add resume_scores table and ResumeScore model"
```

---

### Task 3: LLM — rate_resume function

**Files:**
- Modify: `api/app/services/llm.py`

- [ ] **Step 1: Add the resume rating prompt**

In `api/app/services/llm.py`, add after `_TAILOR_PROMPT`:

```python
_RATE_RESUME_PROMPT = """You are evaluating how well a candidate's resume matches a job posting.
Return ONLY valid JSON with these fields: score (float 0.0-1.0), strengths (array of strings), weaknesses (array of strings).

score: how well the resume matches the job (1.0 = perfect match, 0.0 = no match)
strengths: up to 5 specific things in the resume that match the job well (be concrete, e.g. "3 years Python matches required Python experience")
weaknesses: up to 5 specific gaps between the resume and the job (be concrete, e.g. "Job requires Kubernetes, not mentioned in resume")

Job: {title} at {company}
Job Description: {description}

Resume:
{resume}

Respond with JSON only, no markdown:"""
```

- [ ] **Step 2: Add the `rate_resume` function**

In `api/app/services/llm.py`, add after the `score_job` function:

```python
async def rate_resume(
    resume_text: str,
    job_title: str,
    company: str,
    job_description: str,
) -> dict:
    """Rate a resume against a job. Returns dict with score, strengths, weaknesses."""
    settings = get_settings()

    resume_truncated = " ".join(resume_text.split()[:600]) if resume_text else ""
    desc_truncated = " ".join(job_description.split()[:400]) if job_description else ""

    prompt = _RATE_RESUME_PROMPT.format(
        title=job_title,
        company=company,
        description=desc_truncated,
        resume=resume_truncated,
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_scoring_model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 400},
                },
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "{}")
            result = json.loads(raw)

            return {
                "score": float(result.get("score", 0.0)),
                "strengths": list(result.get("strengths", [])),
                "weaknesses": list(result.get("weaknesses", [])),
            }
    except Exception as e:
        logger.warning(f"Resume rating failed for '{job_title}' at '{company}': {e}")
        return {"score": 0.0, "strengths": [], "weaknesses": []}
```

- [ ] **Step 3: Verify manually**

```bash
docker compose exec api python3 -c "
import asyncio
from app.services.llm import rate_resume
result = asyncio.run(rate_resume('Python developer with React experience', 'Software Engineer', 'Google', 'Requires Python and React'))
print(result)
"
```

Expected: dict with `score`, `strengths`, `weaknesses` keys.

- [ ] **Step 4: Commit**

```bash
git add api/app/services/llm.py
git commit -m "feat: add rate_resume LLM function using fast scoring model"
```

---

### Task 4: Scraper — Score master resumes per new job

**Files:**
- Modify: `api/app/services/scraper.py`

- [ ] **Step 1: Update imports in scraper**

In `api/app/services/scraper.py`, update the imports block at the top:

```python
"""
Orchestrates all job source scrapers. Handles deduplication, scoring, DB inserts,
and Discord notifications.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models import Job, ScrapeRun, Resume
from app.models.resume_score import ResumeScore
from app.services.llm import score_job, rate_resume
from app.services.discord_notifier import notify_new_job

logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Fetch master resumes once per source run**

In `_run_source()`, add a master resumes fetch right after `run.jobs_found = len(raw_jobs)`:

```python
# Fetch master resumes once for the entire run (not per job)
master_resumes_result = await db.execute(
    select(Resume).where(Resume.is_master == True, Resume.extracted_text.isnot(None))
)
master_resumes = master_resumes_result.scalars().all()
```

- [ ] **Step 3: Score each new job against master resumes**

In `_run_source()`, after the existing `job.notified = True` line (inside the job loop, after Discord notification), add resume scoring before the batch commit check:

```python
                # Score against master resumes
                for resume in master_resumes:
                    try:
                        rating = await rate_resume(
                            resume_text=resume.extracted_text,
                            job_title=job.title,
                            company=job.company,
                            job_description=job_data.get("description") or "",
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
```

Also add `import uuid` to the imports at the top of the file (it's not currently imported in scraper.py).

- [ ] **Step 4: Commit**

```bash
git add api/app/services/scraper.py
git commit -m "feat: score master resumes against each new job at scrape time"
```

---

### Task 5: API — resume_match in JobOut + analysis endpoint

**Files:**
- Modify: `api/app/schemas/job.py`
- Modify: `api/app/schemas/resume.py`
- Modify: `api/app/routers/jobs.py`
- Modify: `api/app/routers/resumes.py`

- [ ] **Step 1: Add `resume_match` to `JobOut`**

In `api/app/schemas/job.py`, add to `JobOut` after `experience_level`:

```python
resume_match: Optional[float] = None
```

- [ ] **Step 2: Add `ResumeAnalysis` to resume schemas**

In `api/app/schemas/resume.py`, add at the end of the file:

```python
class ResumeAnalysis(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
```

- [ ] **Step 3: Update `list_jobs` to attach resume_match**

In `api/app/routers/jobs.py`, replace the imports block and the `list_jobs` function:

```python
import math
from collections import defaultdict
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Job, ScrapeRun, Resume
from app.models.resume_score import ResumeScore
from app.schemas.job import JobListOut, JobOut, JobUpdate, ScrapeStatusOut, ScrapeRunOut

router = APIRouter(prefix="/jobs", tags=["jobs"])

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

    # Batch-fetch best resume match per job
    job_ids = [j.id for j in jobs]
    resume_match_map: dict = {}
    if job_ids:
        rs_stmt = (
            select(ResumeScore.job_id, func.max(ResumeScore.score).label("max_score"))
            .join(Resume, ResumeScore.resume_id == Resume.id)
            .where(Resume.is_master == True)
            .where(ResumeScore.job_id.in_(job_ids))
            .group_by(ResumeScore.job_id)
        )
        rs_result = await db.execute(rs_stmt)
        resume_match_map = {row.job_id: row.max_score for row in rs_result}

    items = [
        JobOut.model_validate(j).model_copy(update={"resume_match": resume_match_map.get(j.id)})
        for j in jobs
    ]

    return JobListOut(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=math.ceil(total / limit) if total else 0,
    )
```

- [ ] **Step 4: Add the analysis endpoint to resumes router**

In `api/app/routers/resumes.py`, add these imports at the top:

```python
from collections import Counter
```

And add this import alongside the existing model imports:

```python
from app.models.resume_score import ResumeScore
from app.schemas.resume import ResumeOut, TailorRequest, TailorStatus, ResumeAnalysis
```

Then add the new endpoint after the `get_resume` route:

```python
@router.get("/{resume_id}/analysis", response_model=ResumeAnalysis)
async def get_resume_analysis(
    resume_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    resume = await db.get(Resume, resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")

    stmt = (
        select(ResumeScore)
        .where(ResumeScore.resume_id == resume_id)
        .order_by(ResumeScore.created_at.desc())
        .limit(20)
    )
    result = await db.execute(stmt)
    scores = result.scalars().all()

    all_strengths = [s for row in scores for s in (row.strengths or [])]
    all_weaknesses = [w for row in scores for w in (row.weaknesses or [])]

    strengths = [item for item, _ in Counter(all_strengths).most_common(10)]
    weaknesses = [item for item, _ in Counter(all_weaknesses).most_common(10)]

    return ResumeAnalysis(strengths=strengths, weaknesses=weaknesses)
```

- [ ] **Step 5: Verify the API endpoint exists**

```bash
curl -s http://localhost:8000/api/jobs?limit=1 -H "Authorization: Bearer $(docker compose exec api python3 -c 'from app.auth import create_access_token; print(create_access_token({\"sub\":\"test\"}))')" | python3 -m json.tool | grep resume_match
```

Expected: `"resume_match": null` (null until a scrape runs with a master resume uploaded).

- [ ] **Step 6: Commit**

```bash
git add api/app/schemas/job.py api/app/schemas/resume.py api/app/routers/jobs.py api/app/routers/resumes.py
git commit -m "feat: add resume_match to JobOut and resume analysis endpoint"
```

---

### Task 6: Frontend — Resume match bar + Analysis panel

**Files:**
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/app/dashboard/page.tsx`
- Modify: `web/src/app/dashboard/resumes/page.tsx`

- [ ] **Step 1: Update types**

In `web/src/lib/types.ts`, add `resume_match` to the `Job` interface after `experience_level`:

```typescript
resume_match: number | null;
```

Add `ResumeAnalysis` at the end of the file:

```typescript
export interface ResumeAnalysis {
  strengths: string[];
  weaknesses: string[];
}
```

- [ ] **Step 2: Add resume match bar to job card**

In `web/src/app/dashboard/page.tsx`, update the score section inside `JobCard` (the `{/* Score */}` div around line 108):

```tsx
{/* Score */}
<div className="shrink-0 flex flex-col items-end gap-1.5">
  <div className="flex items-center gap-2">
    <span className="text-xs text-slate-400">Match</span>
    <ScoreBar score={job.relevance_score} />
  </div>
  {job.resume_match !== null && (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-400">Resume</span>
      <ScoreBar score={job.resume_match} />
    </div>
  )}
  <span className="text-xs text-slate-400">{timeAgo(job.scraped_at)}</span>
</div>
```

- [ ] **Step 3: Add Analysis button and inline panel to resumes page**

In `web/src/app/dashboard/resumes/page.tsx`, add the import at the top:

```tsx
import { Resume, TailorStatus, Job, JobListResponse, ResumeAnalysis } from "@/lib/types";
```

Add analysis state inside `ResumesPage` after the `tailoring` state:

```tsx
const [analyzing, setAnalyzing] = useState<string | null>(null); // resume id
const [analysis, setAnalysis] = useState<Record<string, ResumeAnalysis>>({});
const [analysisLoading, setAnalysisLoading] = useState<string | null>(null);
```

Add the `handleAnalyze` function after `handleDelete`:

```tsx
async function handleAnalyze(id: string) {
  if (analyzing === id) {
    setAnalyzing(null);
    return;
  }
  setAnalyzing(id);
  if (!analysis[id]) {
    setAnalysisLoading(id);
    try {
      const data = await api.get<ResumeAnalysis>(`/api/resumes/${id}/analysis`);
      setAnalysis((prev) => ({ ...prev, [id]: data }));
    } finally {
      setAnalysisLoading(null);
    }
  }
}
```

Replace the master resume card rendering (the `masters.map` section) with:

```tsx
{masters.map((r) => (
  <div key={r.id}>
    <div className="bg-white rounded-xl border border-slate-200 px-4 py-3 flex items-center justify-between">
      <div>
        <p className="font-medium text-sm text-slate-900">{r.name}</p>
        <p className="text-xs text-slate-400 mt-0.5">{r.file_type.toUpperCase()} · {timeAgo(r.created_at)}</p>
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={() => handleAnalyze(r.id)}
          className={`text-xs font-medium transition-colors ${
            analyzing === r.id ? "text-primary" : "text-slate-500 hover:text-slate-700"
          }`}
        >
          {analyzing === r.id ? "Hide Analysis" : "Analysis"}
        </button>
        <button
          onClick={() => setTailoring(r)}
          className="text-xs font-medium text-primary hover:text-primary/80 transition-colors"
        >
          Tailor →
        </button>
        <a
          href={`/api/resumes/${r.id}/download`}
          download
          className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
        >
          Download
        </a>
        <button
          onClick={() => handleDelete(r.id)}
          className="text-xs text-red-400 hover:text-red-600 transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
    {analyzing === r.id && (
      <div className="border border-t-0 border-slate-200 rounded-b-xl bg-slate-50 px-4 py-4">
        {analysisLoading === r.id ? (
          <p className="text-sm text-slate-400">Loading analysis…</p>
        ) : analysis[r.id]?.strengths.length === 0 && analysis[r.id]?.weaknesses.length === 0 ? (
          <p className="text-sm text-slate-400">No analysis yet — scrape some jobs first.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs font-semibold text-emerald-600 uppercase tracking-wide mb-2">Strengths</p>
              <ul className="space-y-1">
                {analysis[r.id]?.strengths.map((s, i) => (
                  <li key={i} className="text-xs text-slate-700 flex gap-1.5">
                    <span className="text-emerald-500 shrink-0">✓</span>{s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-semibold text-red-500 uppercase tracking-wide mb-2">Weaknesses</p>
              <ul className="space-y-1">
                {analysis[r.id]?.weaknesses.map((w, i) => (
                  <li key={i} className="text-xs text-slate-700 flex gap-1.5">
                    <span className="text-red-400 shrink-0">✗</span>{w}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    )}
  </div>
))}
```

- [ ] **Step 4: Verify in browser**

Open http://localhost:3000. Check:
- Job cards show a "Resume" score bar below the "Match" bar (only visible after a scrape with a master resume uploaded)
- Resumes page shows an "Analysis" button on each master resume
- Clicking Analysis shows a loading state then strengths/weaknesses in a green/red two-column panel
- Clicking "Hide Analysis" collapses the panel

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/types.ts web/src/app/dashboard/page.tsx web/src/app/dashboard/resumes/page.tsx
git commit -m "feat: add resume match bar to job cards and analysis panel to resumes page"
```
