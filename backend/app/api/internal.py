"""Internal endpoints for external schedulers (Vercel Cron / Supabase pg_cron).

When the app runs serverless, in-process APScheduler can't tick, so an external
scheduler calls ``POST /api/internal/tick`` on an interval. The call must present
the shared ``internal_cron_secret`` to be honored.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException
from sqlalchemy.orm import Session

from ..agents.runner import run_agent_once
from ..config import settings
from ..database import SessionLocal
from ..enums import AgentStatus
from ..models import Agent
from ..observability import audit, capture_exception

router = APIRouter(prefix="/api/internal", tags=["internal"])


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _authorized(authorization: str, x_cron_secret: str) -> bool:
    secret = settings.internal_cron_secret
    if not secret:
        return False
    # Vercel Cron sends `Authorization: Bearer <CRON_SECRET>`.
    if authorization.startswith("Bearer ") and authorization[7:] == secret:
        return True
    # Supabase pg_cron / manual callers may use a custom header instead.
    return x_cron_secret == secret


def _run_tick() -> dict:
    now = datetime.now(timezone.utc)
    evaluated: list[int] = []
    errors = 0
    watches_checked = 0
    pruned = {"snapshots": 0, "signals": 0}
    db: Session = SessionLocal()
    try:
        agents = db.query(Agent).filter(Agent.status == AgentStatus.RUNNING).all()
        for agent in agents:
            due = agent.last_run_at is None or (
                _aware(agent.last_run_at) + timedelta(seconds=agent.interval_seconds) <= now
            )
            if not due:
                continue
            try:
                # respect_interval re-checks due-ness under the per-agent lock,
                # so overlapping ticks can't double-run (returns None if skipped).
                sig = run_agent_once(db, agent, respect_interval=True)
                if sig is not None:
                    evaluated.append(agent.id)
            except Exception as exc:
                db.rollback()
                errors += 1
                # Surface the failure instead of swallowing it silently.
                capture_exception(exc, where="tick.agent", agent_id=agent.id)
        # Evaluate volatility alert watches (never lets a failure break the tick).
        try:
            from .watchlist import evaluate_watches

            watches_checked = evaluate_watches(db)
        except Exception as exc:
            db.rollback()
            errors += 1
            capture_exception(exc, where="tick.watches")
        # Prune aged snapshots/signals so the tables stay bounded (best-effort).
        try:
            from ..retention import prune_old_rows

            pruned = prune_old_rows(db, now)
        except Exception as exc:
            db.rollback()
            errors += 1
            capture_exception(exc, where="tick.retention")
    finally:
        db.close()
    if errors:
        audit("tick.failures", count=errors, evaluated=len(evaluated))
    return {
        "evaluated": evaluated,
        "count": len(evaluated),
        "errors": errors,
        "watches_checked": watches_checked,
        "pruned": pruned,
    }


@router.api_route("/tick", methods=["GET", "POST"])
def tick(
    authorization: str = Header(default=""),
    x_cron_secret: str = Header(default=""),
) -> dict:
    """Evaluate every running agent that is due. Accepts GET (Vercel Cron) or POST."""
    if not _authorized(authorization, x_cron_secret):
        raise HTTPException(status_code=401, detail="Invalid or missing cron secret")
    return _run_tick()
