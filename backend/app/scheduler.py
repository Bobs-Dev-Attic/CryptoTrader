"""Background scheduler that periodically evaluates running agents.

A single lightweight "tick" job scans for agents whose ``status == RUNNING`` and
whose ``interval_seconds`` has elapsed since ``last_run_at``, then evaluates each
one. This avoids one APScheduler job per agent and keeps scheduling in the DB
(so it survives restarts).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .database import SessionLocal
from .enums import AgentStatus
from .models import Agent

logger = logging.getLogger("cryptotrader.scheduler")

_scheduler: BackgroundScheduler | None = None


def _tick() -> None:
    """Evaluate every running agent that is due."""
    from .agents.runner import run_agent_once  # avoid import cycle

    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        agents = db.query(Agent).filter(Agent.status == AgentStatus.RUNNING).all()
        for agent in agents:
            due = agent.last_run_at is None or (
                _aware(agent.last_run_at) + timedelta(seconds=agent.interval_seconds)
                <= now
            )
            if not due:
                continue
            try:
                run_agent_once(db, agent)
                logger.info("Evaluated agent %s (%s)", agent.id, agent.name)
            except Exception:
                logger.exception("Agent %s tick failed", agent.id)
                db.rollback()
    finally:
        db.close()


def _aware(dt: datetime) -> datetime:
    """Treat naive DB timestamps as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def start_scheduler() -> None:
    global _scheduler
    if not settings.scheduler_enabled or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        _tick,
        "interval",
        seconds=settings.min_agent_interval_seconds,
        id="agent_tick",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Agent scheduler started (tick=%ss)", settings.min_agent_interval_seconds)


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
