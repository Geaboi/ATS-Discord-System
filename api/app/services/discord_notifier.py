"""Post job alert embeds to a Discord webhook."""
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _score_color(score: Optional[float]) -> int:
    """Return a Discord embed color based on relevance score."""
    if score is None:
        return 0x95A5A6  # grey
    if score >= 0.85:
        return 0x2ECC71  # green
    if score >= 0.70:
        return 0xF39C12  # orange
    return 0xE67E22  # amber


async def notify_new_job(
    job_id: str,
    title: str,
    company: str,
    location: Optional[str],
    url: str,
    score: Optional[float],
    reasoning: Optional[str],
    tags: list[str],
    source: str,
    domain: str = "",
) -> bool:
    """Send a Discord embed for a new job posting. Returns True on success."""
    settings = get_settings()
    webhook_url = settings.discord_webhook_url
    if not webhook_url or not webhook_url.startswith("https://discord.com"):
        logger.debug("Discord webhook not configured, skipping notification")
        return False

    score_str = f"{score:.0%}" if score is not None else "N/A"
    tags_str = " · ".join(f"`{t}`" for t in tags[:6]) or "—"
    location_str = location or ("Remote" if True else "Unknown")

    dashboard_url = f"https://{domain}/dashboard?job={job_id}" if domain else url

    embed = {
        "title": title,
        "url": url,
        "color": _score_color(score),
        "description": reasoning or "",
        "fields": [
            {"name": "Company", "value": company, "inline": True},
            {"name": "Location", "value": location_str, "inline": True},
            {"name": "Relevance", "value": score_str, "inline": True},
            {"name": "Skills", "value": tags_str, "inline": False},
            {"name": "Source", "value": source.replace("_", " ").title(), "inline": True},
        ],
        "footer": {"text": "ATS Bot · New Grad Job Alert"},
    }

    components = [
        {
            "type": 1,
            "components": [
                {
                    "type": 2,
                    "style": 5,
                    "label": "View Job",
                    "url": url,
                },
                {
                    "type": 2,
                    "style": 5,
                    "label": "Open Dashboard",
                    "url": dashboard_url,
                },
            ],
        }
    ]

    payload = {"embeds": [embed], "components": components}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook_url, json=payload)
            if r.status_code in (200, 204):
                return True
            logger.warning(f"Discord webhook returned {r.status_code}: {r.text}")
            return False
    except Exception as e:
        logger.warning(f"Failed to send Discord notification: {e}")
        return False
