"""Shared enumerations used across models, schemas, and business logic."""
from __future__ import annotations

import enum


class ExchangeId(str, enum.Enum):
    KRAKEN = "kraken"
    BINANCE = "binance"
    COINBASE = "coinbase"
    ROBINHOOD = "robinhood"


class TradeMode(str, enum.Enum):
    """Whether an agent trades against a simulated ledger or real money."""

    PAPER = "paper"
    LIVE = "live"


class StrategyType(str, enum.Enum):
    RULE_BASED = "rule_based"
    LLM = "llm"
    # Additional single-method technical strategies.
    DONCHIAN = "donchian"          # channel breakout (trend-following)
    SUPERTREND = "supertrend"      # ATR trend-following
    BOLLINGER = "bollinger"        # Bollinger Band mean-reversion
    ZSCORE = "zscore"              # z-score mean-reversion
    MOMENTUM = "momentum"          # rate-of-change momentum
    ADX = "adx"                    # ADX/DI trend-strength filter


class AgentStatus(str, enum.Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    ERROR = "error"


class SignalAction(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class OrderSide(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, enum.Enum):
    FILLED = "filled"
    REJECTED = "rejected"
    PENDING = "pending"
