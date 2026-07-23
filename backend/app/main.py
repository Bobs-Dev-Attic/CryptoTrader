"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import accounts, agents, auth, internal, market, portfolio, push, watchlist
from .config import settings
from .database import init_db
from .observability import init_observability
from .scheduler import shutdown_scheduler, start_scheduler

logging.basicConfig(level=logging.INFO)


logger = logging.getLogger("cryptotrader.startup")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Configure structured logging + error tracking first so anything below is
    # captured. No-op (beyond logging setup) unless SENTRY_DSN is set.
    init_observability()

    # Refuse to serve with insecure secrets in production; warn loudly elsewhere.
    problems = settings.security_warnings()
    for p in problems:
        logger.warning("SECURITY: %s", p)
    if settings.is_production and problems:
        raise RuntimeError(
            "Refusing to start in production with insecure configuration: "
            + " | ".join(problems)
        )
    # Non-fatal config-hygiene issues (DEBUG on, wildcard CORS, …).
    for p in settings.config_warnings():
        logger.warning("CONFIG: %s", p)

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
    # Auth is Bearer-token in the Authorization header, not cookies, so we don't
    # enable credentialed CORS. Keeping this False also keeps a wildcard origin
    # spec-valid (browsers reject `Allow-Origin: *` together with credentials).
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(accounts.router)
app.include_router(agents.router)
app.include_router(market.router)
app.include_router(internal.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)
app.include_router(push.router)


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
