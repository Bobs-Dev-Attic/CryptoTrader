"""Strategy interface shared by rule-based and LLM-powered agents."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field

from ..enums import SignalAction
from ..exchanges.base import Candle


@dataclass
class StrategyContext:
    """Everything a strategy needs to make one decision."""

    symbol: str
    timeframe: str
    candles: list[Candle]  # oldest first
    current_price: float
    # Current position state (from the agent's ledger).
    position_qty: float
    avg_entry_price: float
    cash_quote: float
    config: dict = field(default_factory=dict)

    @property
    def closes(self) -> list[float]:
        return [c.close for c in self.candles]

    @property
    def highs(self) -> list[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> list[float]:
        return [c.low for c in self.candles]

    @property
    def has_position(self) -> bool:
        return self.position_qty > 0


@dataclass
class StrategyDecision:
    """A strategy's recommended action for the current bar."""

    action: SignalAction
    confidence: float = 0.5  # 0..1
    rationale: str = ""
    details: dict = field(default_factory=dict)


class Strategy(abc.ABC):
    """Base class for all trading strategies.

    Implementations are pure decision functions: given market + position state
    they return a :class:`StrategyDecision`. Execution (paper or live) is handled
    by the runner, not the strategy.
    """

    #: Human-readable name for UI listings.
    name: str = "strategy"

    def __init__(self, config: dict | None = None) -> None:
        self.config = config or {}

    @abc.abstractmethod
    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        ...
