"""A small DB-backed fixed-window rate limiter.

Serverless has no shared in-memory store and we don't run Redis, so limits are
tracked in Postgres (shared across function instances). Counting is approximate
under heavy concurrency — that's fine for a safety valve. The limiter is
**fail-open**: if the backing store errors, requests are allowed rather than the
endpoint going down.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from .config import settings
from .models import RateLimit

logger = logging.getLogger("cryptotrader.ratelimit")


def client_ip(request: Request) -> str:
    """Best-effort client IP, honoring the proxy's X-Forwarded-For."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(db: Session, key: str, limit: int, window_seconds: int) -> bool:
    """Return True if this hit is within the limit for the current window."""
    if not settings.rate_limit_enabled:
        return True
    now = datetime.now(timezone.utc)
    window_start = int(now.timestamp()) // window_seconds * window_seconds
    bucket = f"{key}:{window_start}"
    try:
        row = db.get(RateLimit, bucket)
        if row is None:
            db.add(
                RateLimit(
                    bucket=bucket,
                    count=1,
                    expires_at=now + timedelta(seconds=window_seconds * 2),
                )
            )
            # Opportunistic cleanup of expired rows (once per new window).
            db.query(RateLimit).filter(RateLimit.expires_at < now).delete()
            db.commit()
            return True
        row.count += 1
        db.commit()
        return row.count <= limit
    except Exception:
        logger.warning("rate limiter store error; allowing request", exc_info=True)
        db.rollback()
        return True  # fail open


def enforce(request: Request, db: Session, name: str, limit: int, window_seconds: int) -> None:
    """Raise 429 if the per-IP limit for ``name`` is exceeded."""
    key = f"{name}:{client_ip(request)}"
    if not check_rate_limit(db, key, limit, window_seconds):
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Try again in up to {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )
