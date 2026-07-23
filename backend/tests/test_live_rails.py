"""Tests for live-trading safety rails (risk.live_buy_guard)."""
from types import SimpleNamespace

from app.agents import risk


def _agent(**risk_config):
    return SimpleNamespace(id=1, risk_config=risk_config)


def _pos(qty=0.0):
    return SimpleNamespace(quantity=qty)


def test_slippage_aborts_buy():
    adj, reason = risk.live_buy_guard(
        None, _agent(max_slippage_pct=0.01), decision_price=100.0, live_price=105.0,
        buy_quote=100.0, position=_pos(),
    )
    assert adj == 0.0 and reason and "slippage" in reason


def test_within_slippage_allows_buy():
    adj, reason = risk.live_buy_guard(
        None, _agent(max_slippage_pct=0.02), decision_price=100.0, live_price=100.5,
        buy_quote=100.0, position=_pos(),
    )
    assert reason is None and adj == 100.0


def test_min_notional_floor_blocks_dust():
    adj, reason = risk.live_buy_guard(
        None, _agent(), decision_price=100.0, live_price=100.0, buy_quote=2.0, position=_pos()
    )
    assert adj == 0.0 and reason and "minimum notional" in reason


def test_position_cap_clamps():
    # Holding 8 units @ 100 = 800; cap 1000 -> 200 headroom clamps a 500 buy.
    adj, reason = risk.live_buy_guard(
        None, _agent(max_position_quote=1000.0), decision_price=100.0, live_price=100.0,
        buy_quote=500.0, position=_pos(qty=8.0),
    )
    assert reason is None and adj == 200.0


def test_position_cap_reached_blocks():
    adj, reason = risk.live_buy_guard(
        None, _agent(max_position_quote=1000.0), decision_price=100.0, live_price=100.0,
        buy_quote=500.0, position=_pos(qty=10.0),
    )
    assert adj == 0.0 and reason and "position cap" in reason


def test_no_config_passes_through():
    adj, reason = risk.live_buy_guard(
        None, _agent(), decision_price=100.0, live_price=100.0, buy_quote=100.0, position=_pos()
    )
    assert reason is None and adj == 100.0


def test_daily_cap_clamps(client, auth_headers):
    from app.database import SessionLocal
    from app.enums import OrderSide, TradeMode
    from app.models import Agent, Trade

    body = {
        "name": "L", "exchange": "kraken", "symbol": "BTC/USD", "timeframe": "1h",
        "strategy_type": "rule_based", "strategy_config": {}, "trade_mode": "paper",
        "order_size_quote": 100.0, "paper_balance_quote": 10_000.0, "interval_seconds": 60,
        "risk_config": {"daily_notional_cap": 1000.0},
    }
    aid = client.post("/api/agents", json=body, headers=auth_headers).json()["id"]

    db = SessionLocal()
    try:
        # Already spent $900 in live buys today.
        db.add(Trade(
            agent_id=aid, side=OrderSide.BUY, symbol="BTC/USD", quantity=0.01, price=90000.0,
            cost_quote=900.0, trade_mode=TradeMode.LIVE, status="filled",
        ))
        db.commit()
        agent = db.get(Agent, aid)
        adj, reason = risk.live_buy_guard(
            db, agent, decision_price=100.0, live_price=100.0, buy_quote=500.0, position=_pos()
        )
        assert reason is None and adj == 100.0  # clamped to the $100 remaining
    finally:
        db.close()
