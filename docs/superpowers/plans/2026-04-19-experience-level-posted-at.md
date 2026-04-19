# Experience Level + Posted Date Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `experience_level` classification (intern/entry/mid/senior) and `posted_at` date display to job listings, with experience level filterable in the dashboard.

**Architecture:** LLM scoring prompt extended to return `experience_level` alongside existing fields. New DB column stores the value. API exposes it as a filter param. Frontend renders a badge and dropdown filter.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, Next.js/React, Tailwind CSS

---

## File Map

| File | Change |
|------|--------|
| `api/alembic/versions/002_add_experience_level.py` | Create: new migration |
| `api/app/models/job.py` | Modify: add `experience_level` column |
| `api/app/services/llm.py` | Modify: extend prompt + extract field from response |
| `api/app/services/scraper.py` | Modify: pass `experience_level` to Job model |
| `api/app/schemas/job.py` | Modify: add field to `JobOut` |
| `api/app/routers/jobs.py` | Modify: add `experience_level` query filter |
| `web/src/lib/types.ts` | Modify: add field to `Job` interface |
| `web/src/app/dashboard/page.tsx` | Modify: badge, posted_at display, filter dropdown |

---

### Task 1: DB Migration + Model

**Files:**
- Create: `api/alembic/versions/002_add_experience_level.py`
- Modify: `api/app/models/job.py`

- [ ] **Step 1: Create the migration file**

Create `api/alembic/versions/002_add_experience_level.py`:

```python
"""Add experience_level to jobs

Revision ID: 002
Revises: 001
Create Date: 2026-04-19 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("experience_level", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "experience_level")
```

- [ ] **Step 2: Add the column to the SQLAlchemy model**

In `api/app/models/job.py`, add after the `notified` line:

```python
experience_level: Mapped[str | None] = mapped_column(String, nullable=True)
```

- [ ] **Step 3: Apply the migration**

```bash
docker compose exec api alembic upgrade head
```

Expected output ends with: `Running upgrade 001 -> 002, Add experience_level to jobs`

- [ ] **Step 4: Verify column exists**

```bash
docker compose exec db psql -U ats -d ats -c "\d jobs"
```

Expected: `experience_level` column appears in the output with type `character varying`.

- [ ] **Step 5: Commit**

```bash
git add api/alembic/versions/002_add_experience_level.py api/app/models/job.py
git commit -m "feat: add experience_level column to jobs table"
```

---

### Task 2: LLM Prompt Extension

**Files:**
- Modify: `api/app/services/llm.py`

- [ ] **Step 1: Update `_SCORE_PROMPT` to request `experience_level`**

Replace the existing `_SCORE_PROMPT` in `api/app/services/llm.py`:

```python
_SCORE_PROMPT = """You are evaluating a job posting for a new grad computer science candidate.
Return ONLY valid JSON with these fields: score (float 0.0-1.0), reasoning (one sentence), tags (array of tech skills), experience_level (string).

experience_level must be one of:
- "intern": internship or co-op role
- "entry": new grad, 0-2 years, junior, associate
- "mid": 2-5 years experience, mid-level, Software Engineer II
- "senior": senior, staff, principal, lead, 5+ years
- "unknown": cannot determine from the information given

Candidate profile: Recent CS graduate with internship experience. Strong in Python, Java, data structures, algorithms. Familiar with web development (React, Node.js) and cloud basics.

Job title: {title}
Company: {company}
Description: {description}

Respond with JSON only, no markdown:"""
```

- [ ] **Step 2: Extract `experience_level` from the LLM response**

In `score_job()`, update the return statement:

```python
return {
    "score": float(result.get("score", 0.5)),
    "reasoning": str(result.get("reasoning", "")),
    "tags": list(result.get("tags", [])),
    "experience_level": str(result.get("experience_level", "unknown")),
}
```

Also update the fallback return in the `except` block:

```python
return {"score": 0.5, "reasoning": "Scoring unavailable", "tags": [], "experience_level": "unknown"}
```

- [ ] **Step 3: Verify manually**

```bash
docker compose exec api python3 -c "
import asyncio
from app.services.llm import score_job
result = asyncio.run(score_job('Senior Software Engineer', 'Google', 'Requires 5+ years Python experience'))
print(result)
"
```

Expected: dict includes `experience_level` key with value like `"senior"`.

- [ ] **Step 4: Commit**

```bash
git add api/app/services/llm.py
git commit -m "feat: extend LLM scoring prompt to classify experience_level"
```

---

### Task 3: Scraper — Pass Experience Level to Job Model

**Files:**
- Modify: `api/app/services/scraper.py`

- [ ] **Step 1: Pass `experience_level` when constructing the Job**

