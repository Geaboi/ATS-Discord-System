# AWS Deployment + Model Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add DB-backed model selection to the settings UI, remove the Ollama container from Docker Compose, then deploy the stack to AWS EC2 t2.micro with Ollama served over Tailscale from the local machine.

**Architecture:** Phase 1 adds `ollama_model` and `ollama_scoring_model` columns to `app_settings`, exposing them via the existing settings API and a new UI dropdown. LLM functions accept an optional `model` parameter; callers fetch the DB value and pass it in. Phase 2 removes the `ollama` Docker service and deploys to EC2 with `OLLAMA_BASE_URL` pointing to the local machine's Tailscale IP.

**Tech Stack:** FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2, Next.js 14, Docker Compose, AWS EC2 t2.micro, Tailscale, Caddy

---

## Phase 1: Model Selection Feature

### Task 1: Add test dependencies and conftest

**Files:**
- Modify: `api/requirements.txt`
- Create: `api/tests/__init__.py`
- Create: `api/tests/conftest.py`

- [ ] **Step 1: Add test dependencies to requirements.txt**

Add these lines at the end of `api/requirements.txt`:

```
# Testing
pytest==8.3.4
pytest-asyncio==0.24.0
respx==0.21.1
```

- [ ] **Step 2: Create `api/tests/__init__.py`** (empty file)

- [ ] **Step 3: Create `api/tests/conftest.py`**

```python
import pytest

pytest_plugins = ["anyio"]
```

- [ ] **Step 4: Install new deps**

```bash
cd api && pip install pytest==8.3.4 pytest-asyncio==0.24.0 respx==0.21.1
```

Expected: packages install without errors.

- [ ] **Step 5: Commit**

```bash
git add api/requirements.txt api/tests/__init__.py api/tests/conftest.py
git commit -m "chore: add pytest + respx test dependencies"
```

---

### Task 2: Alembic migration — add model columns to app_settings

**Files:**
- Create: `api/alembic/versions/004_add_model_settings.py`

- [ ] **Step 1: Create the migration file `api/alembic/versions/004_add_model_settings.py`**

```python
"""Add ollama_model and ollama_scoring_model to app_settings

Revision ID: 004
Revises: 003
Create Date: 2026-04-20 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("ollama_model", sa.String(), nullable=True))
    op.add_column("app_settings", sa.Column("ollama_scoring_model", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "ollama_scoring_model")
    op.drop_column("app_settings", "ollama_model")
```

- [ ] **Step 2: Run the migration against your local DB**

```bash
cd api
DATABASE_URL="postgresql+asyncpg://ats:yourpassword@localhost:5432/ats" alembic upgrade head
```

Expected output ends with: `Running upgrade 003 -> 004, Add ollama_model and ollama_scoring_model to app_settings`

- [ ] **Step 3: Verify columns exist**

```bash
docker compose exec db psql -U ats -d ats -c "\d app_settings"
```

Expected: table shows `ollama_model` and `ollama_scoring_model` columns (character varying, nullable).

- [ ] **Step 4: Commit**

```bash
git add api/alembic/versions/004_add_model_settings.py
git commit -m "feat: migration 004 — add ollama_model columns to app_settings"
```

---

### Task 3: Update AppSettings model and schemas

**Files:**
- Modify: `api/app/models/settings.py`
- Modify: `api/app/schemas/settings.py`

- [ ] **Step 1: Write a failing test for the new schema fields**

Create `api/tests/test_settings_schema.py`:

```python
from app.schemas.settings import SettingsOut, SettingsUpdate


def test_settings_out_includes_model_fields():
    s = SettingsOut(
        discord_webhook=None,
        score_threshold=0.65,
        scrape_interval=60,
        ollama_model="llama3.1:8b",
        ollama_scoring_model="llama3.2:3b",
    )
    assert s.ollama_model == "llama3.1:8b"
    assert s.ollama_scoring_model == "llama3.2:3b"


def test_settings_update_model_fields_optional():
    u = SettingsUpdate()
    assert u.ollama_model is None
    assert u.ollama_scoring_model is None
```

