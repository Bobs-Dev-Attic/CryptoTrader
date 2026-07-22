"""Risk & exit overlays applied by the runner around any strategy.

The strategy decides *direction*; these helpers decide *whether to force an exit*,
*how much to buy*, and *whether the agent should keep trading at all*. They read
``agent.risk_config`` (a plain dict) and default to OFF, so an agent with an
empty config behaves exactly as before.

risk_config keys (all optional):
    stop_loss_pct      float  e.g. 0.05 = exit if price falls 5% below entry
    take_profit_pct    float  e.g. 0.10 = exit if price rises 10% above entry
    trailing_stop_pct  float  e.g. 0.05 = exit if price falls 5% below the peak
    max_drawdown_pct   float  e.g. 0.20 = stop the agent if equity falls 20% from its peak
    cooldown_seconds   int    block new BUYs for N seconds after a losing exit
    sizing             str    "fixed" | "fixed_fractional" | "atr_target"
    risk_pct           float  fraction of equity per trade (sizing modes)
    atr_period         int    ATR lookback for atr_target sizing (default 14)
    atr_mult           float  stop distance in ATRs for atr_target sizing (default 2)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..enums import OrderSide
from ..models import Agent, EquitySnapshot, Position, Trade
from . import indicators as ind


def _f(cfg: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(cfg.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return default


def check_exit(cfg: dict, position: Position, price: float) -> str | None:
    """Return a forced-exit reason if a stop/target/trailing rule triggers."""
    if position.quantity <= 0 or position.avg_entry_price <= 0 or price <= 0:
        return None
    entry = position.avg_entry_price
    sl = _f(cfg, "stop_loss_pct")
    tp = _f(cfg, "take_profit_pct")
    trail = _f(cfg, "trailing_stop_pct")
    if sl > 0 and price <= entry * (1 - sl):
        return f"stop-loss hit ({price:.2f} ≤ {entry * (1 - sl):.2f})"
    if tp > 0 and price >= entry * (1 + tp):
        return f"take-profit hit ({price:.2f} ≥ {entry * (1 + tp):.2f})"
    if trail > 0 and position.high_water > 0 and price <= position.high_water * (1 - trail):
        return f"trailing stop hit ({price:.2f} ≤ {position.high_water * (1 - trail):.2f})"
    return None


def check_drawdown(db: Session, agent: Agent, current_equity: float) -> str | None:
    """Return a reason if equity has fallen more than max_drawdown_pct from its peak."""
    mdd = _f(agent.risk_config or {}, "max_drawdown_pct")
    if mdd <= 0:
        return None
    peak = db.query(func.max(EquitySnapshot.equity)).filter(
        EquitySnapshot.agent_id == agent.id
    ).scalar()
    peak = max(peak or 0.0, current_equity)
    if peak <= 0:
        return None
    if current_equity <= peak * (1 - mdd):
        return f"max drawdown hit ({(1 - current_equity / peak) * 100:.1f}% ≥ {mdd * 100:.0f}%)"
    return None


def cooldown_remaining(db: Session, agent: Agent, now: datetime | None = None) -> int:
    """Seconds remaining in a post-loss cooldown (0 if not cooling down)."""
    secs = int(_f(agent.risk_config or {}, "cooldown_seconds"))
    if secs <= 0:
        return 0
    now = now or datetime.now(timezone.utc)
    last_loss = (
        db.query(Trade)
        .filter(
            Trade.agent_id == agent.id,
            Trade.side == OrderSide.SELL,
            Trade.realized_pnl < 0,
        )
        .order_by(Trade.created_at.desc())
        .first()
    )
    if not last_loss:
        return 0
    ts = last_loss.created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    elapsed = (now - ts).total_seconds()
    return max(0, int(secs - elapsed))


def entry_notional(
    agent: Agent,
    equity: float,
    price: float,
    highs, lows, closes,
) -> float:
    """Quote-currency amount to deploy on a BUY, per the sizing rule.

    Falls back to the agent's fixed ``order_size_quote`` for the default mode or
    when a volatility estimate isn't available yet.
    """
    cfg = agent.risk_config or {}
    mode = str(cfg.get("sizing", "fixed") or "fixed")
    base = float(agent.order_size_quote)
    if mode == "fixed" or equity <= 0 or price <= 0:
        return base
    risk_pct = _f(cfg, "risk_pct")
    if risk_pct <= 0:
        return base
    if mode == "fixed_fractional":
        return round(equity * risk_pct, 2)
    if mode == "atr_target":
        period = int(_f(cfg, "atr_period", 14) or 14)
        mult = _f(cfg, "atr_mult", 2.0) or 2.0
        atr = ind.atr(highs, lows, closes, period)
        if not atr or atr <= 0:
            return base
        stop_distance = mult * atr  # price move to the stop
        # Size so a stop-out loses ~risk_pct of equity: qty = risk$ / stop_distance.
        risk_dollars = equity * risk_pct
        qty = risk_dollars / stop_distance
        return round(min(qty * price, equity), 2)
    return base
