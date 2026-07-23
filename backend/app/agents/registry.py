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


def available_strategies() -> list[dict]:
    """Metadata for the client's strategy picker.

    Beyond ``config_schema`` (which drives a generic form), each entry carries
    decision-support context so a user can pick the right strategy:
      kind        — the family it belongs to
      best_for    — market conditions where it shines
      avoid_when  — conditions where it struggles
      difficulty  — rough experience level
    """
    return [
        {
            "type": StrategyType.RULE_BASED.value,
            "name": RuleBasedStrategy.name,
            "kind": "Multi-indicator",
            "difficulty": "Beginner",
            "description": "Combines RSI, MACD and MA-cross votes; acts only when they agree.",
            "best_for": "A balanced first bot. Because it waits for several indicators to agree, it trades less often but with more conviction — a good default while you learn.",
            "avoid_when": "You want quick reactions to every move; the agreement filter can be slow to enter and exit.",
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
            "kind": "AI analyst",
            "difficulty": "Beginner",
            "description": "Claude weighs the market like an analyst, following your plain-English guidance.",
            "best_for": "Following plain-English instructions and weighing mixed or unusual signals the way a human analyst would.",
            "avoid_when": "You need fully deterministic, free, low-latency decisions — each evaluation costs a little and needs an AI key configured on the server (without one it just holds).",
            "config_schema": {
                "model": {"type": "str", "default": "claude-opus-4-8"},
                "guidance": {"type": "str", "default": ""},
            },
        },
        {
            "type": StrategyType.DONCHIAN.value,
            "name": DonchianBreakoutStrategy.name,
            "kind": "Trend-following",
            "difficulty": "Intermediate",
            "description": "Buys when price breaks above the N-bar high; sells when it breaks the N-bar low.",
            "best_for": "Catching the start of strong, sustained moves. Shines in trending markets that keep making new highs or lows.",
            "avoid_when": "Sideways / choppy markets, where breakouts routinely fail and reverse (whipsaw).",
            "config_schema": {
                "period": _p("int", 20, "Channel period", "How many bars form the high/low channel. Larger = fewer, stronger breakouts."),
            },
        },
        {
            "type": StrategyType.SUPERTREND.value,
            "name": SuperTrendStrategy.name,
            "kind": "Trend-following",
            "difficulty": "Intermediate",
            "description": "Follows an ATR-based trend line; long above it, flat/short below it.",
            "best_for": "Riding an established trend while ignoring normal wiggles — the ATR band widens or tightens with how volatile the market is.",
            "avoid_when": "Range-bound markets, where the line flips back and forth and racks up small losses.",
            "config_schema": {
                "period": _p("int", 10, "ATR period", "Bars used for the volatility (ATR) estimate."),
                "multiplier": _p("float", 3.0, "ATR multiplier", "Band width in ATRs. Higher = slower to flip, fewer whipsaws."),
            },
        },
        {
            "type": StrategyType.BOLLINGER.value,
            "name": BollingerReversionStrategy.name,
            "kind": "Mean-reversion",
            "difficulty": "Intermediate",
            "description": "Buys dips to the lower band, sells rallies to the upper band.",
            "best_for": "Calm, range-bound markets that oscillate around an average — it fades stretched moves back toward the middle.",
            "avoid_when": "Strong trends, where price 'walks the band' and buying dips keeps losing.",
            "config_schema": {
                "period": _p("int", 20, "Period", "Bars for the moving average and standard deviation."),
                "k": _p("float", 2.0, "Std-dev width", "Band distance in standard deviations."),
            },
        },
        {
            "type": StrategyType.ZSCORE.value,
            "name": ZScoreReversionStrategy.name,
            "kind": "Mean-reversion",
            "difficulty": "Advanced",
            "description": "Trades when price is a set number of standard deviations from its mean.",
            "best_for": "Fading statistically extreme moves back toward the average in a stable, range-bound market.",
            "avoid_when": "Trending or news-driven markets that keep extending — 'extreme' can get more extreme.",
            "config_schema": {
                "period": _p("int", 20, "Lookback", "Bars for the rolling mean/standard deviation."),
                "threshold": _p("float", 2.0, "Z threshold", "Std-devs from the mean that trigger a trade."),
            },
        },
        {
            "type": StrategyType.MOMENTUM.value,
            "name": MomentumStrategy.name,
            "kind": "Momentum",
            "difficulty": "Intermediate",
            "description": "Buys strength and sells weakness once the move exceeds a percent threshold.",
            "best_for": "Fast-moving markets with follow-through — it joins a move that's already underway.",
            "avoid_when": "Quiet, directionless markets, where it can buy tops and sell bottoms on false starts.",
            "config_schema": {
                "period": _p("int", 10, "Lookback", "Bars over which to measure percent change."),
                "threshold": _p("float", 2.0, "Threshold %", "Percent move required to act."),
            },
        },
        {
            "type": StrategyType.ADX.value,
            "name": ADXTrendStrategy.name,
            "kind": "Trend-following (filtered)",
            "difficulty": "Advanced",
            "description": "Trades trend direction, but only when ADX confirms the trend is strong.",
            "best_for": "Avoiding chop — it deliberately sits out weak, rangy conditions and only acts when a trend is genuinely strong.",
            "avoid_when": "You want frequent trades; by design it stays flat much of the time.",
            "config_schema": {
                "period": _p("int", 14, "DI/ADX period", "Bars for the directional-movement calculation."),
                "adx_min": _p("float", 25.0, "Min ADX", "Minimum trend strength (ADX) required to trade."),
            },
        },
    ]
