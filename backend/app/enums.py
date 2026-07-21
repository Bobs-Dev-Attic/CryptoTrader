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
