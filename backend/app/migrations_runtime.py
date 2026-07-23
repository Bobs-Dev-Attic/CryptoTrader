"""Programmatic Alembic runner used at application startup.

Serverless has no separate ``alembic upgrade`` deploy step, so the schema must
self-apply when the app boots — exactly like the old ``create_all`` +
``_ensure_columns`` did, but now with real migration history and a down-path.

Adoption on an existing database (the production DB was built by the pre-Alembic
path and has no ``alembic_version`` table) is handled by *stamping* the baseline
rather than re-running it: we first backfill any columns the legacy path was
responsible for, then record that the DB is at the baseline revision, then apply
anything newer. A brand-new database simply upgrades from zero.
"""
from __future__ import annotations

import logging
import os

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect

from .database import engine

logger = logging.getLogger("cryptotrader.migrations")

BASELINE_REVISION = "0001_baseline"
# A table that only ever existed under the old create_all path; its presence
# without an alembic_version table means "legacy DB, adopt in place".
_SENTINEL_TABLE = "users"

# backend/ (contains alembic.ini and the migrations/ package), resolved
# absolutely so it works regardless of the process's cwd (Vercel, tests, CLI).
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _config() -> Config:
    cfg = Config(os.path.join(_BACKEND_DIR, "alembic.ini"))
    # Absolute script location so the versions/ package is always found.
    cfg.set_main_option("script_location", os.path.join(_BACKEND_DIR, "migrations"))
    return cfg


def _current_revision(conn) -> str | None:
    return MigrationContext.configure(conn).get_current_revision()


def run_migrations() -> None:
    """Bring the database up to head, adopting a legacy DB in place if needed."""
    cfg = _config()
    with engine.connect() as conn:
        current = _current_revision(conn)
        has_legacy_schema = current is None and inspect(conn).has_table(_SENTINEL_TABLE)

    if has_legacy_schema:
        # DB predates Alembic. Backfill any columns the old path owned, then
        # adopt the baseline without re-creating existing tables.
        logger.info("Adopting existing pre-Alembic database: stamping %s", BASELINE_REVISION)
        from .database import _ensure_columns

        _ensure_columns()
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")
