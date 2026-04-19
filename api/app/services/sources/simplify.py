"""
SimplifyJobs/New-Grad-Positions scraper.
Community-maintained GitHub repo with a structured JSON file of new grad jobs.
No authentication needed (public repo).
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
SOURCE = "simplify"


def _make_external_id(job: dict) -> str:
    url = job.get("url") or job.get("link") or ""
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"{SOURCE}:{h}"


async def fetch_jobs() -> list[dict]:
    """Fetch jobs from the SimplifyJobs GitHub repo JSON file."""
    settings = get_settings()
    url = settings.simplify_url

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning(f"SimplifyJobs fetch failed: {e}")
        return []

    results = []
    # The JSON schema may vary; handle both list and dict-wrapped formats
    jobs = data if isinstance(data, list) else data.get("jobs", data.get("listings", []))

    for job in jobs:
        # Filter: must be active and not internship
        if not job.get("active", True):
            continue
        if "intern" in job.get("title", "").lower():
            continue

        url_val = (
            job.get("url")
            or job.get("link")
            or job.get("apply_url")
            or ""
        )
        if not url_val:
            continue

        ext_id = _make_external_id(job)

        # Parse date_posted if available
        posted_at: Optional[datetime] = None
        if ts := job.get("date_posted") or job.get("posted"):
            try:
                if isinstance(ts, (int, float)):
                    posted_at = datetime.fromtimestamp(ts, tz=timezone.utc)
                else:
                    from dateutil import parser as date_parser
                    posted_at = date_parser.parse(str(ts)).replace(tzinfo=timezone.utc)
            except Exception:
                pass

        locations = job.get("locations") or []
        location_str = ", ".join(locations[:2]) if locations else job.get("location")

        results.append({
            "external_id": ext_id,
            "source": SOURCE,
            "title": (job.get("title") or "").strip(),
            "company": (job.get("company_name") or job.get("company") or "Unknown").strip(),
            "location": location_str,
            "remote": any(
                "remote" in str(loc).lower() for loc in (locations or [location_str or ""])
            ),
            "url": url_val,
            "description": job.get("description") or "",
            "salary_min": None,
            "salary_max": None,
            "posted_at": posted_at,
        })

    logger.info(f"SimplifyJobs: fetched {len(results)} active jobs")
    return results
