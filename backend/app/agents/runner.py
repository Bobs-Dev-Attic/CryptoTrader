"""Agent execution: evaluate a strategy and route the decision to execution.

``run_agent_once`` is the single entry point used by both the scheduler and the
manual "run now" API endpoint. It is transactional per invocation and records a
Signal for every evaluation plus a Trade whenever an order is executed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..enums import (
    AgentStatus,
    OrderStatus,
    SignalAction,
    TradeMode,
)
from ..exchanges import get_adapter
from ..exchanges.base import OrderResult
from ..exchanges.paper import Ledger, PaperBroker
from ..locks import try_agent_lock
from ..models import Agent, EquitySnapshot, Position, Signal, Trade
from ..observability import audit, capture_exception
from ..security import decrypt_secret
from . import risk
from .base import StrategyContext, StrategyDecision
from .registry import build_strategy


def _get_or_create_position(db: Session, agent: Agent) -> Position:
    if agent.position is not None:
        return agent.position
    pos = Position(
        agent_id=agent.id,
        quantity=0.0,
        avg_entry_price=0.0,
        cash_quote=agent.paper_balance_quote,
        realized_pnl=0.0,
    )
    db.add(pos)
    db.flush()
    return pos


def run_agent_once(
    db: Session, agent: Agent, respect_interval: bool = False
) -> Signal | None:
    """Evaluate one agent and execute any resulting order.

    Returns the recorded Signal, or ``None`` when the evaluation is skipped
    because another worker holds the per-agent lock, or (``respect_interval``)
    the agent isn't due yet — checked *inside* the lock so overlapping ticks can
    never double-execute the same agent (and never place duplicate live orders).
    """
    # Cross-instance guard: acquire the per-agent transaction advisory lock.
    if not try_agent_lock(db, agent.id):
        db.rollback()
        return None
    db.refresh(agent)  # read fresh last_run_at while holding the lock

    now = datetime.now(timezone.utc)
    if respect_interval and agent.last_run_at is not None:
        last = agent.last_run_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last + timedelta(seconds=agent.interval_seconds) > now:
            db.rollback()  # not due — another worker just ran it; release lock
            return None

    agent.last_run_at = now

    # Credentials (only needed for live trading / private data).
    api_key = api_secret = api_pass = ""
    if agent.account is not None:
        api_key = decrypt_secret(agent.account.api_key_enc)
        api_secret = decrypt_secret(agent.account.api_secret_enc)
        api_pass = decrypt_secret(agent.account.api_passphrase_enc)

    adapter = get_adapter(agent.exchange, api_key, api_secret, api_pass)

    # --- Market data --------------------------------------------------- #
    try:
        candles = adapter.fetch_ohlcv(agent.symbol, agent.timeframe, limit=200)
        if not candles:
            raise RuntimeError("No candle data returned by exchange.")
        current_price = candles[-1].close
    except Exception as exc:
        agent.status = AgentStatus.ERROR
        agent.last_error = f"market data error: {exc}"
        signal = Signal(
            agent_id=agent.id,
            action=SignalAction.HOLD,
            confidence=0.0,
            price=0.0,
            rationale=agent.last_error,
            details={},
        )
        db.add(signal)
        db.commit()
        return signal

    position = _get_or_create_position(db, agent)
    risk_cfg = agent.risk_config or {}

    # Track the running peak price while in a position (for trailing stops).
    if position.quantity > 0:
        position.high_water = max(position.high_water or 0.0, current_price)
    equity_now = position.cash_quote + position.quantity * current_price

    # --- Strategy decision -------------------------------------------- #
    strategy = build_strategy(agent.strategy_type, agent.strategy_config or {})
    ctx = StrategyContext(
        symbol=agent.symbol,
        timeframe=agent.timeframe,
        candles=candles,
        current_price=current_price,
        position_qty=position.quantity,
        avg_entry_price=position.avg_entry_price,
        cash_quote=position.cash_quote,
        config=agent.strategy_config or {},
    )
    decision = strategy.decide(ctx)

    # --- Risk & exit overlays (may override the strategy's decision) --- #
    stop_after = False  # drawdown kill-switch: stop the agent after this tick
    drawdown = risk.check_drawdown(db, agent, equity_now)
    if drawdown:
        stop_after = True
        if position.quantity > 0:
            decision = StrategyDecision(SignalAction.SELL, 1.0, f"Risk: {drawdown} — liquidating and stopping.")
        else:
            decision = StrategyDecision(SignalAction.HOLD, 0.0, f"Risk: {drawdown} — agent stopped.")
    else:
        forced = risk.check_exit(risk_cfg, position, current_price)
        if forced:
            decision = StrategyDecision(SignalAction.SELL, 1.0, f"Risk: {forced}.")
        elif decision.action == SignalAction.BUY:
            remaining = risk.cooldown_remaining(db, agent)
            if remaining > 0:
                decision = StrategyDecision(
                    SignalAction.HOLD,
                    decision.confidence,
                    f"Cooldown after a losing trade — {remaining}s remaining.",
                    decision.details,
                )

    signal = Signal(
        agent_id=agent.id,
        action=decision.action,
        confidence=decision.confidence,
        price=current_price,
        rationale=decision.rationale,
        details=decision.details or {},
    )
    db.add(signal)
    db.flush()  # assign signal.id for the trade FK

    # --- Execution ----------------------------------------------------- #
    if decision.action in (SignalAction.BUY, SignalAction.SELL):
        try:
            order_quote = (
                risk.entry_notional(agent, equity_now, current_price, ctx.highs, ctx.lows, ctx.closes)
                if decision.action == SignalAction.BUY
                else agent.order_size_quote
            )
            self_execute(db, agent, position, decision.action, current_price, signal, order_quote)
            agent.status = AgentStatus.RUNNING
            agent.last_error = ""
        except NotImplementedError as exc:
            agent.status = AgentStatus.ERROR
            agent.last_error = str(exc)
            signal.rationale += f" | execution skipped: {exc}"
        except Exception as exc:
            agent.status = AgentStatus.ERROR
            agent.last_error = f"execution error: {exc}"
            capture_exception(
                exc, agent_id=agent.id, exchange=str(agent.exchange), trade_mode=str(agent.trade_mode)
            )
    else:
        agent.status = AgentStatus.RUNNING
        agent.last_error = ""

    # Maintain the trailing-stop high-water mark and stop on a drawdown kill.
    if position.quantity > 0:
        position.high_water = max(position.high_water or 0.0, current_price)
    else:
        position.high_water = 0.0
    if stop_after:
        agent.status = AgentStatus.STOPPED
        agent.last_error = drawdown

    # Record an equity snapshot for the equity curve (cash + position at mark).
    equity = position.cash_quote + position.quantity * current_price
    db.add(
        EquitySnapshot(
            agent_id=agent.id,
            equity=equity,
            realized_pnl=position.realized_pnl,
            price=current_price,
        )
    )

    db.commit()
    return signal


def self_execute(
    db: Session,
    agent: Agent,
    position: Position,
    action: SignalAction,
    price: float,
    signal: Signal,
    order_quote: float | None = None,
) -> None:
    """Execute a BUY or SELL for the agent in its configured trade mode.

    ``order_quote`` is the quote-currency notional to deploy on a BUY (defaults to
    the agent's fixed ``order_size_quote``); risk-based position sizing passes a
    computed value.
    """
    result: OrderResult | None = None
    trade_realized = 0.0  # P&L booked by this order (sells that close a position)
    buy_quote = agent.order_size_quote if order_quote is None else order_quote

    if agent.trade_mode == TradeMode.PAPER:
        broker = PaperBroker()
        prev_realized = position.realized_pnl
        ledger = Ledger(
            cash_quote=position.cash_quote,
            quantity=position.quantity,
            avg_entry_price=position.avg_entry_price,
            realized_pnl=position.realized_pnl,
        )
        if action == SignalAction.BUY:
            result = broker.buy(ledger, agent.symbol, price, buy_quote)
        else:
            result = broker.sell_all(ledger, agent.symbol, price)

        if result is not None:
            trade_realized = ledger.realized_pnl - prev_realized
            # Persist the mutated ledger back onto the position.
            position.cash_quote = ledger.cash_quote
            position.quantity = ledger.quantity
            position.avg_entry_price = ledger.avg_entry_price
            position.realized_pnl = ledger.realized_pnl

    else:  # LIVE
        adapter = _live_adapter(agent)
        if action == SignalAction.BUY:
            # Use the live price for the guard + sizing (market may have moved).
            try:
                live_price = adapter.fetch_ticker(agent.symbol).last or price
            except Exception:
                live_price = price
            adj_quote, reason = risk.live_buy_guard(db, agent, price, live_price, buy_quote, position)
            if reason:
                signal.rationale += f" | live buy skipped — {reason}"
                return
            qty = adj_quote / live_price if live_price > 0 else 0.0
            if qty <= 0:
                signal.rationale += " | live buy skipped — computed zero quantity"
                return
            result = adapter.create_market_order(agent.symbol, "buy", qty)
            # Track position from the fill (best-effort; live balances are source of truth).
            filled = result.quantity
            prev = position.quantity
            new_qty = prev + filled
            position.avg_entry_price = (
                (position.avg_entry_price * prev + result.price * filled) / new_qty
                if new_qty > 0
                else 0.0
            )
            position.quantity = new_qty
        else:
            qty = position.quantity
            if qty <= 0:
                return
            result = adapter.create_market_order(agent.symbol, "sell", qty)
            trade_realized = (result.price - position.avg_entry_price) * result.quantity
            position.realized_pnl += trade_realized
            position.quantity = 0.0
            position.avg_entry_price = 0.0

    if result is None:
        signal.rationale += " | order not executed (insufficient funds / flat)."
        return

    trade = Trade(
        agent_id=agent.id,
        signal_id=signal.id,
        side=result.side,
        symbol=result.symbol,
        quantity=result.quantity,
        price=result.price,
        cost_quote=result.cost,
        fee_quote=result.fee,
        realized_pnl=trade_realized,
        trade_mode=agent.trade_mode,
        status=OrderStatus(result.status) if result.status in OrderStatus._value2member_map_ else OrderStatus.FILLED,
        external_id=result.external_id,
        note=result.note,
    )
    db.add(trade)

    # Immutable audit trail of every executed order (no secrets / PII).
    audit(
        "trade.executed",
        agent_id=agent.id,
        trade_mode=str(agent.trade_mode),
        exchange=str(agent.exchange),
        side=str(result.side),
        symbol=result.symbol,
        quantity=result.quantity,
        price=result.price,
        cost_quote=result.cost,
        realized_pnl=trade_realized,
        external_id=result.external_id or None,
    )


def _live_adapter(agent: Agent):
    if agent.account is None:
        raise NotImplementedError("Live trading requires a linked exchange account.")
    adapter = get_adapter(
        agent.exchange,
        decrypt_secret(agent.account.api_key_enc),
        decrypt_secret(agent.account.api_secret_enc),
        decrypt_secret(agent.account.api_passphrase_enc),
    )
    if not adapter.supports_live:
        raise NotImplementedError(
            f"{agent.exchange} does not support live execution in this build."
        )
    return adapter
