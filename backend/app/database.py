"""Database engine, session, and declarative base."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from .config import settings

# check_same_thread is only needed for SQLite when used across threads
# (the APScheduler background jobs run in a separate thread pool).
connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

# In serverless, each invocation is short-lived and there may be many concurrent
# function instances; a per-instance connection pool would exhaust Postgres.
# Use NullPool and let Supabase's connection pooler (pgbouncer) manage pooling.
engine_kwargs: dict = {"connect_args": connect_args, "pool_pre_ping": True}
if settings.is_serverless and not settings.database_url.startswith("sqlite"):
    engine_kwargs["poolclass"] = NullPool

engine = create_engine(settings.database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Bring the schema up to date via Alembic (self-applies on startup).

    Imports models first so they register on ``Base.metadata`` (the baseline
    migration and the adoption backfill both read from it).
    """
    from . import models  # noqa: F401
    from .migrations_runtime import run_migrations

    run_migrations()


# --- Legacy column backfill (pre-Alembic) --------------------------------
# Retained only for *adopting* a database that predates Alembic: on first boot
# under the new system we run this once to guarantee every column exists, then
# stamp the baseline (see migrations_runtime.run_migrations). Do NOT add new
# entries here — schema changes now go through Alembic migrations.
#
# ``create_all`` only creates missing *tables*, never missing *columns* on an
# existing one. (table, column, postgres_ddl, sqlite_ddl)
_ADDED_COLUMNS = [
    (
        "users", "token_version",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0",
    ),
    (
        "agents", "risk_config",
        "ALTER TABLE agents ADD COLUMN IF NOT EXISTS risk_config JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE agents ADD COLUMN risk_config JSON DEFAULT '{}'",
    ),
    (
        "positions", "high_water",
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS high_water DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE positions ADD COLUMN high_water FLOAT DEFAULT 0",
    ),
]


def _ensure_columns() -> None:
    """Idempotently add newly-introduced columns to existing tables.

    Each statement runs in its own transaction so one benign failure (e.g. the
    column already exists on SQLite, which lacks ``ADD COLUMN IF NOT EXISTS``)
    never aborts the others. Safe to run on every startup.
    """
    from sqlalchemy import text

    is_pg = engine.dialect.name == "postgresql"
    for _table, _col, pg_ddl, sqlite_ddl in _ADDED_COLUMNS:
        ddl = pg_ddl if is_pg else sqlite_ddl
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
        except Exception:
            # Column already exists or table not present yet — benign.
            pass
