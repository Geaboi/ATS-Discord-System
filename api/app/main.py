import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base
from app.scheduler import scheduler, setup_scheduler

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting ATS API...")

    # Ensure upload directory exists
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(f"{settings.upload_dir}/master", exist_ok=True)
    os.makedirs(f"{settings.upload_dir}/tailored", exist_ok=True)

    # Create DB tables (Alembic handles migrations in production;
    # this ensures tables exist in dev without running alembic manually)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start APScheduler
    setup_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
    await engine.dispose()
    logger.info("Database connections closed")


app = FastAPI(
    title="ATS API",
    version="1.0.0",
    description="Job Application Tracking System API",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS — allows the Next.js frontend to call the API
_allowed_origins = [
    "http://localhost:3000",
    "http://web:3000",
]
# Add production domain if DOMAIN env var is set (set in .env for production)
_domain = os.environ.get("DOMAIN", "")
if _domain:
    _allowed_origins.append(f"https://{_domain}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all routers under /api prefix
from app.routers import auth, jobs, applications, resumes, settings as settings_router  # noqa: E402

app.include_router(auth.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(resumes.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")


@app.get("/api")
async def root():
    return {"service": "ATS API", "status": "ok"}
