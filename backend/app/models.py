"""SQLAlchemy ORM models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base
from .enums import (
    AgentStatus,
    ExchangeId,
    OrderSide,
    OrderStatus,
    SignalAction,
    StrategyType,
    TradeMode,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    accounts: Mapped[list["ExchangeAccount"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    agents: Mapped[list["Agent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class ExchangeAccount(Base):
    """A user's connection to a specific exchange. API keys stored encrypted."""

    __tablename__ = "exchange_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    exchange: Mapped[ExchangeId] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(120), default="")

    # Encrypted at rest via app.security.encrypt_secret.
    api_key_enc: Mapped[str] = mapped_column(Text, default="")
    api_secret_enc: Mapped[str] = mapped_column(Text, default="")
    # Some exchanges (e.g. Coinbase Advanced) require a passphrase.
    api_passphrase_enc: Mapped[str] = mapped_column(Text, default="")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="accounts")
    agents: Mapped[list["Agent"]] = relationship(back_populates="account")


class Agent(Base):
    """A configured trading agent that runs a strategy on a symbol/exchange."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("exchange_accounts.id"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(120))
    exchange: Mapped[ExchangeId] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))  # e.g. "BTC/USD"
    timeframe: Mapped[str] = mapped_column(String(8), default="1h")

    strategy_type: Mapped[StrategyType] = mapped_column(String(32))
    # Free-form strategy parameters (indicator thresholds, LLM prompt hints, etc.)
    strategy_config: Mapped[dict] = mapped_column(JSON, default=dict)
    # Risk & exit overlays applied by the runner around any strategy
    # (stop-loss, take-profit, trailing stop, position sizing, drawdown kill,
    # post-loss cooldown). Empty dict = overlays off.
    risk_config: Mapped[dict] = mapped_column(JSON, default=dict)

    trade_mode: Mapped[TradeMode] = mapped_column(String(8), default=TradeMode.PAPER)
    # Notional amount (in quote currency) to deploy per BUY signal.
    order_size_quote: Mapped[float] = mapped_column(Float, default=100.0)
    # Starting paper balance in quote currency.
    paper_balance_quote: Mapped[float] = mapped_column(Float, default=10_000.0)

    # How often the agent evaluates, in seconds.
    interval_seconds: Mapped[int] = mapped_column(Integer, default=300)

    status: Mapped[AgentStatus] = mapped_column(String(16), default=AgentStatus.STOPPED)
    last_error: Mapped[str] = mapped_column(Text, default="")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    user: Mapped["User"] = relationship(back_populates="agents")
    account: Mapped["ExchangeAccount | None"] = relationship(back_populates="agents")
    signals: Mapped[list["Signal"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    trades: Mapped[list["Trade"]] = relationship(
        back_populates="agent", cascade="all, delete-orphan"
    )
    position: Mapped["Position | None"] = relationship(
        back_populates="agent", cascade="all, delete-orphan", uselist=False
    )


class Position(Base):
    """Current holdings for an agent (one open position per agent, per symbol)."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id"), unique=True, index=True
    )

    # Base asset quantity held (e.g. BTC amount).
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    # Average entry price in quote currency.
    avg_entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    # Free quote-currency balance (paper mode ledger).
    cash_quote: Mapped[float] = mapped_column(Float, default=0.0)
    # Realized profit/loss accumulated over closed trades.
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    # Highest price seen since the current position was opened (for trailing stops).
    high_water: Mapped[float] = mapped_column(Float, default=0.0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    agent: Mapped["Agent"] = relationship(back_populates="position")


class Signal(Base):
    """A decision produced by a strategy evaluation."""

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)

    action: Mapped[SignalAction] = mapped_column(String(8))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1
    price: Mapped[float] = mapped_column(Float, default=0.0)
    rationale: Mapped[str] = mapped_column(Text, default="")
    # Snapshot of indicators / analyst notes for transparency.
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    agent: Mapped["Agent"] = relationship(back_populates="signals")


class EquitySnapshot(Base):
    """Point-in-time equity for an agent, recorded on each evaluation tick.

    Powers the equity curve. Equity = cash + position marked to current price.
    """

    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    equity: Mapped[float] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    price: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class VolatilityWatch(Base):
    """A user's alert on a coin's volatility metric crossing a threshold.

    Evaluated by the internal tick; ``triggered`` reflects the latest check and
    ``last_triggered_at`` marks the most recent rising-edge crossing.
    """

    __tablename__ = "volatility_watches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    exchange: Mapped[ExchangeId] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(32))
    # One of: range_24h | change_24h | volume | ret_vol | atr_pct
    metric: Mapped[str] = mapped_column(String(16), default="range_24h")
    threshold: Mapped[float] = mapped_column(Float, default=5.0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Trade(Base):
    """An executed (or attempted) order, paper or live."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"), index=True)
    signal_id: Mapped[int | None] = mapped_column(
        ForeignKey("signals.id"), nullable=True
    )

    side: Mapped[OrderSide] = mapped_column(String(8))
    symbol: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[float] = mapped_column(Float)
    price: Mapped[float] = mapped_column(Float)
    cost_quote: Mapped[float] = mapped_column(Float)  # quantity * price
    fee_quote: Mapped[float] = mapped_column(Float, default=0.0)
    # Realized P&L booked by this order (nonzero only on position-closing sells).
    realized_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    trade_mode: Mapped[TradeMode] = mapped_column(String(8))
    status: Mapped[OrderStatus] = mapped_column(String(16), default=OrderStatus.FILLED)
    # Exchange order id for live trades; empty for paper.
    external_id: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)

    agent: Mapped["Agent"] = relationship(back_populates="trades")
