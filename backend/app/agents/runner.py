"""Agent execution: evaluate a strategy and route the decision to execution.

``run_agent_once`` is the single entry point used by both the scheduler and the
manual "run now" API endpoint. It is transactional per invocation and records a
Signal for every evaluation plus a Trade whenever an order is executed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

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
from ..models import Agent, Position, Signal, Trade
from ..security import decrypt_secret
from .base import StrategyContext
from .registry import build_strategy

logger = logging.getLogger("cryptotrader.runner")


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


def run_agent_once(db: Session, agent: Agent) -> Signal:
    """Evaluate one agent and execute any resulting order. Returns the Signal."""
    agent.last_run_at = datetime.now(timezone.utc)

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
            self_execute(db, agent, position, decision.action, current_price, signal)
            agent.status = AgentStatus.RUNNING
            agent.last_error = ""
        except NotImplementedError as exc:
            agent.status = AgentStatus.ERROR
            agent.last_error = str(exc)
            signal.rationale += f" | execution skipped: {exc}"
        except Exception as exc:
            agent.status = AgentStatus.ERROR
            agent.last_error = f"execution error: {exc}"
            logger.exception("Execution failed for agent %s", agent.id)
    else:
        agent.status = AgentStatus.RUNNING
        agent.last_error = ""

    db.commit()
    return signal


def self_execute(
    db: Session,
    agent: Agent,
    position: Position,
    action: SignalAction,
    price: float,
    signal: Signal,
) -> None:
    """Execute a BUY or SELL for the agent in its configured trade mode."""
    result: OrderResult | None = None

    if agent.trade_mode == TradeMode.PAPER:
        broker = PaperBroker()
        ledger = Ledger(
            cash_quote=position.cash_quote,
            quantity=position.quantity,
            avg_entry_price=position.avg_entry_price,
            realized_pnl=position.realized_pnl,
        )
        if action == SignalAction.BUY:
            result = broker.buy(ledger, agent.symbol, price, agent.order_size_quote)
        else:
            result = broker.sell_all(ledger, agent.symbol, price)

        if result is not None:
            # Persist the mutated ledger back onto the position.
            position.cash_quote = ledger.cash_quote
            position.quantity = ledger.quantity
            position.avg_entry_price = ledger.avg_entry_price
            position.realized_pnl = ledger.realized_pnl

    else:  # LIVE
        adapter = _live_adapter(agent)
        if action == SignalAction.BUY:
            qty = agent.order_size_quote / price if price > 0 else 0.0
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
            realized = (result.price - position.avg_entry_price) * result.quantity
            position.realized_pnl += realized
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
        trade_mode=agent.trade_mode,
        status=OrderStatus(result.status) if result.status in OrderStatus._value2member_map_ else OrderStatus.FILLED,
        external_id=result.external_id,
        note=result.note,
    )
    db.add(trade)


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
