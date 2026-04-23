"""
Ollama LLM client for job scoring and resume tailoring.
Communicates with the Ollama service on the internal Docker network.
"""
import json
import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Scoring prompt — kept short for fast inference
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

# Tailoring prompt
_TAILOR_PROMPT = """You are a professional resume writer helping a new grad CS candidate tailor their resume.

Given the master resume and the job description below, rewrite the resume to:
1. Emphasize the most relevant experience and skills for this specific role
2. Mirror the exact terminology and tech stack names used in the job description
3. Reorder bullet points to lead with the most relevant experience
4. Do NOT invent, fabricate, or exaggerate any experience
5. Keep the same overall structure and length
6. Output ONLY the tailored resume text, no commentary

Job: {title} at {company}

Job Description:
{jd_text}

Master Resume:
{resume_text}

Tailored Resume:"""

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


async def score_job(
    title: str,
    company: str,
    description: str,
    model: str | None = None,
) -> dict:
    """Score a job for relevance. Returns dict with score, reasoning, tags."""
    settings = get_settings()
    _model = model or settings.ollama_scoring_model

    # Truncate description to ~800 words to keep tokens manageable
    desc_truncated = " ".join(description.split()[:800]) if description else ""

    prompt = _SCORE_PROMPT.format(
        title=title, company=company, description=desc_truncated
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": _model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 350},
                },
            )
            response.raise_for_status()
            data = response.json()
            raw = data.get("response", "{}")
            result = json.loads(raw)

            return {
                "score": float(result.get("score", 0.5)),
                "reasoning": str(result.get("reasoning", "")),
                "tags": list(result.get("tags", [])),
                "experience_level": str(result.get("experience_level", "unknown")),
            }
    except Exception as e:
        logger.warning(f"LLM scoring failed for '{title}' at '{company}': {e}")
        return {"score": 0.5, "reasoning": "Scoring unavailable", "tags": [], "experience_level": "unknown"}


async def rate_resume(
    resume_text: str,
    job_title: str,
    company: str,
    job_description: str,
    model: str | None = None,
) -> dict:
    """Rate a resume against a job. Returns dict with score, strengths, weaknesses."""
    settings = get_settings()
    _model = model or settings.ollama_scoring_model

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
                    "model": _model,
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


async def tailor_resume(
    resume_text: str,
    jd_text: str,
    job_title: str,
    company: str,
    model: str | None = None,
) -> str:
    """Tailor a resume for a specific job. Returns the tailored resume text."""
    settings = get_settings()
    _model = model or settings.ollama_model

    prompt = _TAILOR_PROMPT.format(
        title=job_title,
        company=company,
        jd_text=jd_text,
        resume_text=resume_text,
    )

    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": _model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_predict": 2000},
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("response", "").strip()
