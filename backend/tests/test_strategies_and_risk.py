"""Tests for the new technical strategies, risk overlays, and portfolio optimize."""
from types import SimpleNamespace

from app.agents import indicators as ind
from app.agents import risk
from app.agents.base import StrategyContext
from app.agents.registry import available_strategies, build_strategy
from app.enums import SignalAction, StrategyType
from app.exchanges.base import Candle


def _ohlc(closes, spread=1.0, position_qty=0.0):
    candles = [
        Candle(timestamp=i * 3600_000, open=c, high=c + spread, low=c - spread, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]
    return StrategyContext(
        symbol="BTC/USD",
        timeframe="1h",
        candles=candles,
        current_price=closes[-1],
        position_qty=position_qty,
        avg_entry_price=closes[0] if position_qty else 0.0,
        cash_quote=10_000.0,
    )


# --- Indicators ----------------------------------------------------------- #
def test_indicators_defined_on_uptrend():
    closes = [100.0 + i for i in range(60)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    assert ind.atr(highs, lows, closes, 14) is not None
    assert ind.bollinger(closes, 20) is not None
    assert ind.roc(closes, 10) > 0  # rising
    adx = ind.adx(highs, lows, closes, 14)
    assert adx is not None and adx[1] >= adx[2]  # +DI >= -DI in an uptrend


def test_donchian_breakout_buys_on_new_high():
    closes = [100.0 + i for i in range(40)]  # strictly rising -> breaks its own channel
    # spread=0 so the channel's upper (prior highest high) sits just below the
    # current close, making the rise a genuine breakout.
    d = build_strategy(StrategyType.DONCHIAN, {"period": 20}).decide(_ohlc(closes, spread=0.0))
    assert d.action == SignalAction.BUY


def test_bollinger_buys_on_sharp_dip():
    closes = [100.0] * 30 + [80.0]  # sudden drop below lower band
    d = build_strategy(StrategyType.BOLLINGER, {"period": 20, "k": 2.0}).decide(_ohlc(closes))
    assert d.action == SignalAction.BUY


def test_momentum_sells_on_strong_drop_with_position():
    closes = [200.0 - i * 2 for i in range(30)]  # falling fast
    d = build_strategy(StrategyType.MOMENTUM, {"period": 10, "threshold": 2.0}).decide(
        _ohlc(closes, position_qty=1.0)
    )
    assert d.action == SignalAction.SELL


def test_all_new_strategies_return_valid_action():
    closes = [100.0 + (i % 7) - 3 for i in range(80)]  # choppy
    for st in (
        StrategyType.DONCHIAN, StrategyType.SUPERTREND, StrategyType.BOLLINGER,
        StrategyType.ZSCORE, StrategyType.MOMENTUM, StrategyType.ADX,
    ):
        d = build_strategy(st).decide(_ohlc(closes))
        assert d.action in (SignalAction.BUY, SignalAction.SELL, SignalAction.HOLD)


def test_available_strategies_lists_all_types():
    types = {s["type"] for s in available_strategies()}
    assert {"rule_based", "llm", "donchian", "supertrend", "bollinger", "zscore", "momentum", "adx"} <= types


# --- Risk overlays (pure helpers) ---------------------------------------- #
def _pos(qty=1.0, entry=100.0, high=100.0):
    return SimpleNamespace(quantity=qty, avg_entry_price=entry, high_water=high)


def test_stop_loss_triggers_exit():
    reason = risk.check_exit({"stop_loss_pct": 0.05}, _pos(entry=100.0), price=94.0)
    assert reason and "stop-loss" in reason


def test_take_profit_triggers_exit():
    reason = risk.check_exit({"take_profit_pct": 0.10}, _pos(entry=100.0), price=111.0)
    assert reason and "take-profit" in reason


def test_trailing_stop_triggers_exit():
    reason = risk.check_exit({"trailing_stop_pct": 0.05}, _pos(entry=100.0, high=120.0), price=113.0)
    assert reason and "trailing" in reason


def test_no_exit_when_disabled():
    assert risk.check_exit({}, _pos(entry=100.0), price=50.0) is None


def test_fixed_fractional_sizing():
    agent = SimpleNamespace(order_size_quote=100.0, risk_config={"sizing": "fixed_fractional", "risk_pct": 0.1})
    notional = risk.entry_notional(agent, equity=10_000.0, price=100.0, highs=[], lows=[], closes=[])
    assert abs(notional - 1000.0) < 1e-6


def test_fixed_sizing_default():
    agent = SimpleNamespace(order_size_quote=250.0, risk_config={})
    notional = risk.entry_notional(agent, equity=10_000.0, price=100.0, highs=[], lows=[], closes=[])
    assert notional == 250.0


# --- API integration ------------------------------------------------------ #
def _make_agent(client, headers, **overrides):
    body = {
        "name": "T", "exchange": "kraken", "symbol": "BTC/USD", "timeframe": "1h",
        "strategy_type": "rule_based", "strategy_config": {"use_rsi": False},
        "trade_mode": "paper", "order_size_quote": 100.0, "paper_balance_quote": 10_000.0,
        "interval_seconds": 60,
    }
    body.update(overrides)
    resp = client.post("/api/agents", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_risk_config_roundtrips(client, auth_headers):
    agent = _make_agent(client, auth_headers, risk_config={"stop_loss_pct": 0.05})
    assert agent["risk_config"]["stop_loss_pct"] == 0.05


def test_fixed_fractional_sizing_applied_on_run(client, auth_headers, fake_adapter):
    # Uptrend feed + rule_based(no RSI) => BUY; sizing should deploy ~10% of equity.
    agent = _make_agent(
        client, auth_headers,
        risk_config={"sizing": "fixed_fractional", "risk_pct": 0.1},
    )
    run = client.post(f"/api/agents/{agent['id']}/run", headers=auth_headers)
    assert run.status_code == 200, run.text
    detail = client.get(f"/api/agents/{agent['id']}", headers=auth_headers).json()
    assert detail["recent_trades"], "expected a buy trade"
    # ~10% of 10_000 = ~1000 (minus fees), not the 100 default.
    assert detail["recent_trades"][0]["cost_quote"] > 500


def test_new_strategy_agent_runs(client, auth_headers, fake_adapter):
    agent = _make_agent(client, auth_headers, strategy_type="donchian", strategy_config={"period": 20})
    run = client.post(f"/api/agents/{agent['id']}/run", headers=auth_headers)
    assert run.status_code == 200, run.text
    assert run.json()["action"] in ("buy", "sell", "hold")


def test_portfolio_optimize(client, auth_headers, fake_adapter):
    a = _make_agent(client, auth_headers)
    client.post(f"/api/agents/{a['id']}/run", headers=auth_headers)
    resp = client.get("/api/portfolio/optimize?method=risk_parity", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["method"] == "risk_parity"
    assert isinstance(data["allocations"], list) and data["allocations"]
    assert abs(sum(a["weight"] for a in data["allocations"]) - 1.0) < 1e-6
