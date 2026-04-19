"""
Adzuna API scraper for new grad software engineering jobs.
Free tier: 250 requests/day. No scraping, structured JSON.
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from dateutil import parser as date_parser

from app.config import get_settings

logger = logging.getLogger(__name__)

SOURCE = "adzuna"

# Adzuna country codes → base URL segment
_COUNTRY = "us"
_BASE_URL = f"https://api.adzuna.com/v1/api/jobs/{_COUNTRY}/search"

# Keywords targeting new grad CS roles
_SEARCH_TERMS = [
    "new grad software engineer",
    "entry level software engineer",
    "junior software engineer",
    "new graduate software developer",
]


def _make_external_id(job: dict) -> str:
    return f"{SOURCE}:{job.get('id', hashlib.md5(job.get('redirect_url', '').encode()).hexdigest())}"


async def fetch_jobs() -> list[dict]:
    """Fetch new grad jobs from Adzuna. Returns list of normalized job dicts."""
    settings = get_settings()
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        logger.warning("Adzuna credentials not configured, skipping")
        return []

    results = []
    seen_ids: set[str] = set()

    async with httpx.AsyncClient(timeout=15) as client:
        for term in _SEARCH_TERMS:
            try:
                params = {
                    "app_id": settings.adzuna_app_id,
                    "app_key": settings.adzuna_app_key,
                    "what": term,
                    "where": "United States",
                    "results_per_page": 20,
                    "max_days_old": 7,
                    "content-type": "application/json",
                }
                r = await client.get(f"{_BASE_URL}/1", params=params)
                r.raise_for_status()
                data = r.json()

                for job in data.get("results", []):
                    ext_id = _make_external_id(job)
                    if ext_id in seen_ids:
                        continue
                    seen_ids.add(ext_id)

                    # Parse posted date
                    posted_at: Optional[datetime] = None
                    if raw_date := job.get("created"):
                        try:
                            posted_at = date_parser.parse(raw_date).replace(tzinfo=timezone.utc)
                        except Exception:
                            pass

                    salary_min = salary_max = None
                    if sal := job.get("salary_min"):
                        salary_min = int(sal)
                    if sal := job.get("salary_max"):
                        salary_max = int(sal)

                    results.append({
                        "external_id": ext_id,
                        "source": SOURCE,
                        "title": job.get("title", "").strip(),
                        "company": job.get("company", {}).get("display_name", "Unknown"),
                        "location": job.get("location", {}).get("display_name"),
                        "remote": False,
                        "url": job.get("redirect_url", ""),
                        "description": job.get("description", ""),
                        "salary_min": salary_min,
                        "salary_max": salary_max,
                        "posted_at": posted_at,
                    })
            except Exception as e:
                logger.warning(f"Adzuna fetch failed for term '{term}': {e}")

    logger.info(f"Adzuna: fetched {len(results)} jobs")
    return results
