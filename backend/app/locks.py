"""Cross-instance locking for agent evaluation.

Uses PostgreSQL **transaction-level** advisory locks (`pg_try_advisory_xact_lock`),
which are held until the current transaction ends and auto-release on
commit/rollback. This is the correct choice behind a transaction-mode connection
pooler (e.g. Supabase's pooler), where *session*-level advisory locks are
unreliable because statements may land on different backends.

On SQLite (tests / local single-process) there is nothing to coordinate, so the
lock is a no-op that always succeeds.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

# Arbitrary namespace so agent ids can't collide with other advisory-lock users.
_AGENT_LOCK_NAMESPACE = 4747


def try_agent_lock(db: Session, agent_id: int) -> bool:
    """Try to acquire the per-agent transaction lock. Non-blocking.

    Returns True if acquired (or non-Postgres). The lock releases automatically
    when the surrounding transaction commits or rolls back.
    """
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return True
    acquired = db.execute(
        text("SELECT pg_try_advisory_xact_lock(:ns, :key)"),
        {"ns": _AGENT_LOCK_NAMESPACE, "key": int(agent_id)},
    ).scalar()
    return bool(acquired)
