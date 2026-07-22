"""Maps a StrategyType to a concrete Strategy implementation."""
from __future__ import annotations

from ..enums import StrategyType
from .base import Strategy
from .llm_agent import LLMStrategy
from .rule_based import RuleBasedStrategy
from .technical import (
    ADXTrendStrategy,
    BollingerReversionStrategy,
    DonchianBreakoutStrategy,
    MomentumStrategy,
    SuperTrendStrategy,
    ZScoreReversionStrategy,
)

_REGISTRY: dict[StrategyType, type[Strategy]] = {
    StrategyType.RULE_BASED: RuleBasedStrategy,
    StrategyType.LLM: LLMStrategy,
    StrategyType.DONCHIAN: DonchianBreakoutStrategy,
    StrategyType.SUPERTREND: SuperTrendStrategy,
    StrategyType.BOLLINGER: BollingerReversionStrategy,
    StrategyType.ZSCORE: ZScoreReversionStrategy,
    StrategyType.MOMENTUM: MomentumStrategy,
    StrategyType.ADX: ADXTrendStrategy,
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


def _p(type_: str, default, label: str, help: str) -> dict:
    """One config-parameter descriptor for the client's generic form renderer."""
    return {"type": type_, "default": default, "label": label, "help": help}


# Short plain-language blurb shown under each strategy in the picker.
_KIND_TREND = "Trend-following: rides sustained moves."
_KIND_REVERT = "Mean-reversion: fades stretched moves back toward average."
_KIND_MOMENTUM = "Momentum: buys strength, sells weakness."


def available_strategies() -> list[dict]:
    """Metadata for the client's strategy picker (schema drives a generic form)."""
    return [
        {
            "type": StrategyType.RULE_BASED.value,
            "name": RuleBasedStrategy.name,
            "description": "Combines RSI, MACD and MA-cross votes; acts when they agree.",
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
            "description": "Claude weighs the market like an analyst using your guidance.",
            "config_schema": {
                "model": {"type": "str", "default": "claude-opus-4-8"},
                "guidance": {"type": "str", "default": ""},
            },
        },
        {
            "type": StrategyType.DONCHIAN.value,
            "name": DonchianBreakoutStrategy.name,
            "description": f"{_KIND_TREND} Buys N-bar highs, sells N-bar lows.",
            "config_schema": {
                "period": _p("int", 20, "Channel period", "How many bars form the high/low channel. Larger = fewer, stronger breakouts."),
            },
        },
        {
            "type": StrategyType.SUPERTREND.value,
            "name": SuperTrendStrategy.name,
            "description": f"{_KIND_TREND} Follows an ATR-based trend line.",
            "config_schema": {
                "period": _p("int", 10, "ATR period", "Bars used for the volatility (ATR) estimate."),
                "multiplier": _p("float", 3.0, "ATR multiplier", "Band width in ATRs. Higher = slower to flip, fewer whipsaws."),
            },
        },
        {
            "type": StrategyType.BOLLINGER.value,
            "name": BollingerReversionStrategy.name,
            "description": f"{_KIND_REVERT} Buys the lower band, sells the upper band.",
            "config_schema": {
                "period": _p("int", 20, "Period", "Bars for the moving average and standard deviation."),
                "k": _p("float", 2.0, "Std-dev width", "Band distance in standard deviations."),
            },
        },
        {
            "type": StrategyType.ZSCORE.value,
            "name": ZScoreReversionStrategy.name,
            "description": f"{_KIND_REVERT} Buys/sells when price is N std-devs from its mean.",
            "config_schema": {
                "period": _p("int", 20, "Lookback", "Bars for the rolling mean/standard deviation."),
                "threshold": _p("float", 2.0, "Z threshold", "Std-devs from the mean that trigger a trade."),
            },
        },
        {
            "type": StrategyType.MOMENTUM.value,
            "name": MomentumStrategy.name,
            "description": f"{_KIND_MOMENTUM} Trades when rate-of-change exceeds a threshold.",
            "config_schema": {
                "period": _p("int", 10, "Lookback", "Bars over which to measure percent change."),
                "threshold": _p("float", 2.0, "Threshold %", "Percent move required to act."),
            },
        },
        {
            "type": StrategyType.ADX.value,
            "name": ADXTrendStrategy.name,
            "description": f"{_KIND_TREND} Only trades when ADX confirms a strong trend.",
            "config_schema": {
                "period": _p("int", 14, "DI/ADX period", "Bars for the directional-movement calculation."),
                "adx_min": _p("float", 25.0, "Min ADX", "Minimum trend strength (ADX) required to trade."),
            },
        },
    ]
