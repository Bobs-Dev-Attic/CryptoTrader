"""Tests for data retention pruning and bounded portfolio queries."""
from datetime import datetime, timedelta, timezone

import pytest

from app.api import portfolio
from app.database import SessionLocal, init_db
from app.enums import OrderSide, StrategyType, TradeMode
from app.models import Agent, EquitySnapshot, Signal, Trade, User
from app.retention import prune_old_rows


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def db():
    init_db()  # ensure schema exists (app startup normally does this)
    s = SessionLocal()
    # The suite shares one sqlite file; isolate the high-volume tables so a
    # prior test's rows can't be swept into this test's global age-based batch.
    s.query(Trade).delete()
    s.query(Signal).delete()
    s.query(EquitySnapshot).delete()
    s.commit()
    try:
        yield s
    finally:
        s.close()


def _make_user(db, email_suffix: str) -> User:
    u = User(email=f"ret-{email_suffix}@example.com", hashed_password="x")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _make_agent(db, user: User) -> Agent:
    a = Agent(
        user_id=user.id,
        name="ret-agent",
        exchange="kraken",
        symbol="BTC/USD",
        strategy_type=StrategyType.RULE_BASED,
        trade_mode=TradeMode.PAPER,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_prune_drops_old_keeps_recent_and_trades(db):
    user = _make_user(db, "prune")
    agent = _make_agent(db, user)
    now = _naive_now()
    old = now - timedelta(days=200)
    recent = now - timedelta(days=1)

    db.add_all([
        EquitySnapshot(agent_id=agent.id, equity=100.0, created_at=old),
        EquitySnapshot(agent_id=agent.id, equity=110.0, created_at=recent),
        Signal(agent_id=agent.id, action="buy", created_at=old),
        Signal(agent_id=agent.id, action="hold", created_at=recent),
        # A trade older than any retention window must survive — it's the record.
        Trade(
            agent_id=agent.id, side=OrderSide.SELL, symbol="BTC/USD",
            quantity=1.0, price=100.0, cost_quote=100.0, realized_pnl=5.0,
            trade_mode=TradeMode.PAPER, created_at=old,
        ),
    ])
    db.commit()

    result = prune_old_rows(db, now)
    assert result["snapshots"] == 1
    assert result["signals"] == 1

    snaps = db.query(EquitySnapshot).filter(EquitySnapshot.agent_id == agent.id).all()
    assert [round(s.equity, 1) for s in snaps] == [110.0]  # only the recent one
    sigs = db.query(Signal).filter(Signal.agent_id == agent.id).all()
    assert [s.action for s in sigs] == ["hold"]
    trades = db.query(Trade).filter(Trade.agent_id == agent.id).all()
    assert len(trades) == 1  # trades are never pruned


def test_prune_is_noop_when_within_window(db):
    user = _make_user(db, "noop")
    agent = _make_agent(db, user)
    now = _naive_now()
    db.add(EquitySnapshot(agent_id=agent.id, equity=100.0, created_at=now - timedelta(days=2)))
    db.commit()
    assert prune_old_rows(db, now) == {"snapshots": 0, "signals": 0}


def test_prune_respects_disabled_retention(db, monkeypatch):
    user = _make_user(db, "disabled")
    agent = _make_agent(db, user)
    now = _naive_now()
    db.add(EquitySnapshot(agent_id=agent.id, equity=1.0, created_at=now - timedelta(days=999)))
    db.commit()
    from app import retention
    monkeypatch.setattr(retention.settings, "retention_enabled", False)
    assert prune_old_rows(db, now) == {"snapshots": 0, "signals": 0}
    assert db.query(EquitySnapshot).filter(EquitySnapshot.agent_id == agent.id).count() == 1


def test_prune_batches_are_bounded(db, monkeypatch):
    user = _make_user(db, "batch")
    agent = _make_agent(db, user)
    now = _naive_now()
    old = now - timedelta(days=200)
    db.add_all([EquitySnapshot(agent_id=agent.id, equity=float(i), created_at=old) for i in range(10)])
    db.commit()
    from app import retention
    monkeypatch.setattr(retention.settings, "retention_batch", 3)
    assert prune_old_rows(db, now)["snapshots"] == 3  # capped at the batch size
    assert db.query(EquitySnapshot).filter(EquitySnapshot.agent_id == agent.id).count() == 7


def test_stats_winloss_aggregated_in_sql(db):
    user = _make_user(db, "stats")
    agent = _make_agent(db, user)
    db.add_all([
        Trade(agent_id=agent.id, side=OrderSide.SELL, symbol="BTC/USD", quantity=1,
              price=1, cost_quote=1, realized_pnl=10.0, trade_mode=TradeMode.PAPER),
        Trade(agent_id=agent.id, side=OrderSide.SELL, symbol="BTC/USD", quantity=1,
              price=1, cost_quote=1, realized_pnl=-4.0, trade_mode=TradeMode.PAPER),
        Trade(agent_id=agent.id, side=OrderSide.SELL, symbol="BTC/USD", quantity=1,
              price=1, cost_quote=1, realized_pnl=6.0, trade_mode=TradeMode.PAPER),
        # A BUY must not count toward win/loss.
        Trade(agent_id=agent.id, side=OrderSide.BUY, symbol="BTC/USD", quantity=1,
              price=1, cost_quote=1, realized_pnl=0.0, trade_mode=TradeMode.PAPER),
    ])
    db.commit()

    out = portfolio.stats(user=user, db=db)
    assert out["wins"] == 2
    assert out["losses"] == 1
    assert out["closed_trades"] == 3
    assert out["avg_win"] == 8.0   # (10 + 6) / 2
    assert out["avg_loss"] == -4.0
    assert out["win_rate"] == round(2 / 3, 3)


def test_equity_history_windows_and_seeds_baseline(db):
    user = _make_user(db, "hist")
    a1 = _make_agent(db, user)
    a2 = _make_agent(db, user)
    now = _naive_now()
    # a1 last snapshot is OLD (before the 7-day window) -> must be carried in.
    db.add(EquitySnapshot(agent_id=a1.id, equity=100.0, created_at=now - timedelta(days=30)))
    # a2 has an in-window snapshot.
    db.add(EquitySnapshot(agent_id=a2.id, equity=50.0, created_at=now - timedelta(days=1)))
    db.commit()

    points = portfolio.equity_history(days=7, user=user, db=db)
    # One in-window event (a2); the portfolio total includes a1's carried-in 100.
    assert len(points) == 1
    assert points[-1]["equity"] == 150.0


def test_equity_history_full_series_without_window(db):
    user = _make_user(db, "full")
    agent = _make_agent(db, user)
    now = _naive_now()
    db.add_all([
        EquitySnapshot(agent_id=agent.id, equity=100.0, created_at=now - timedelta(days=3)),
        EquitySnapshot(agent_id=agent.id, equity=120.0, created_at=now - timedelta(days=1)),
    ])
    db.commit()
    points = portfolio.equity_history(days=None, user=user, db=db)
    assert [p["equity"] for p in points] == [100.0, 120.0]
