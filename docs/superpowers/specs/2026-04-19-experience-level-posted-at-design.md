# Design: Experience Level Classification + Posted Date Display

**Date:** 2026-04-19  
**Status:** Approved

## Summary

Add `experience_level` classification and `posted_at` date display to job listings. Experience level is filterable in the dashboard. Both fields are derived at scrape time and stored in the database.

---

## Backend

### Database
New Alembic migration adds `experience_level VARCHAR` (nullable) to the `jobs` table. Valid values: `"intern"`, `"entry"`, `"mid"`, `"senior"`, `"unknown"`. Existing rows default to `NULL` (treated as unknown in the UI).

### LLM Scoring Prompt
Extend the existing `_SCORE_PROMPT` in `api/app/services/llm.py` to include `experience_level` in the required JSON response. The field is classified by the LLM based on job title and description. No additional Ollama call — it's one more field in the same JSON response.

Updated JSON contract:
```json
{
  "score": 0.85,
  "reasoning": "Strong Python match",
  "tags": ["Python", "React"],
  "experience_level": "entry"
}
```

Classification guide added to prompt:
- `intern`: internship or co-op
- `entry`: new grad, 0-2 years, junior, associate
- `mid`: 2-5 years, mid-level, software engineer II
- `senior`: senior, staff, principal, lead, 5+ years
- `unknown`: cannot determine

### Scraper
`score_result["experience_level"]` passed through to `Job` model in `api/app/services/scraper.py`. Falls back to `"unknown"` if field missing from LLM response.

### API Schema
- `JobOut`: add `experience_level: Optional[str]`
- `list_jobs` router: add optional `?experience_level=entry` query param, filtered via `Job.experience_level == value`

---

## Frontend

### Job Card (`web/src/app/dashboard/page.tsx`)
Two additions to the metadata row (company · location · salary line):

1. **Posted date**: `posted_at` rendered via existing `timeAgo()` util (e.g. "3 days ago"). Falls back to `scraped_at` if `posted_at` is null. Shown with a `·` separator.
2. **Experience level badge**: colored pill next to the source label:
   - `intern` → purple
   - `entry` → blue
   - `mid` → amber
   - `senior` → red
   - `unknown` / null → hidden

### Filter Bar
New experience level dropdown added to the filter row alongside the existing min score filter:
- Options: Any, Intern, Entry, Mid, Senior
- Selecting a value adds `experience_level=<value>` to the API request and resets to page 1

### Types (`web/src/lib/types.ts`)
Add `experience_level: string | null` to the `Job` interface.

---

## Data Flow

```
Ollama /api/generate
  → returns { score, reasoning, tags, experience_level }
  → scraper writes experience_level to Job row
  → API exposes via JobOut + list_jobs filter
  → frontend badge + dropdown filter
```

---

## Out of Scope
- Retroactively re-scoring existing jobs (existing rows stay NULL/unknown)
- Filtering by experience level in Discord notifications
- Experience level as a sort option
