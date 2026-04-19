"""
ATS Discord Alert Bot.

Polls the database every 5 minutes for new high-relevance jobs that haven't been
notified yet and posts rich embeds to the configured Discord webhook.
No bot gateway connection needed — pure webhook poster.
"""
import asyncio
import logging
import os
from typing import Optional

import asyncpg
import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("ats-bot")

# Configuration
DATABASE_URL = os.environ["DATABASE_URL"].replace(
    "postgresql+asyncpg://", "postgresql://"
)
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
DOMAIN = os.environ.get("DOMAIN", "")
POLL_INTERVAL = 300  # 5 minutes


def _score_color(score: Optional[float]) -> int:
    if score is None:
        return 0x95A5A6
    if score >= 0.85:
        return 0x2ECC71  # green
    if score >= 0.70:
        return 0xF1C40F  # yellow
    return 0xE67E22  # orange


async def fetch_pending_jobs(conn: asyncpg.Connection, threshold: float) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT id, title, company, location, url, relevance_score,
               score_reasoning, tags, source
        FROM jobs
        WHERE notified = false
          AND relevance_score >= $1
        ORDER BY relevance_score DESC
        LIMIT 20
        """,
        threshold,
    )
    return [dict(r) for r in rows]


async def mark_notified(conn: asyncpg.Connection, job_id: str) -> None:
    await conn.execute("UPDATE jobs SET notified = true WHERE id = $1", job_id)


async def get_score_threshold(conn: asyncpg.Connection) -> float:
    row = await conn.fetchrow("SELECT score_threshold FROM app_settings WHERE id = 1")
    return float(row["score_threshold"]) if row else 0.65


async def post_embed(job: dict) -> bool:
    if not DISCORD_WEBHOOK_URL or not DISCORD_WEBHOOK_URL.startswith("https://discord.com"):
        logger.warning("Discord webhook not configured")
        return False

    score = job.get("relevance_score")
    tags = job.get("tags") or []
    tags_str = " · ".join(f"`{t}`" for t in tags[:6]) or "—"
    score_str = f"{score:.0%}" if score is not None else "N/A"
    location_str = job.get("location") or "Unknown"
    job_id = str(job["id"])
    dashboard_url = f"https://{DOMAIN}/dashboard?job={job_id}" if DOMAIN else job["url"]

    embed = {
        "title": job["title"],
        "url": job["url"],
        "color": _score_color(score),
        "description": job.get("score_reasoning") or "",
        "fields": [
            {"name": "Company", "value": job["company"], "inline": True},
            {"name": "Location", "value": location_str, "inline": True},
            {"name": "Relevance", "value": score_str, "inline": True},
            {"name": "Skills", "value": tags_str, "inline": False},
            {"name": "Source", "value": str(job["source"]).replace("_", " ").title(), "inline": True},
        ],
        "footer": {"text": "ATS Bot · New Grad Job Alert"},
    }

    components = [
        {
            "type": 1,
            "components": [
                {"type": 2, "style": 5, "label": "View Job", "url": job["url"]},
                {"type": 2, "style": 5, "label": "Dashboard", "url": dashboard_url},
            ],
        }
    ]

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                DISCORD_WEBHOOK_URL,
                json={"embeds": [embed], "components": components},
            )
            if r.status_code in (200, 204):
                return True
            logger.warning(f"Webhook returned {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        logger.warning(f"Failed to post embed: {e}")
        return False


async def run_loop():
    logger.info("ATS Discord bot starting...")

    if not DISCORD_WEBHOOK_URL:
        logger.warning("DISCORD_WEBHOOK_URL not set — notifications will be skipped")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)
    logger.info("Database pool connected")

    while True:
        try:
            async with pool.acquire() as conn:
                threshold = await get_score_threshold(conn)
                jobs = await fetch_pending_jobs(conn, threshold)

                if jobs:
                    logger.info(f"Found {len(jobs)} unnotified jobs above threshold {threshold:.0%}")
                    for job in jobs:
                        success = await post_embed(job)
                        if success:
                            await mark_notified(conn, job["id"])
                            logger.info(f"Notified: {job['title']} @ {job['company']}")
                        await asyncio.sleep(1)  # brief pause between posts
                else:
                    logger.debug("No new jobs to notify")

        except Exception as e:
            logger.error(f"Bot loop error: {e}", exc_info=True)

        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_loop())
