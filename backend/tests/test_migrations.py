"""Tests for Alembic-based schema management and legacy adoption.

Each test drives ``run_migrations`` against its own throwaway SQLite file by
pointing the app's engine at it (env.py reads ``app.database.engine`` fresh on
every Alembic invocation, so patching that one reference redirects everything).
"""
import os
import tempfile

import pytest
from sqlalchemy import create_engine, inspect, text

import app.database as database
import app.migrations_runtime as mig
from app.database import Base
from app import models  # noqa: F401  (register metadata)
from app.migrations_runtime import BASELINE_REVISION, run_migrations


@pytest.fixture
def temp_engine(monkeypatch):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    # Redirect both the runner and env.py (which imports app.database.engine).
    monkeypatch.setattr(database, "engine", eng)
    monkeypatch.setattr(mig, "engine", eng)
    try:
        yield eng
    finally:
        eng.dispose()
        os.unlink(path)


def _version(eng) -> str | None:
    insp = inspect(eng)
    if "alembic_version" not in insp.get_table_names():
        return None
    with eng.connect() as c:
        return c.execute(text("SELECT version_num FROM alembic_version")).scalar()


def test_fresh_db_upgrades_from_zero(temp_engine):
    assert _version(temp_engine) is None
    run_migrations()
    assert _version(temp_engine) == BASELINE_REVISION
    tables = set(inspect(temp_engine).get_table_names())
    assert {"users", "agents", "positions", "trades", "equity_snapshots"} <= tables


def test_baseline_includes_formerly_added_columns(temp_engine):
    run_migrations()
    insp = inspect(temp_engine)
    assert "token_version" in [c["name"] for c in insp.get_columns("users")]
    assert "risk_config" in [c["name"] for c in insp.get_columns("agents")]
    assert "high_water" in [c["name"] for c in insp.get_columns("positions")]


def test_legacy_db_is_adopted_without_data_loss(temp_engine):
    # Simulate a pre-Alembic database: tables created the old way, a real row
    # of data, and NO alembic_version table.
    Base.metadata.create_all(bind=temp_engine)
    with temp_engine.begin() as c:
        c.execute(
            text("INSERT INTO users (email, hashed_password, token_version, created_at) "
                 "VALUES ('legacy@example.com', 'x', 0, '2026-01-01 00:00:00')")
        )
    assert _version(temp_engine) is None  # not yet under Alembic

    run_migrations()  # adopt in place

    assert _version(temp_engine) == BASELINE_REVISION
    with temp_engine.connect() as c:
        email = c.execute(text("SELECT email FROM users")).scalar()
    assert email == "legacy@example.com"  # data preserved, table not recreated


def test_run_migrations_is_idempotent(temp_engine):
    run_migrations()
    run_migrations()  # must not raise or change the head revision
    assert _version(temp_engine) == BASELINE_REVISION