- [ ] **Step 2: Run to verify test fails**

```bash
cd api && pytest tests/test_settings_schema.py -v
```

Expected: `FAILED — unexpected keyword argument 'ollama_model'`

- [ ] **Step 3: Update `api/app/models/settings.py`**

Replace the full file with:

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class AppSettings(Base):
    """Single-row settings table. Insert row id=1 on first access."""

    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    discord_webhook: Mapped[str | None] = mapped_column(String)
    score_threshold: Mapped[float] = mapped_column(Float, default=0.65)
    scrape_interval: Mapped[int] = mapped_column(Integer, default=60)
    ollama_model: Mapped[str | None] = mapped_column(String, nullable=True)
    ollama_scoring_model: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
```

- [ ] **Step 4: Update `api/app/schemas/settings.py`**

Replace the full file with:

```python
from typing import Optional
from pydantic import BaseModel, ConfigDict


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    discord_webhook: Optional[str]
    score_threshold: float
    scrape_interval: int
    ollama_model: Optional[str]
    ollama_scoring_model: Optional[str]


class SettingsUpdate(BaseModel):
    discord_webhook: Optional[str] = None
    score_threshold: Optional[float] = None
    scrape_interval: Optional[int] = None
    ollama_model: Optional[str] = None
    ollama_scoring_model: Optional[str] = None
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd api && pytest tests/test_settings_schema.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add api/app/models/settings.py api/app/schemas/settings.py api/tests/test_settings_schema.py
git commit -m "feat: add ollama_model fields to AppSettings model and schema"
```

---

### Task 4: Update settings router to persist model fields

**Files:**
- Modify: `api/app/routers/settings.py`

- [ ] **Step 1: Update the PATCH handler in `api/app/routers/settings.py`**

Replace the `update_settings` function (lines 33–48) with:

```python
@router.patch("", response_model=SettingsOut)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: dict = Depends(get_current_user),
):
    row = await _get_or_create_settings(db)
    if body.discord_webhook is not None:
        row.discord_webhook = body.discord_webhook
    if body.score_threshold is not None:
        row.score_threshold = body.score_threshold
    if body.scrape_interval is not None:
        row.scrape_interval = body.scrape_interval
    if body.ollama_model is not None:
        row.ollama_model = body.ollama_model
    if body.ollama_scoring_model is not None:
        row.ollama_scoring_model = body.ollama_scoring_model
    await db.commit()
    await db.refresh(row)
    return row
```

- [ ] **Step 2: Verify the API responds correctly**

Start the API locally (`uvicorn app.main:app --reload`) then:

```bash
# Get current settings — should show ollama_model: null
curl -s -b "access_token=<your-token>" http://localhost:8000/api/settings | python3 -m json.tool

# Update the tailoring model
curl -s -X PATCH http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -b "access_token=<your-token>" \
  -d '{"ollama_model": "llama3.1:8b"}' | python3 -m json.tool
```

Expected: PATCH response contains `"ollama_model": "llama3.1:8b"`.

- [ ] **Step 3: Commit**

```bash
git add api/app/routers/settings.py
git commit -m "feat: expose ollama_model fields in settings GET/PATCH"
```

---

### Task 5: Update llm.py to accept model overrides

**Files:**
- Modify: `api/app/services/llm.py`
- Create: `api/tests/test_llm_model_param.py`

- [ ] **Step 1: Write failing tests**

Create `api/tests/test_llm_model_param.py`:

```python
import pytest
import respx
import httpx
import json
from app.services.llm import score_job, rate_resume, tailor_resume


@pytest.mark.anyio
@respx.mock
async def test_score_job_uses_passed_model():
    """score_job sends the explicit model name to Ollama when provided."""
    captured = {}

    def capture(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": json.dumps({
            "score": 0.8, "reasoning": "good", "tags": [], "experience_level": "entry"
        })})

    respx.post("http://ollama:11434/api/generate").mock(side_effect=capture)

    await score_job("SWE", "Acme", "Python role", model="llama3.3:70b")
    assert captured["body"]["model"] == "llama3.3:70b"


