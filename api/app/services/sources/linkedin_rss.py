"""
LinkedIn public RSS feed scraper (unauthenticated).
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
SOURCE = "linkedin_rss"

_RSS_URLS = [
    "https://www.linkedin.com/jobs/search/?keywords=new+grad+software+engineer&f_E=1&f_JT=F",
    "https://www.linkedin.com/jobs/search/?keywords=entry+level+software+engineer&f_JT=F",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ATSBot/1.0; +https://github.com/example/ats)"
}


def _make_external_id(entry: dict) -> str:
    link = entry.get("link", "")
    h = hashlib.md5(link.encode()).hexdigest()[:12]
    return f"{SOURCE}:{h}"


async def fetch_jobs() -> list[dict]:
    results = []
    seen: set[str] = set()

    for rss_url in _RSS_URLS:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(rss_url, headers=_HEADERS)
                if r.status_code != 200:
                    logger.warning(f"LinkedIn RSS returned {r.status_code} for {rss_url}")
                    continue
                feed = feedparser.parse(r.text)

            for entry in feed.entries:
                ext_id = _make_external_id(entry)
                if ext_id in seen:
                    continue
                seen.add(ext_id)

                # Parse date
                posted_at: Optional[datetime] = None
                if published := entry.get("published_parsed"):
                    try:
                        posted_at = datetime(*published[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                title = entry.get("title", "").strip()
                # Extract company from title "Role at Company" pattern
                company = "Unknown"
                if " at " in title:
                    parts = title.rsplit(" at ", 1)
                    title = parts[0].strip()
                    company = parts[1].strip()

                results.append({
                    "external_id": ext_id,
                    "source": SOURCE,
                    "title": title,
                    "company": company,
                    "location": entry.get("location"),
                    "remote": False,
                    "url": entry.get("link", ""),
                    "description": entry.get("summary", ""),
                    "salary_min": None,
                    "salary_max": None,
                    "posted_at": posted_at,
                })
        except Exception as e:
            logger.warning(f"LinkedIn RSS fetch failed for {rss_url}: {e}")

    logger.info(f"LinkedIn RSS: fetched {len(results)} jobs")
    return results