In `_run_source()` in `api/app/services/scraper.py`, add `experience_level` to the `Job(...)` constructor after `notified=False`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add api/app/services/scraper.py
git commit -m "feat: persist experience_level from LLM scoring to job record"
```

---

### Task 4: API Schema + Router Filter

**Files:**
- Modify: `api/app/schemas/job.py`
- Modify: `api/app/routers/jobs.py`

- [ ] **Step 1: Add `experience_level` to `JobOut`**

In `api/app/schemas/job.py`, add to `JobOut` after `score_reasoning`:

```python
experience_level: Optional[str]
```

- [ ] **Step 2: Add `experience_level` filter to `list_jobs`**

In `api/app/routers/jobs.py`, add the query param and filter. Update the `list_jobs` function signature and body:

```python
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
    if experience_level:
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
```

- [ ] **Step 3: Verify the API responds correctly**

```bash
curl -s "http://localhost:8000/api/jobs?experience_level=entry&limit=1" \
  -H "Authorization: Bearer <your_token>" | python3 -m json.tool
```

Expected: JSON response with `items` array where each job has `"experience_level": "entry"`.

- [ ] **Step 4: Commit**

```bash
git add api/app/schemas/job.py api/app/routers/jobs.py
git commit -m "feat: expose experience_level in JobOut schema and list_jobs filter"
```

---

### Task 5: Frontend — Types, Badge, Posted Date, Filter

**Files:**
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/app/dashboard/page.tsx`

- [ ] **Step 1: Add `experience_level` to the `Job` type**

In `web/src/lib/types.ts`, add to the `Job` interface after `posted_at`:

```typescript
experience_level: string | null;
```

- [ ] **Step 2: Add the `ExperienceBadge` component**

In `web/src/app/dashboard/page.tsx`, add this component after the `ScoreBar` component:

```tsx
const LEVEL_STYLES: Record<string, string> = {
  intern: "bg-purple-50 text-purple-600",
  entry: "bg-blue-50 text-blue-600",
  mid: "bg-amber-50 text-amber-600",
  senior: "bg-red-50 text-red-600",
};

function ExperienceBadge({ level }: { level: string | null }) {
  if (!level || level === "unknown" || !LEVEL_STYLES[level]) return null;
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${LEVEL_STYLES[level]}`}>
      {level.charAt(0).toUpperCase() + level.slice(1)}
    </span>
  );
}
```

- [ ] **Step 3: Add badge and posted date to `JobCard`**

In `JobCard`, update the source/remote badge row (around line 54-62) to include `ExperienceBadge`:

```tsx
<div className="flex items-center gap-2 mb-1">
  <span className="text-xs text-slate-400 font-medium uppercase tracking-wide">
    {SOURCES[job.source] || job.source}
  </span>
  {job.remote && (
    <span className="text-xs bg-emerald-50 text-emerald-600 px-1.5 py-0.5 rounded font-medium">
      Remote
    </span>
  )}
  <ExperienceBadge level={job.experience_level} />
</div>
```

Then update the company/location/salary row to add posted date (around line 72-86):

```tsx
<div className="flex items-center gap-2 mt-1 text-sm text-slate-500">
  <span className="font-medium text-slate-700">{job.company}</span>
  {job.location && (
    <>
      <span className="text-slate-300">·</span>
      <span>{job.location}</span>
    </>
  )}
  {salary && (
    <>
      <span className="text-slate-300">·</span>
      <span className="text-emerald-600 font-medium">{salary}</span>
    </>
  )}
  <span className="text-slate-300">·</span>
  <span>{timeAgo(job.posted_at ?? job.scraped_at)}</span>
</div>
```

- [ ] **Step 4: Add experience level state and filter dropdown**

In `DashboardPage`, add state after `minScore`:

```tsx
const [expLevel, setExpLevel] = useState<string>("");
```

Update the `load` function's params block to include `expLevel`:

```tsx
const params = new URLSearchParams({
  page: String(page),
  limit: "20",
  status: filter,
});
if (minScore > 0) params.set("min_score", String(minScore / 100));
if (expLevel) params.set("experience_level", expLevel);
```

Add `expLevel` to the `useCallback` dependency array:

```tsx
}, [page, filter, minScore, expLevel]);
```

Add the dropdown to the filter bar, after the min score select:

```tsx
<div className="flex items-center gap-2 text-sm text-slate-600">
  <span>Level:</span>
  <select
    value={expLevel}
    onChange={(e) => { setExpLevel(e.target.value); setPage(1); }}
    className="border border-slate-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:outline-none"
  >
    <option value="">Any</option>
    <option value="intern">Intern</option>
    <option value="entry">Entry</option>
    <option value="mid">Mid</option>
    <option value="senior">Senior</option>
  </select>
</div>
```

- [ ] **Step 5: Verify in browser**

Open http://localhost:3000. Check:
- Job cards show a colored experience badge (e.g. blue "Entry")
- Job cards show a posted date like "3d ago" in the metadata row
- The filter bar has a "Level" dropdown
- Selecting "Entry" from the dropdown reloads the list filtered to entry-level jobs only

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/types.ts web/src/app/dashboard/page.tsx
git commit -m "feat: add experience level badge, posted date, and level filter to job dashboard"
```
