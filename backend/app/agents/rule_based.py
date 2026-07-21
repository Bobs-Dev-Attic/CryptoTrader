"""A configurable rule-based strategy driven by classic technical indicators.

Signals combine three optional sub-rules — RSI reversion, MACD crossover, and a
fast/slow moving-average crossover. Each enabled rule casts a BUY/SELL/HOLD
vote; the aggregate decides the action, and vote agreement sets the confidence.

Config keys (all optional, sensible defaults):
    use_rsi (bool=True), rsi_period (int=14),
        rsi_oversold (float=30), rsi_overbought (float=70)
    use_macd (bool=True), macd_fast (12), macd_slow (26), macd_signal (9)
    use_ma_cross (bool=True), ma_fast (int=20), ma_slow (int=50)
"""
from __future__ import annotations

from ..enums import SignalAction
from . import indicators as ind
from .base import Strategy, StrategyContext, StrategyDecision


class RuleBasedStrategy(Strategy):
    name = "Rule-based (RSI / MACD / MA cross)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        cfg = self.config
        closes = ctx.closes
        if len(closes) < 30:
            return StrategyDecision(
                SignalAction.HOLD,
                confidence=0.0,
                rationale="Not enough history to evaluate indicators.",
            )

        votes: list[int] = []  # +1 buy, -1 sell, 0 hold
        details: dict = {}

        # --- RSI mean-reversion --------------------------------------- #
        if cfg.get("use_rsi", True):
            period = int(cfg.get("rsi_period", 14))
            oversold = float(cfg.get("rsi_oversold", 30))
            overbought = float(cfg.get("rsi_overbought", 70))
            rsi_val = ind.rsi(closes, period)
            details["rsi"] = round(rsi_val, 2) if rsi_val is not None else None
            if rsi_val is not None:
                if rsi_val <= oversold:
                    votes.append(1)
                elif rsi_val >= overbought:
                    votes.append(-1)
                else:
                    votes.append(0)

        # --- MACD crossover ------------------------------------------- #
        if cfg.get("use_macd", True):
            m = ind.macd(
                closes,
                int(cfg.get("macd_fast", 12)),
                int(cfg.get("macd_slow", 26)),
                int(cfg.get("macd_signal", 9)),
            )
            if m is not None:
                macd_line, signal_line, hist = m
                details["macd"] = {
                    "macd": round(macd_line, 6),
                    "signal": round(signal_line, 6),
                    "hist": round(hist, 6),
                }
                votes.append(1 if hist > 0 else -1 if hist < 0 else 0)

        # --- Moving-average crossover --------------------------------- #
        if cfg.get("use_ma_cross", True):
            fast_p = int(cfg.get("ma_fast", 20))
            slow_p = int(cfg.get("ma_slow", 50))
            fast_ma = ind.sma(closes, fast_p)
            slow_ma = ind.sma(closes, slow_p)
            details["ma_fast"] = round(fast_ma, 2) if fast_ma else None
            details["ma_slow"] = round(slow_ma, 2) if slow_ma else None
            if fast_ma is not None and slow_ma is not None:
                votes.append(1 if fast_ma > slow_ma else -1 if fast_ma < slow_ma else 0)

        if not votes:
            return StrategyDecision(
                SignalAction.HOLD, 0.0, "No rules enabled.", details
            )

        score = sum(votes)
        agreement = abs(score) / len(votes)

        if score > 0:
            action = SignalAction.BUY
            rationale = f"{score}/{len(votes)} indicators bullish."
        elif score < 0:
            action = SignalAction.SELL
            rationale = f"{-score}/{len(votes)} indicators bearish."
        else:
            action = SignalAction.HOLD
            rationale = "Indicators are mixed / neutral."

        # Suppress redundant actions given current position.
        if action == SignalAction.BUY and ctx.has_position:
            action, rationale = SignalAction.HOLD, "Bullish but already in position."
        elif action == SignalAction.SELL and not ctx.has_position:
            action, rationale = SignalAction.HOLD, "Bearish but no position to exit."

        return StrategyDecision(
            action=action,
            confidence=round(agreement, 2),
            rationale=rationale,
            details=details,
        )
