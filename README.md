# ATS Discord System

A personal job application tracking system for new grad CS roles. Scrapes job boards automatically, scores relevance with a self-hosted LLM (Ollama), tailors your resume on demand, tracks your entire pipeline, and sends Discord alerts — all from a private web dashboard.

---

## Features

- **Job Feed** — scrapes Adzuna, SimplifyJobs/New-Grad-Positions, LinkedIn RSS, and Indeed RSS on a schedule
- **AI Scoring** — every job is scored 0–100% for relevance using Ollama (llama3.1:8b) running locally on your server
- **Resume Tailoring** — upload your master resume (PDF/DOCX) and tailor it to any job description with one click; Ollama rewrites it to match keywords without fabricating experience
- **Pipeline Kanban** — track applications through 8 stages: Interested → Applied → Phone Screen → Technical → Onsite → Offer → Rejected / Withdrawn
- **Discord Alerts** — new high-relevance jobs trigger a rich embed in your Discord server automatically
- **Private** — single-user JWT auth; nothing is public

## Architecture Overview

```
Browser
  │
  ▼
Caddy (HTTPS, reverse proxy)
  ├── /api/*  ──► FastAPI (Python)
  │                  ├── PostgreSQL (jobs, applications, resumes)
  │                  ├── Ollama (llama3.1:8b) — scoring & tailoring
  │                  ├── APScheduler — scrapes every N minutes
  │                  └── Discord webhook notifier
  └── /*  ─────► Next.js 14 (dashboard UI)

Discord Bot (separate container)
  └── Polls DB every 5 min → posts embeds to Discord webhook
```

**Tech stack:**

