# AWS Deployment + Model Selection Design

**Date:** 2026-04-20
**Status:** Approved

## Goal

Deploy the ATS Discord System to AWS free tier (EC2 t2.micro) with Ollama running on the user's local machine via Tailscale. Add a UI-configurable model selection feature so models can be switched without editing `.env` or restarting containers.

## Infrastructure

### AWS (free tier)

- **EC2 t2.micro** (1GB RAM, 1 vCPU) — runs db, api, web, bot, caddy via Docker Compose
- **Elastic IP** — free while instance is running; used as DNS target
- **Security group** — inbound: 80 (HTTP), 443 (HTTPS), 22 (SSH); all else blocked

### Local machine (Ollama)

- Ollama continues running locally as-is
- **Tailscale** installed on both EC2 and local machine
- `OLLAMA_BASE_URL=http://<tailscale-ip>:11434` in EC2 `.env`
- When local machine is offline, LLM features degrade gracefully (API returns 50% fallback score); rest of app stays up

### Migration path to home lab

1. Stop EC2 instance
2. `docker compose up` on home server
3. Update DNS A record to home server IP
4. Done — no other changes required

## Model Selection Feature

### Current behavior

Models are read from env vars at startup:
- `OLLAMA_MODEL` (default `llama3.1:8b`) — used by `tailor_resume()` only
- `OLLAMA_SCORING_MODEL` (default `llama3.2:3b`) — used by `score_job()` and `rate_resume()`

### New behavior

Models are stored in the `app_settings` DB table and editable from the Settings page UI. Env vars serve as defaults on first boot only.

**Model responsibilities (unchanged):**
- Tailoring model → resume tailoring only
- Scoring model → job scoring + resume rating/analysis

### Model options in UI

Dropdown with: `llama3.2:3b`, `llama3.1:8b`, `llama3.3:70b`, plus a free-text field for any custom Ollama model name.

## Changes Required

### Docker Compose

- Remove `ollama` service
- Remove `ollama` healthcheck dependency from `api` service

### Backend

| File | Change |
|---|---|
| `api/app/models/settings.py` | Add `ollama_model: str` and `ollama_scoring_model: str` columns |
| `api/app/services/llm.py` | Read model names from DB settings at request time; fall back to env var if DB value is null |
| `api/app/routers/settings.py` | Expose both model fields in GET/PATCH `/api/settings` |
| `api/app/schemas/settings.py` | Add fields to settings request/response schemas |
| `alembic/versions/` | New migration adding both columns to `app_settings` |

### Frontend

| File | Change |
|---|---|
| `web/src/app/dashboard/settings/page.tsx` | Add model dropdowns (tailoring model + scoring model) |

### Environment

- `OLLAMA_BASE_URL` on EC2 set to Tailscale IP of local machine instead of `http://ollama:11434`

## Out of Scope

- RDS, S3, or other AWS managed services
- CI/CD pipeline changes
- Changes to scraping, auth, kanban, or resume upload/download
