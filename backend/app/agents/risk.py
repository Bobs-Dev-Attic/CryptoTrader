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

Live-trading safety rails (LIVE mode only; applied to BUY entries, never exits):
    max_slippage_pct    float  abort a live buy if price moved > this since the bar
    min_notional        float  don't place a live buy below this (default 5)
    max_position_quote  float  cap total position value; clamp/skip beyond it
    daily_notional_cap  float  cap total live buy notional per UTC day
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..enums import OrderSide, TradeMode
from ..models import Agent, EquitySnapshot, Position, Trade
from . import indicators as ind

# Absolute floor for a live order notional, even if the agent sets a lower one.
_MIN_NOTIONAL_FLOOR = 5.0


def _f(cfg: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(cfg.get(key, default) or 0.0)
    except (TypeError, ValueError):
        return default


def live_buy_guard(
    db: Session | None,
    agent: Agent,
    decision_price: float,
    live_price: float,
    buy_quote: float,
    position: Position,
) -> tuple[float, str | None]:
    """Vet a LIVE buy against the safety rails. Returns (adjusted_quote, reason).

    ``reason`` non-None means DO NOT trade (and explains why). Otherwise the
    (possibly clamped) notional to actually deploy is returned. Exits (sells) are
    never gated — an agent must always be able to get out.
    """
    cfg = agent.risk_config or {}
    min_notional = max(_f(cfg, "min_notional"), _MIN_NOTIONAL_FLOOR)
    max_slip = _f(cfg, "max_slippage_pct")
    max_pos = _f(cfg, "max_position_quote")
    daily_cap = _f(cfg, "daily_notional_cap")

    # Slippage: abort if the live price has moved too far from the decision bar.
    if max_slip > 0 and decision_price > 0 and live_price > 0:
        slip = abs(live_price - decision_price) / decision_price
        if slip > max_slip:
            return 0.0, (
                f"slippage guard — price moved {slip * 100:.2f}% since the signal "
                f"(> {max_slip * 100:.2f}% allowed)"
            )

    # Max position cap: clamp the buy to remaining headroom.
    if max_pos > 0:
        current = position.quantity * (live_price or decision_price)
        headroom = max_pos - current
        if headroom <= 0:
            return 0.0, f"position cap reached (${current:.2f} ≥ ${max_pos:.2f})"
        buy_quote = min(buy_quote, headroom)

    # Daily notional cap: clamp to what's left of today's live-buy budget.
    if daily_cap > 0 and db is not None:
        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        spent = (
            db.query(func.coalesce(func.sum(Trade.cost_quote), 0.0))
            .filter(
                Trade.agent_id == agent.id,
                Trade.trade_mode == TradeMode.LIVE,
                Trade.side == OrderSide.BUY,
                Trade.created_at >= day_start,
            )
            .scalar()
            or 0.0
        )
        remaining = daily_cap - spent
        if remaining <= 0:
            return 0.0, f"daily notional cap reached (${spent:.2f} ≥ ${daily_cap:.2f})"
        buy_quote = min(buy_quote, remaining)

    if buy_quote < min_notional:
        return 0.0, f"order ${buy_quote:.2f} below minimum notional ${min_notional:.2f}"
    return round(buy_quote, 2), None


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