@pytest.mark.anyio
@respx.mock
async def test_score_job_falls_back_to_env_model():
    """score_job falls back to OLLAMA_SCORING_MODEL env var when model is None."""
    captured = {}

    def capture(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": json.dumps({
            "score": 0.5, "reasoning": "ok", "tags": [], "experience_level": "unknown"
        })})

    respx.post("http://ollama:11434/api/generate").mock(side_effect=capture)

    await score_job("SWE", "Acme", "Python role", model=None)
    assert captured["body"]["model"] == "llama3.2:3b"  # default from config


@pytest.mark.anyio
@respx.mock
async def test_tailor_resume_uses_passed_model():
    """tailor_resume sends the explicit model name to Ollama when provided."""
    captured = {}

    def capture(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": "tailored resume text"})

    respx.post("http://ollama:11434/api/generate").mock(side_effect=capture)

    await tailor_resume("my resume", "job desc", "SWE", "Acme", model="llama3.2:3b")
    assert captured["body"]["model"] == "llama3.2:3b"
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd api && pytest tests/test_llm_model_param.py -v
```

Expected: `FAILED — score_job() got an unexpected keyword argument 'model'`

- [ ] **Step 3: Update `api/app/services/llm.py`**

Replace the three async function signatures and their internal model references:

**`score_job` — change signature and model line:**

```python
async def score_job(
    title: str,
    company: str,
    description: str,
    model: str | None = None,
) -> dict:
    """Score a job for relevance. Returns dict with score, reasoning, tags."""
    settings = get_settings()
    _model = model or settings.ollama_scoring_model
    # ... rest of function unchanged except replace settings.ollama_scoring_model with _model
```

In the `json={...}` block inside `score_job`, change:
```python
"model": settings.ollama_scoring_model,
```
to:
```python
"model": _model,
```

**`rate_resume` — change signature and model line:**

```python
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
```

In the `json={...}` block inside `rate_resume`, change:
```python
"model": settings.ollama_scoring_model,
```
to:
```python
"model": _model,
```

**`tailor_resume` — change signature and model line:**

```python
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
```

In the `json={...}` block inside `tailor_resume`, change:
```python
"model": settings.ollama_model,
```
to:
```python
"model": _model,
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd api && pytest tests/test_llm_model_param.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add api/app/services/llm.py api/tests/test_llm_model_param.py
git commit -m "feat: add optional model param to llm functions, falls back to env var"
```

---

### Task 6: Update callers to pass DB model values

**Files:**
- Modify: `api/app/services/scraper.py`
- Modify: `api/app/routers/resumes.py`

- [ ] **Step 1: Update `api/app/services/scraper.py`**

In `_run_source`, after the `async with AsyncSessionLocal() as db:` block opens and `run` is committed, add a fetch for DB settings. Find this section (around line 40):

```python
async with AsyncSessionLocal() as db:
    run = ScrapeRun(source=source_name, started_at=datetime.now(timezone.utc))
    db.add(run)
    await db.commit()
    await db.refresh(run)
```

Add the import at the top of the file (with the other imports):

```python
from app.models.settings import AppSettings
```

Then, immediately after `await db.refresh(run)`, add:

```python
        db_settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
        db_settings = db_settings_result.scalar_one_or_none()
        scoring_model = db_settings.ollama_scoring_model if db_settings else None
```

Then pass `model=scoring_model` to both `score_job` and `rate_resume` calls. Find the `score_job` call (around line 75):

```python
                score_result = await score_job(
                    title=job_data["title"],
                    company=job_data["company"],
                    description=job_data.get("description") or "",
                    model=scoring_model,
                )
```

And the `rate_resume` call (around line 127):

```python
                        rating = await rate_resume(
                            resume_text=resume.extracted_text,
                            job_title=job.title,
                            company=job.company,
                            job_description=job_data.get("description") or "",
                            model=scoring_model,
                        )
```

- [ ] **Step 2: Update `api/app/routers/resumes.py` — `_run_tailoring` background task**

In `_run_tailoring` (around line 196), at the top of the function body add a DB fetch for the tailoring model. Add after the existing imports inside the function:

```python
async def _run_tailoring(
    task_id: str,
    resume_id: str,
    resume_text: str,
    resume_name: str,
    job_id: str,
    job_description: str,
    job_title: str,
    company: str,
    upload_dir: str,
):
    from app.services.llm import tailor_resume as llm_tailor
    from app.database import AsyncSessionLocal
    from app.models.settings import AppSettings
    from sqlalchemy import select
    import uuid

    _tailor_tasks[task_id]["status"] = "processing"
    try:
        async with AsyncSessionLocal() as db:
            db_settings_result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
            db_settings = db_settings_result.scalar_one_or_none()
            tailoring_model = db_settings.ollama_model if db_settings else None

        tailored_text = await llm_tailor(resume_text, job_description, job_title, company, model=tailoring_model)
```

- [ ] **Step 3: Run the full test suite to confirm nothing is broken**

```bash
cd api && pytest tests/ -v
```

Expected: all 5 tests pass.

- [ ] **Step 4: Commit**

```bash
git add api/app/services/scraper.py api/app/routers/resumes.py
git commit -m "feat: pass DB model settings to llm callers in scraper and resume router"
```

---

### Task 7: Frontend — model dropdowns in Settings page

**Files:**
- Modify: `web/src/lib/types.ts`
- Modify: `web/src/app/dashboard/settings/page.tsx`

- [ ] **Step 1: Update `AppSettings` interface in `web/src/lib/types.ts`**

Replace the `AppSettings` interface (lines 76–80):

```typescript
export interface AppSettings {
  discord_webhook: string | null;
  score_threshold: number;
  scrape_interval: number;
  ollama_model: string | null;
  ollama_scoring_model: string | null;
}
```

- [ ] **Step 2: Add model dropdowns to `web/src/app/dashboard/settings/page.tsx`**

After the `Scrape Interval` field block (after its closing `</div>` around line 123), add the two model selectors before the Save button:

```tsx
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Tailoring Model
              </label>
              <select
                value={settings.ollama_model || "llama3.1:8b"}
                onChange={(e) => setSettings({ ...settings, ollama_model: e.target.value })}
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="llama3.2:3b">llama3.2:3b — fast, low RAM</option>
                <option value="llama3.1:8b">llama3.1:8b — balanced</option>
                <option value="llama3.3:70b">llama3.3:70b — high quality</option>
              </select>
              <p className="text-xs text-slate-400 mt-1">Used for resume tailoring</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">
                Scoring Model
              </label>
              <select
                value={settings.ollama_scoring_model || "llama3.2:3b"}
                onChange={(e) => setSettings({ ...settings, ollama_scoring_model: e.target.value })}
                className="w-full text-sm border border-slate-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="llama3.2:3b">llama3.2:3b — fast, low RAM</option>
                <option value="llama3.1:8b">llama3.1:8b — balanced</option>
                <option value="llama3.3:70b">llama3.3:70b — high quality</option>
              </select>
              <p className="text-xs text-slate-400 mt-1">Used for job scoring and resume analysis</p>
            </div>
```

- [ ] **Step 3: Start the dev server and verify**

```bash
cd web && npm run dev
```

Navigate to `http://localhost:3000/dashboard/settings`. Verify:
- Two new dropdowns appear: "Tailoring Model" and "Scoring Model"
- Selecting a model and clicking Save updates the value (check Network tab — PATCH `/api/settings` should include `ollama_model` in the body)
- Refreshing the page restores the saved selection

- [ ] **Step 4: Commit**

```bash
git add web/src/lib/types.ts web/src/app/dashboard/settings/page.tsx
git commit -m "feat: add model selection dropdowns to settings UI"
```

---

## Phase 2: Deployment

### Task 8: Remove Ollama from Docker Compose

**Files:**
- Modify: `docker-compose.yml`
- Modify: `docker-compose.override.yml`

- [ ] **Step 1: Remove the `ollama` service from `docker-compose.yml`**

Delete the entire `ollama:` block (lines 19–35):

```yaml
  ollama:
    build: ./ollama
    restart: unless-stopped
    volumes:
      - ollama_models:/root/.ollama
    networks:
      - ats_net
    deploy:
      resources:
        limits:
          memory: 6g
    healthcheck:
      test: ["CMD-SHELL", "curl -sf http://localhost:11434/api/tags || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 10
      start_period: 300s
```

- [ ] **Step 2: Remove `ollama` from the `api` service's `depends_on` in `docker-compose.yml`**

The `api` depends_on block currently reads:

```yaml
    depends_on:
      db:
        condition: service_healthy
      ollama:
        condition: service_healthy
```

Change it to:

```yaml
    depends_on:
      db:
        condition: service_healthy
```

- [ ] **Step 3: Remove `ollama_models` from the `volumes` section in `docker-compose.yml`**

The volumes section currently reads:

```yaml
volumes:
  postgres_data:
  ollama_models:
  uploads:
  caddy_data:
  caddy_config:
```

Change it to:

```yaml
volumes:
  postgres_data:
  uploads:
  caddy_data:
  caddy_config:
```

- [ ] **Step 4: Remove the `ollama` block from `docker-compose.override.yml`**

Delete this block from the override file:

```yaml
  ollama:
    ports:
      - "11434:11434"
```

- [ ] **Step 5: Test locally — start without ollama service**

```bash
docker compose up db api web bot -d --build
```

Check that API starts healthy:

```bash
curl http://localhost:8000/api/settings/health
```

Expected: `{"db":"ok","ollama":"error: ...","discord":"..."}` — ollama shows error (expected, it's on your local machine), but db is ok and the API is up.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml docker-compose.override.yml
git commit -m "feat: remove ollama container — Ollama now served from local machine via Tailscale"
```

---

### Task 9: Provision AWS EC2 + Elastic IP

This task is manual AWS console steps — no code.

- [ ] **Step 1: Create EC2 instance**

In the AWS Console → EC2 → Launch Instance:
- Name: `ats-system`
- AMI: Ubuntu Server 24.04 LTS (free tier eligible)
- Instance type: `t2.micro` (free tier eligible)
- Key pair: create new, name it `ats-key`, download the `.pem` file
- Network settings: create new security group named `ats-sg` with these inbound rules:
  - SSH (port 22) — source: My IP
  - HTTP (port 80) — source: Anywhere (0.0.0.0/0)
  - HTTPS (port 443) — source: Anywhere (0.0.0.0/0)
- Storage: 30 GB gp3 (free tier gives 30GB)
- Click Launch Instance

- [ ] **Step 2: Allocate and associate an Elastic IP**

EC2 → Elastic IPs → Allocate Elastic IP address → Allocate.
Then Actions → Associate Elastic IP → select your `ats-system` instance → Associate.

Note the Elastic IP address — you'll use it as the DNS target.

- [ ] **Step 3: Point your domain's A record at the Elastic IP**

In your DNS provider, create:
- Type: A
- Name: `ats` (or `@` for root)
- Value: `<your-elastic-ip>`
- TTL: 300

Wait 5–10 minutes for DNS to propagate before proceeding with Caddy setup.

- [ ] **Step 4: SSH into the instance and install Docker**

```bash
chmod 400 ~/Downloads/ats-key.pem
ssh -i ~/Downloads/ats-key.pem ubuntu@<your-elastic-ip>

# On the server:
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker ubuntu
newgrp docker
docker --version
```

Expected: `Docker version 27.x.x`

- [ ] **Step 5: Clone the repo**

```bash
git clone https://github.com/youruser/ATS-Discord-System.git /opt/ats
cd /opt/ats
```

---

### Task 10: Install Tailscale on EC2 and local machine

- [ ] **Step 1: Install Tailscale on the EC2 instance**

On the EC2 server (still SSH'd in):

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

You'll get a URL — open it in your browser to authenticate. Once authenticated:

```bash
tailscale ip -4
```

Note this IP (e.g., `100.64.x.x`) — this is your EC2's Tailscale IP.

- [ ] **Step 2: Install Tailscale on your local machine (if not already installed)**

Download from https://tailscale.com/download and sign in with the same Tailscale account.

- [ ] **Step 3: Find your local machine's Tailscale IP**

On your local machine:

```bash
tailscale ip -4
```

Note this IP (e.g., `100.64.y.y`) — this is what the EC2 API will use to reach Ollama.

- [ ] **Step 4: Verify EC2 can reach Ollama on your local machine**

Make sure Ollama is running locally (`ollama serve` or the Ollama app), then from the EC2 server:

```bash
curl http://100.64.y.y:11434/api/tags
```

Expected: JSON response listing your local Ollama models.

If this fails, check that your local machine's Tailscale is connected and that Ollama is running.

---

### Task 11: Configure .env and deploy on EC2

- [ ] **Step 1: Generate credentials on the EC2 server**

```bash
# JWT secret
openssl rand -hex 32

# Bcrypt hash for your password (replace 'yourpassword')
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```

Note both outputs.

- [ ] **Step 2: Create `.env` on the EC2 server**

```bash
cd /opt/ats
cp .env.example .env
nano .env
```

Fill in every value. Key fields that differ from local dev:

```bash
# Point to your local machine's Tailscale IP
OLLAMA_BASE_URL=http://100.64.y.y:11434

# Your domain
NEXT_PUBLIC_API_URL=https://ats.yourdomain.com/api
DOMAIN=ats.yourdomain.com
ACME_EMAIL=your@email.com

# Credentials generated above
JWT_SECRET=<openssl output>
AUTH_EMAIL=your@email.com
AUTH_PASSWORD_HASH=<bcrypt output>

# PostgreSQL (choose a strong password)
POSTGRES_PASSWORD=choose_a_strong_password
DATABASE_URL=postgresql+asyncpg://ats:choose_a_strong_password@db:5432/ats
```

- [ ] **Step 3: Start the stack**

```bash
cd /opt/ats
docker compose --profile production up -d --build
```

Watch startup logs:

```bash
docker compose logs api -f
```

Expected: API logs show `Application startup complete` — no ollama healthcheck blocking it.

- [ ] **Step 4: Run migrations**

```bash
docker compose exec api alembic upgrade head
```

Expected output ends with: `Running upgrade 003 -> 004, Add ollama_model and ollama_scoring_model to app_settings`

- [ ] **Step 5: Verify health**

```bash
curl https://ats.yourdomain.com/api/settings/health
```

Expected:
```json
{"db": "ok", "ollama": "ok", "discord": "configured"}
```

If `ollama` shows error, re-check that Ollama is running locally and Tailscale is connected on both machines.

---

### Task 12: Verify end-to-end functionality

- [ ] **Step 1: Log in to the dashboard**

Open `https://ats.yourdomain.com` in your browser. Log in with your credentials.

- [ ] **Step 2: Check Settings page shows model dropdowns**

Navigate to Settings. Verify the Tailoring Model and Scoring Model dropdowns appear. Change one and save — verify it persists after page refresh.

- [ ] **Step 3: Trigger a manual scrape**

On the Job Feed page, click "Scrape Now". Watch for new jobs to appear with relevance scores. Scores confirm Ollama on your local machine is being reached.

- [ ] **Step 4: Final commit (update .env.example if needed)**

If you added any new env var keys during setup that aren't in `.env.example`, add them with placeholder values:

```bash
git add .env.example  # only if changed
git commit -m "chore: update .env.example with Tailscale OLLAMA_BASE_URL note"
```

---

## Resume-Worthy Bullet Points

Once deployed, you can write:

- "Deployed containerized application stack (FastAPI, Next.js, PostgreSQL) on AWS EC2 with Caddy reverse proxy and automatic HTTPS"
- "Configured Tailscale mesh VPN to securely connect cloud infrastructure to local Ollama LLM inference"
- "Built DB-backed model selection feature allowing runtime model switching without container restarts"
