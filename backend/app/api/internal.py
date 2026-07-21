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
                run_agent_once(db, agent)
                evaluated.append(agent.id)
            except Exception:
                db.rollback()
    finally:
        db.close()
    return {"evaluated": evaluated, "count": len(evaluated)}


@router.api_route("/tick", methods=["GET", "POST"])
def tick(
    authorization: str = Header(default=""),
    x_cron_secret: str = Header(default=""),
) -> dict:
    """Evaluate every running agent that is due. Accepts GET (Vercel Cron) or POST."""
    if not _authorized(authorization, x_cron_secret):
        raise HTTPException(status_code=401, detail="Invalid or missing cron secret")
    return _run_tick()
