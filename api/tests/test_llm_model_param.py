import pytest
import httpx
import json
from unittest.mock import patch
from app.services.llm import score_job, rate_resume, tailor_resume


def make_client(captured: dict, response_body):
    """Create an httpx.AsyncClient with a mock transport that captures the request body."""

    class CapturingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            if isinstance(response_body, dict):
                return httpx.Response(200, json=response_body)
            return httpx.Response(200, text=response_body)

    # Return a real AsyncClient with a custom transport
    return httpx.AsyncClient(transport=CapturingTransport())


@pytest.mark.anyio
async def test_score_job_uses_passed_model():
    """score_job sends the explicit model name to Ollama when provided."""
    captured = {}
    client = make_client(captured, {"response": json.dumps({
        "score": 0.8, "reasoning": "good", "tags": [], "experience_level": "entry"
    })})

    with patch("app.services.llm.httpx.AsyncClient", return_value=client):
        await score_job("SWE", "Acme", "Python role", model="llama3.3:70b")

    assert captured["body"]["model"] == "llama3.3:70b"


@pytest.mark.anyio
async def test_score_job_falls_back_to_env_model():
    """score_job falls back to OLLAMA_SCORING_MODEL env var when model is None."""
    captured = {}
    client = make_client(captured, {"response": json.dumps({
        "score": 0.5, "reasoning": "ok", "tags": [], "experience_level": "unknown"
    })})

    with patch("app.services.llm.httpx.AsyncClient", return_value=client):
        await score_job("SWE", "Acme", "Python role", model=None)

    assert captured["body"]["model"] == "llama3.2:3b"  # default from config


@pytest.mark.anyio
async def test_tailor_resume_uses_passed_model():
    """tailor_resume sends the explicit model name to Ollama when provided."""
    captured = {}
    client = make_client(captured, {"response": "tailored resume text"})

    with patch("app.services.llm.httpx.AsyncClient", return_value=client):
        await tailor_resume("my resume", "job desc", "SWE", "Acme", model="llama3.2:3b")

    assert captured["body"]["model"] == "llama3.2:3b"