| Layer | Technology |
|---|---|
| Backend API | FastAPI + async SQLAlchemy |
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui |
| LLM | Ollama — llama3.1:8b (self-hosted, zero API cost) |
| Database | PostgreSQL 16 |
| Scheduler | APScheduler (runs inside FastAPI process) |
| Discord | Webhook POST only (no bot token/gateway) |
| Reverse proxy | Caddy (auto HTTPS via Let's Encrypt) |
| Containers | Docker Compose |

---

## Prerequisites

- [Docker Desktop](https://docs.docker.com/get-docker/) (includes Docker Compose)
- A Discord server where you can create a webhook
- (Optional) A free [Adzuna API account](https://developer.adzuna.com) for structured job search

---

## Local Development

### 1. Clone and configure

```bash
git clone https://github.com/youruser/ATS-Discord-System.git
cd ATS-Discord-System

cp .env.example .env
```

Open `.env` and fill in:

| Variable | How to get it |
|---|---|
| `POSTGRES_PASSWORD` | Any strong password |
| `DATABASE_URL` | Replace `changeme_strong_password` with the same password |
| `JWT_SECRET` | `openssl rand -hex 32` |
| `AUTH_EMAIL` | Your email address |
| `AUTH_PASSWORD_HASH` | See command below |
| `DISCORD_WEBHOOK_URL` | Discord server → channel settings → Integrations → Webhooks |
| `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` | [developer.adzuna.com](https://developer.adzuna.com) (free) |

**Generate your password hash:**
```bash
python3 -c "import bcrypt; print(bcrypt.hashpw(b'yourpassword', bcrypt.gensalt()).decode())"
```
Paste the output (starts with `$2b$12$...`) as `AUTH_PASSWORD_HASH` in `.env`.

### 2. Start the services

```bash
# Start database and Ollama (runs in background)
docker compose up db ollama -d

# First-time Ollama setup: wait for the model to download (~4.7GB)
docker compose logs ollama -f
# Wait until you see: "Model 'llama3.1:8b' pulled successfully"
# Press Ctrl+C when done watching logs
```

### 3. Run the backend

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Run database migrations
DATABASE_URL="postgresql+asyncpg://ats:yourpassword@localhost:5432/ats" \
  alembic upgrade head

# Start the API
DATABASE_URL="postgresql+asyncpg://ats:yourpassword@localhost:5432/ats" \
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API is now at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/api/docs`

### 4. Run the frontend

Open a new terminal:

```bash
cd web
npm install
npm run dev
```

The dashboard is now at `http://localhost:3000`.

### 5. Log in

Go to `http://localhost:3000`, enter the email and password you used when generating the bcrypt hash.

---

## Running Everything with Docker (recommended for testing)

```bash
# Build and start all services (DB, Ollama, API, frontend, Discord bot)
# Caddy is disabled in local dev (override file handles this automatically)
docker compose up --build
```

Services exposed locally:
- `http://localhost:3000` — dashboard
- `http://localhost:8000` — API + docs (`/api/docs`)
- `http://localhost:11434` — Ollama (direct access)
- `localhost:5432` — PostgreSQL

> **Note:** On first run, Ollama downloads `llama3.1:8b` (~4.7GB). This takes several minutes. The API will wait for Ollama to be healthy before starting.

---

## Project Structure

```
ATS-Discord-System/
├── docker-compose.yml           # Production service definitions
├── docker-compose.override.yml  # Local dev overrides (auto-applied)
├── .env.example                 # Template — copy to .env
├── Caddyfile                    # Reverse proxy config (production)
│
├── api/                         # FastAPI backend
│   ├── app/
│   │   ├── main.py              # App factory, lifespan, router mounts
│   │   ├── config.py            # Settings (reads .env via pydantic-settings)
│   │   ├── database.py          # Async SQLAlchemy engine + session
│   │   ├── auth.py              # JWT creation/verification, bcrypt
│   │   ├── scheduler.py         # APScheduler — registers scrape job
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── job.py           # Job, ScrapeRun
│   │   │   ├── application.py   # Application, ApplicationNote
│   │   │   ├── resume.py        # Resume (master + tailored)
│   │   │   └── settings.py      # AppSettings (single-row config table)
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   ├── routers/             # FastAPI route handlers
│   │   │   ├── auth.py          # POST /api/auth/login|logout, GET /me
│   │   │   ├── jobs.py          # GET/PATCH /api/jobs, POST /api/jobs/scrape
│   │   │   ├── applications.py  # CRUD /api/applications + notes
│   │   │   ├── resumes.py       # Upload, download, tailor /api/resumes
│   │   │   └── settings.py      # GET/PATCH /api/settings, GET /health
│   │   └── services/
│   │       ├── llm.py           # Ollama client: score_job(), tailor_resume()
│   │       ├── scraper.py       # Orchestrates all scrapers, dedup, scoring
│   │       ├── resume.py        # PDF/DOCX text extraction
│   │       ├── discord_notifier.py  # POST embeds to Discord webhook
│   │       └── sources/
│   │           ├── adzuna.py    # Adzuna REST API
│   │           ├── simplify.py  # SimplifyJobs GitHub JSON
│   │           ├── linkedin_rss.py  # LinkedIn RSS feed
│   │           └── indeed_rss.py    # Indeed RSS feed
│   └── alembic/                 # Database migrations
│       └── versions/
│           └── 001_initial_schema.py
│
├── web/                         # Next.js 14 frontend
│   └── src/
│       ├── middleware.ts         # Redirect unauthenticated → /login
│       ├── lib/
│       │   ├── api.ts           # Typed fetch wrapper (all API calls)
│       │   ├── types.ts         # TypeScript interfaces (Job, Application, etc.)
│       │   └── utils.ts         # formatSalary, timeAgo, stage colors
│       └── app/
│           ├── login/           # Login page
│           └── dashboard/
│               ├── page.tsx     # Job Feed
│               ├── pipeline/    # Kanban board
│               ├── resumes/     # Resume upload + tailoring
│               └── settings/    # Config + health check
│
├── bot/
│   └── bot.py                   # Discord alert loop (polls DB → webhook)
│
└── ollama/
    └── entrypoint.sh            # Starts Ollama + pulls model on first boot
```

---

## API Reference

All endpoints are prefixed `/api`. All routes except `/api/auth/login` require an `access_token` cookie (set automatically on login).

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/login` | Login with email + password |
| `POST` | `/api/auth/logout` | Clear session cookie |
| `GET` | `/api/jobs` | Paginated job list (`?status=new&min_score=0.7&q=search`) |
| `GET` | `/api/jobs/{id}` | Single job detail |
| `PATCH` | `/api/jobs/{id}` | Update job status (bookmarked/dismissed) |
| `POST` | `/api/jobs/scrape` | Trigger manual scrape (background task) |
| `GET` | `/api/jobs/scrape/status` | Last scrape run info per source |
| `GET` | `/api/applications` | All applications (`?stage=applied`) |
| `POST` | `/api/applications` | Create application (`{job_id, stage}`) |
| `PATCH` | `/api/applications/{id}` | Update stage, notes, next action date |
| `DELETE` | `/api/applications/{id}` | Delete application |
| `POST` | `/api/resumes/upload` | Upload PDF or DOCX master resume |
| `POST` | `/api/resumes/{id}/tailor` | Tailor resume for a job (`{job_id}`) → `{task_id}` |
| `GET` | `/api/resumes/tailor/{task_id}` | Poll tailoring status → download URL when done |
| `GET` | `/api/resumes/{id}/download` | Download resume file |
| `GET` | `/api/settings` | Get config (webhook, threshold, interval) |
| `PATCH` | `/api/settings` | Update config |
| `GET` | `/api/settings/health` | System health: `{db, ollama, discord}` |

---

## Cloud Deployment (Hetzner VPS)

### Provision the server

1. Create a [Hetzner CX32](https://www.hetzner.com/cloud) (4 vCPU / 8GB RAM / ~€11/mo), Ubuntu 24.04
2. Add your SSH public key during setup
3. Point a domain's `A` record at the server IP (DNS needs to propagate before Caddy can get a TLS cert)

### Initial server setup

```bash
ssh root@<your-vps-ip>

# Install Docker
curl -fsSL https://get.docker.com | sh
apt install docker-compose-plugin -y

# Clone the repo
git clone https://github.com/youruser/ATS-Discord-System.git /opt/ats
cd /opt/ats

# Set up environment
cp .env.example .env
nano .env   # fill in all values; set DOMAIN=ats.yourdomain.com
```

### Deploy

```bash
cd /opt/ats
docker compose --profile production up -d --build
```

> Caddy requests an HTTPS certificate automatically. Ollama downloads the model on first boot (~5 min). Check progress with `docker compose logs ollama -f`.

### Run migrations after deploy

```bash
docker compose exec api alembic upgrade head
```

### Auto-deploy via GitHub Actions

Add these secrets to your GitHub repo (Settings → Secrets → Actions):
- `VPS_HOST` — your VPS IP address
- `VPS_USER` — `root` (or your deploy user)
- `VPS_SSH_KEY` — your private SSH key (`cat ~/.ssh/id_ed25519`)

Every push to `main` will SSH into the VPS and run `git pull + docker compose up -d --build`.

---

## Useful Commands

```bash
# View live logs
docker compose logs api -f
docker compose logs bot -f
docker compose logs ollama -f

# Trigger a manual scrape
curl -X POST http://localhost:8000/api/jobs/scrape \
  -H "Cookie: access_token=<your-token>"

# Check system health
curl http://localhost:8000/api/settings/health

# Open a database shell
docker compose exec db psql -U ats -d ats

# List jobs in DB
docker compose exec db psql -U ats -d ats -c "SELECT title, company, relevance_score FROM jobs ORDER BY scraped_at DESC LIMIT 10;"

# Restart a single service
docker compose restart api

# Switch Ollama model (e.g., smaller/faster)
docker compose exec ollama ollama pull llama3.2:3b
# Then update OLLAMA_MODEL in .env and restart: docker compose restart api bot

# Run DB migration manually
docker compose exec api alembic upgrade head
```

---

## Security Notes

- **`.env` is gitignored** — never commit it. It contains your credentials.
- **`.env.example` is committed** — it must only contain placeholder values.
- The dashboard is protected by JWT auth. The `access_token` cookie is `HttpOnly` + `Secure` + `SameSite=Strict`.
- Ollama runs on the internal Docker network only — it is not exposed to the internet.
- PostgreSQL is not exposed externally in production (no ports mapping in `docker-compose.yml` for `db`).
- Caddy enforces HTTPS with HSTS headers.

---

## Troubleshooting

**Ollama is slow / tailoring times out**

Increase `OLLAMA_TIMEOUT` in `.env` (default: 90s). On a CPU-only VPS, tailoring an 8B model takes 30–90 seconds. For faster responses, switch to `llama3.2:3b`.

**`alembic upgrade head` fails with "relation already exists"**

The tables were already created by FastAPI's `Base.metadata.create_all` on first boot. Run:
```bash
docker compose exec api alembic stamp head
```

**Login says "Invalid credentials"**

Regenerate your bcrypt hash and make sure there are no leading/trailing spaces in `AUTH_PASSWORD_HASH` in your `.env`.

**Discord alerts not firing**

Check `GET /api/settings/health` — the `discord` field shows `configured` or `not configured`. Make sure `DISCORD_WEBHOOK_URL` starts with `https://discord.com/api/webhooks/`.

**Jobs showing score of 50% for everything**

Ollama is likely still loading the model. Check `docker compose logs ollama`. Once the model is loaded, trigger a rescrape.
