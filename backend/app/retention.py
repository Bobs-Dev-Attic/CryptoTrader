"""Age-based pruning of high-volume, derivable rows.

``equity_snapshots`` and ``signals`` are written on every agent tick and would
otherwise grow without bound. They're either fully derivable (the equity curve
is a convenience series) or low-value once old (signal rationales are a
transparency log), so we drop rows past a configurable age.

Trades are deliberately **never** pruned here: they are the financial record
that lifetime P&L and win/loss stats are computed from, so aging them out would
silently corrupt those numbers.

Deletes are batched (``id IN (SELECT ... LIMIT n)``) so a single call does a
bounded amount of work regardless of backlog, and the query shape is portable
across Postgres (prod) and SQLite (tests/dev).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from .config import settings
from .models import EquitySnapshot, Signal


def _prune_older_than(db: Session, model, cutoff: datetime, batch: int) -> int:
    """Delete up to ``batch`` rows of ``model`` created before ``cutoff``.

    Returns the number of rows removed. Uses a subquery of primary keys so the
    row cap works identically on Postgres and SQLite (neither reliably supports
    ``DELETE ... LIMIT`` directly).
    """
    ids = [
        row[0]
        for row in db.query(model.id)
        .filter(model.created_at < cutoff)
        .order_by(model.created_at.asc())
        .limit(batch)
        .all()
    ]
    if not ids:
        return 0
    deleted = (
        db.query(model)
        .filter(model.id.in_(ids))
        .delete(synchronize_session=False)
    )
    return int(deleted)


def prune_old_rows(db: Session, now: datetime | None = None) -> dict:
    """Prune aged equity snapshots and signals. Commits on success.

    Safe to call every tick: when the tables are already within their retention
    window each query is a cheap indexed range scan that matches nothing. A
    retention of 0 days disables that table. Returns a per-table delete count.
    """
    result = {"snapshots": 0, "signals": 0}
    if not settings.retention_enabled:
        return result
    now = now or datetime.now(timezone.utc)
    batch = max(int(settings.retention_batch), 1)

    def cutoff(days: int) -> datetime:
        # created_at is stored naive-UTC (plain DateTime column); compare against
        # a naive cutoff so the range scan is unambiguous on Postgres and SQLite.
        return (now - timedelta(days=days)).replace(tzinfo=None)

    if settings.snapshot_retention_days > 0:
        result["snapshots"] = _prune_older_than(
            db, EquitySnapshot, cutoff(settings.snapshot_retention_days), batch
        )
    if settings.signal_retention_days > 0:
        result["signals"] = _prune_older_than(
            db, Signal, cutoff(settings.signal_retention_days), batch
        )

    if result["snapshots"] or result["signals"]:
        db.commit()
    return result
