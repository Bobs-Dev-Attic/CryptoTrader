"""Maps a StrategyType to a concrete Strategy implementation."""
from __future__ import annotations

from ..enums import StrategyType
from .base import Strategy
from .llm_agent import LLMStrategy
from .rule_based import RuleBasedStrategy

_REGISTRY: dict[StrategyType, type[Strategy]] = {
    StrategyType.RULE_BASED: RuleBasedStrategy,
    StrategyType.LLM: LLMStrategy,
}


def build_strategy(strategy_type: str | StrategyType, config: dict | None = None) -> Strategy:
    st = (
        StrategyType(strategy_type)
        if not isinstance(strategy_type, StrategyType)
        else strategy_type
    )
    klass = _REGISTRY.get(st)
    if klass is None:
        raise ValueError(f"Unknown strategy type: {strategy_type}")
    return klass(config or {})


def available_strategies() -> list[dict]:
    """Metadata for the client's strategy picker."""
    return [
        {
            "type": StrategyType.RULE_BASED.value,
            "name": RuleBasedStrategy.name,
            "config_schema": {
                "use_rsi": {"type": "bool", "default": True},
                "rsi_period": {"type": "int", "default": 14},
                "rsi_oversold": {"type": "float", "default": 30},
                "rsi_overbought": {"type": "float", "default": 70},
                "use_macd": {"type": "bool", "default": True},
                "use_ma_cross": {"type": "bool", "default": True},
                "ma_fast": {"type": "int", "default": 20},
                "ma_slow": {"type": "int", "default": 50},
            },
        },
        {
            "type": StrategyType.LLM.value,
            "name": LLMStrategy.name,
            "config_schema": {
                "model": {"type": "str", "default": "claude-opus-4-8"},
                "guidance": {"type": "str", "default": ""},
            },
        },
    ]
