"""Tests for the DB-backed rate limiter and agent-evaluation guards."""
from app import ratelimit
from app.database import SessionLocal
from app.locks import try_agent_lock


def test_rate_limiter_blocks_after_limit(monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", True)
    db = SessionLocal()
    try:
        key = "unit-test-key"
        results = [ratelimit.check_rate_limit(db, key, limit=3, window_seconds=3600) for _ in range(5)]
        # First 3 allowed, the rest blocked within the window.
        assert results[:3] == [True, True, True]
        assert results[3] is False and results[4] is False
    finally:
        db.close()


def test_rate_limiter_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(ratelimit.settings, "rate_limit_enabled", False)
    db = SessionLocal()
    try:
        assert all(ratelimit.check_rate_limit(db, "k2", limit=1, window_seconds=60) for _ in range(10))
    finally:
        db.close()


def test_try_agent_lock_noop_on_sqlite():
    # On SQLite the advisory lock is a no-op that always succeeds.
    db = SessionLocal()
    try:
        assert try_agent_lock(db, 123) is True
    finally:
        db.close()


def test_run_once_skips_when_not_due(client, auth_headers, fake_adapter):
    """With respect_interval, a just-run agent is not re-evaluated (returns None)."""
    from app.agents.runner import run_agent_once
    from app.models import Agent, User

    # Create a running-ish agent via the API, then drive run_agent_once directly.
    body = {
        "name": "T", "exchange": "kraken", "symbol": "BTC/USD", "timeframe": "1h",
        "strategy_type": "rule_based", "strategy_config": {"use_rsi": False},
        "trade_mode": "paper", "order_size_quote": 100.0, "paper_balance_quote": 10_000.0,
        "interval_seconds": 3600,
    }
    resp = client.post("/api/agents", json=body, headers=auth_headers)
    assert resp.status_code == 201
    agent_id = resp.json()["id"]

    db = SessionLocal()
    try:
        agent = db.get(Agent, agent_id)
        first = run_agent_once(db, agent, respect_interval=True)
        assert first is not None  # first run happens
        agent2 = db.get(Agent, agent_id)
        second = run_agent_once(db, agent2, respect_interval=True)
        assert second is None  # not due again within the hour -> skipped
    finally:
        db.close()
