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
    """Create all tables. Import models so they register on Base.metadata."""
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
