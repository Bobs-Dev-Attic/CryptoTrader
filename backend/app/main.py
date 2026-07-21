"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import accounts, agents, auth, internal, market
from .config import settings
from .database import init_db
from .scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)


logger = logging.getLogger("cryptotrader.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist, but NEVER let DB setup crash app startup. In
    # serverless the DB may be unreachable (e.g. DATABASE_URL not yet set), and
    # the managed schema is created via migrations anyway — so non-DB endpoints
    # (/health, /api/market/*) must still come up. DB-backed endpoints will
    # surface their own errors until the database is configured.
    try:
        init_db()
    except Exception:
        logger.exception(
            "init_db() failed at startup; continuing. DB-backed endpoints will "
            "error until DATABASE_URL points at a reachable database."
        )
    # In serverless there is no long-lived process for a background thread, so
    # the in-process scheduler is skipped; an external cron hits /api/internal/tick.
    if not settings.is_serverless:
        start_scheduler()
    yield
    if not settings.is_serverless:
        shutdown_scheduler()


app = FastAPI(
    title=f"{settings.app_name} API",
    version="0.1.0",
    description="Configure and run cross-exchange crypto trading agents.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(agents.router)
app.include_router(market.router)
app.include_router(internal.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "app": settings.app_name, "environment": settings.environment}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "health": "/health",
    }
