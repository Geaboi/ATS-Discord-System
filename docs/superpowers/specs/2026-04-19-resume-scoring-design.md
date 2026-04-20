# Design: Resume Scoring + Model Split

**Date:** 2026-04-19  
**Status:** Approved

## Summary

Add personalized resume-job match scoring using the user's uploaded master resumes. Scores are computed at scrape time and stored. The job feed shows the highest resume match percentage per job. The resumes page shows aggregated strengths and weaknesses per resume. A faster model (`llama3.2:3b`) is used for all scoring, while `llama3.1:8b` is kept for resume tailoring.

---

## Section 1: Model Split

- Add `OLLAMA_SCORING_MODEL=llama3.2:3b` to `.env.example` and `api/app/config.py`
- `score_job()` and new `rate_resume()` use `settings.ollama_scoring_model`
- `tailor_resume()` keeps using `settings.ollama_model` (`llama3.1:8b`)
- `ollama/entrypoint.sh` pulls both models on startup

---

## Section 2: Backend

### Database

New Alembic migration `003_add_resume_scores.py` creates the `resume_scores` table:

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| resume_id | UUID FK → resumes.id | ON DELETE CASCADE |
| job_id | UUID FK → jobs.id | ON DELETE CASCADE |
| score | FLOAT | 0.0–1.0 |
| strengths | TEXT[] | Array of strength strings |
| weaknesses | TEXT[] | Array of weakness strings |
| created_at | TIMESTAMPTZ | |

Unique constraint on `(resume_id, job_id)` — one score per resume-job pair. Index on `job_id` for the subquery in `list_jobs`.

### LLM Service (`api/app/services/llm.py`)

New `rate_resume()` function:
- Inputs: `resume_text: str`, `job_title: str`, `company: str`, `job_description: str`
- Prompt asks for JSON: `{score: float, strengths: string[], weaknesses: string[]}`
- Uses `ollama_scoring_model`, `num_predict: 400`, `temperature: 0.1`
- Falls back to `{score: 0.0, strengths: [], weaknesses: []}` on error
- Truncates resume to 600 words and description to 400 words to stay within context

`score_job()` updated to use `ollama_scoring_model` instead of `ollama_model`.

### Scraper (`api/app/services/scraper.py`)

In `_run_source()`, after a new job is committed to the DB:
1. Fetch all master resumes from DB (cached once per source run, not per job)
2. For each master resume with `extracted_text`, call `rate_resume()`
3. Upsert result into `resume_scores` using `INSERT ... ON CONFLICT DO UPDATE`

Gracefully skips if no master resumes exist. Resume scoring errors are logged as warnings and do not fail the scrape.

### API

**`JobOut` schema** gains:
```python
resume_match: Optional[float]  # highest score across master resumes, None if no resumes uploaded
```

**`list_jobs`** uses a scalar subquery to compute `resume_match` per job:
```sql
SELECT MAX(score) FROM resume_scores
JOIN resumes ON resume_scores.resume_id = resumes.id
WHERE resume_scores.job_id = jobs.id AND resumes.is_master = true
```

**New endpoint** `GET /api/resumes/{resume_id}/analysis`:
- Returns `{strengths: string[], weaknesses: string[]}` aggregated from the resume's 20 most recent `resume_scores` rows
- Aggregation: collect all strengths arrays and weaknesses arrays, deduplicate, return top 10 of each by frequency
- Returns `{strengths: [], weaknesses: []}` if no scores exist yet

New schema `ResumeAnalysis`:
```python
class ResumeAnalysis(BaseModel):
    strengths: list[str]
    weaknesses: list[str]
```

---

## Section 3: Frontend

### Job Card (`web/src/app/dashboard/page.tsx`)

Add a second score bar below the existing relevance score bar in the card's top-right corner:
- Label: "Resume" in xs slate text
- Same `ScoreBar` component reused
- Only rendered when `job.resume_match !== null`
- Existing score bar gets label "Match" for clarity

### Resumes Page (`web/src/app/dashboard/resumes/page.tsx`)

Each master resume card gets an "Analysis" button alongside the existing "Tailor →" button.

Clicking opens an inline panel (not a modal) below the resume row showing:
- **Strengths** section: green bullet list
- **Weaknesses** section: red bullet list
- Loading state while fetching
- "No analysis yet — scrape some jobs first" if both arrays are empty

### Types (`web/src/lib/types.ts`)

```typescript
// Add to Job interface:
resume_match: number | null;

// New type:
export interface ResumeAnalysis {
  strengths: string[];
  weaknesses: string[];
}
```

---

## Data Flow

```
Scrape new job
  → score_job() [llama3.2:3b] → relevance_score, experience_level
  → for each master resume:
      rate_resume() [llama3.2:3b] → score, strengths, weaknesses
      → upsert resume_scores row
  → commit job + scores

GET /api/jobs
  → subquery MAX(resume_scores.score) per job
  → JobOut.resume_match = highest score or null

GET /api/resumes/{id}/analysis
  → aggregate strengths/weaknesses from 20 most recent scores
  → return top 10 each by frequency
```

---

## Out of Scope

- Rescoring existing jobs against a newly uploaded resume (existing jobs stay unscored until re-scraped)
- Per-job strengths/weaknesses on the job card (only the score is shown there)
- Resume scoring for tailored (non-master) resumes
