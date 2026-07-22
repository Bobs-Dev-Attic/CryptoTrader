"""Pydantic request/response schemas for the REST API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .enums import (
    AgentStatus,
    ExchangeId,
    SignalAction,
    StrategyType,
    TradeMode,
)


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class EmailUpdate(BaseModel):
    new_email: EmailStr
    current_password: str


class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


# --------------------------------------------------------------------------- #
# Exchange accounts
# --------------------------------------------------------------------------- #
class ExchangeAccountCreate(BaseModel):
    exchange: ExchangeId
    label: str = ""
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""


class ExchangeAccountUpdate(BaseModel):
    label: str | None = None
    is_active: bool | None = None
    # Provide any of these to replace stored credentials (leave unset to keep).
    api_key: str | None = None
    api_secret: str | None = None
    api_passphrase: str | None = None


class ExchangeAccountValidate(BaseModel):
    exchange: ExchangeId
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""


class ValidationResult(BaseModel):
    ok: bool
    message: str
    # True when the credentials authenticated against the exchange.
    authenticated: bool = False
    # Number of non-zero balances found (live keys only), if available.
    asset_count: int | None = None


class ExchangeAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exchange: ExchangeId
    label: str
    is_active: bool
    created_at: datetime
    # Never expose secrets; expose whether they are set.
    has_credentials: bool = False


# --------------------------------------------------------------------------- #
# Agents
# --------------------------------------------------------------------------- #
class AgentCreate(BaseModel):
    name: str
    exchange: ExchangeId
    symbol: str = "BTC/USD"
    timeframe: str = "1h"
    strategy_type: StrategyType
    strategy_config: dict = Field(default_factory=dict)
    risk_config: dict = Field(default_factory=dict)
    trade_mode: TradeMode = TradeMode.PAPER
    order_size_quote: float = 100.0
    paper_balance_quote: float = 10_000.0
    interval_seconds: int = 300
    account_id: int | None = None


class AgentUpdate(BaseModel):
    name: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    strategy_config: dict | None = None
    risk_config: dict | None = None
    trade_mode: TradeMode | None = None
    order_size_quote: float | None = None
    interval_seconds: int | None = None
    account_id: int | None = None


class PositionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    quantity: float
    avg_entry_price: float
    cash_quote: float
    realized_pnl: float


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    exchange: ExchangeId
    symbol: str
    timeframe: str
    strategy_type: StrategyType
    strategy_config: dict
    risk_config: dict = {}
    trade_mode: TradeMode
    order_size_quote: float
    paper_balance_quote: float
    interval_seconds: int
    status: AgentStatus
    last_error: str
    last_run_at: datetime | None
    account_id: int | None
    created_at: datetime
    position: PositionOut | None = None


class SignalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: SignalAction
    confidence: float
    price: float
    rationale: str
    details: dict
    created_at: datetime


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    side: str
    symbol: str
    quantity: float
    price: float
    cost_quote: float
    fee_quote: float
    realized_pnl: float = 0.0
    trade_mode: TradeMode
    status: str
    external_id: str
    note: str
    created_at: datetime


class AgentDetail(AgentOut):
    recent_signals: list[SignalOut] = []
    recent_trades: list[TradeOut] = []
    equity: float | None = None
    unrealized_pnl: float | None = None


# --------------------------------------------------------------------------- #
# Market data
# --------------------------------------------------------------------------- #
class CandleOut(BaseModel):
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
