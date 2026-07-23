"""Alembic environment.

Wired to the application's own engine and metadata so migrations use the exact
same connection configuration (NullPool on serverless Postgres, SQLite connect
args in dev/tests) and the same source of truth for the schema. Runs online
only — we always execute migrations programmatically from app startup, never via
an offline SQL dump.
"""
from __future__ import annotations

from alembic import context

# Importing the app registers every model on Base.metadata.
from app.database import Base, engine
from app import models  # noqa: F401  (side-effect: populate Base.metadata)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Batch mode lets SQLite (dev/tests) emulate ALTER TABLE for future
            # column changes; a no-op on Postgres.
            render_as_batch=connection.dialect.name == "sqlite",
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


# We only ever run online (programmatically, against a live connection). Guard
# offline mode so `alembic … --sql` doesn't attempt a connection.
if not context.is_offline_mode():
    run_migrations_online()
