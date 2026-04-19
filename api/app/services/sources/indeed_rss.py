"""
Indeed RSS feed scraper (unauthenticated public RSS).
"""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
SOURCE = "indeed_rss"

_RSS_URLS = [
    "https://www.indeed.com/rss?q=new+grad+software+engineer&l=United+States&jt=fulltime",
    "https://www.indeed.com/rss?q=entry+level+software+engineer&l=United+States&jt=fulltime",
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ATSBot/1.0; +https://github.com/example/ats)"
}


def _make_external_id(entry: dict) -> str:
    link = entry.get("link", "") or entry.get("id", "")
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
                    logger.warning(f"Indeed RSS returned {r.status_code} for {rss_url}")
                    continue
                feed = feedparser.parse(r.text)

            for entry in feed.entries:
                ext_id = _make_external_id(entry)
                if ext_id in seen:
                    continue
                seen.add(ext_id)

                posted_at: Optional[datetime] = None
                if published := entry.get("published_parsed"):
                    try:
                        posted_at = datetime(*published[:6], tzinfo=timezone.utc)
                    except Exception:
                        pass

                # Indeed puts "Company - Location" in the source field
                company = "Unknown"
                location = None
                if source := entry.get("source", {}).get("title"):
                    if " - " in source:
                        parts = source.split(" - ", 1)
                        company = parts[0].strip()
                        location = parts[1].strip()
                    else:
                        company = source

                results.append({
                    "external_id": ext_id,
                    "source": SOURCE,
                    "title": entry.get("title", "").strip(),
                    "company": company,
                    "location": location,
                    "remote": False,
                    "url": entry.get("link", ""),
                    "description": entry.get("summary", ""),
                    "salary_min": None,
                    "salary_max": None,
                    "posted_at": posted_at,
                })
        except Exception as e:
            logger.warning(f"Indeed RSS fetch failed for {rss_url}: {e}")

    logger.info(f"Indeed RSS: fetched {len(results)} jobs")
    return results
