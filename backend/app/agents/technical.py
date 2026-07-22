"""Single-method technical strategies (breakout, mean-reversion, momentum, …).

Each is a self-contained :class:`Strategy` that maps market state to one BUY /
SELL / HOLD decision. They share :func:`_finalize`, which suppresses redundant
actions given the current position (don't buy while already in, don't sell while
flat) — mirroring the rule-based strategy's behaviour.
"""
from __future__ import annotations

from ..enums import SignalAction
from . import indicators as ind
from .base import Strategy, StrategyContext, StrategyDecision


def _finalize(
    action: SignalAction,
    confidence: float,
    rationale: str,
    ctx: StrategyContext,
    details: dict,
) -> StrategyDecision:
    if action == SignalAction.BUY and ctx.has_position:
        action, rationale = SignalAction.HOLD, "Bullish but already in position."
    elif action == SignalAction.SELL and not ctx.has_position:
        action, rationale = SignalAction.HOLD, "Bearish but no position to exit."
    return StrategyDecision(action=action, confidence=round(confidence, 2), rationale=rationale, details=details)


def _need(ctx: StrategyContext, bars: int) -> StrategyDecision | None:
    if len(ctx.closes) < bars:
        return StrategyDecision(SignalAction.HOLD, 0.0, "Not enough history yet.")
    return None


class DonchianBreakoutStrategy(Strategy):
    name = "Donchian breakout (trend)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        period = int(self.config.get("period", 20))
        guard = _need(ctx, period + 2)
        if guard:
            return guard
        ch = ind.donchian(ctx.highs, ctx.lows, period)
        if ch is None:
            return StrategyDecision(SignalAction.HOLD, 0.0, "Channel undefined.")
        upper, lower = ch
        price = ctx.current_price
        details = {"upper": round(upper, 2), "lower": round(lower, 2), "price": round(price, 2)}
        if price > upper:
            return _finalize(SignalAction.BUY, 0.7, f"Broke above the {period}-bar high ({upper:.2f}).", ctx, details)
        if price < lower:
            return _finalize(SignalAction.SELL, 0.7, f"Broke below the {period}-bar low ({lower:.2f}).", ctx, details)
        return _finalize(SignalAction.HOLD, 0.3, "Inside the channel.", ctx, details)


class SuperTrendStrategy(Strategy):
    name = "SuperTrend (ATR trend)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        period = int(self.config.get("period", 10))
        mult = float(self.config.get("multiplier", 3.0))
        guard = _need(ctx, period + 2)
        if guard:
            return guard
        st = ind.supertrend(ctx.highs, ctx.lows, ctx.closes, period, mult)
        if st is None:
            return StrategyDecision(SignalAction.HOLD, 0.0, "SuperTrend undefined.")
        value, direction = st
        details = {"supertrend": round(value, 2), "direction": direction}
        if direction > 0:
            return _finalize(SignalAction.BUY, 0.7, f"Uptrend — price above SuperTrend ({value:.2f}).", ctx, details)
        return _finalize(SignalAction.SELL, 0.7, f"Downtrend — price below SuperTrend ({value:.2f}).", ctx, details)


class BollingerReversionStrategy(Strategy):
    name = "Bollinger reversion (mean-revert)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        period = int(self.config.get("period", 20))
        k = float(self.config.get("k", 2.0))
        guard = _need(ctx, period + 1)
        if guard:
            return guard
        b = ind.bollinger(ctx.closes, period, k)
        if b is None:
            return StrategyDecision(SignalAction.HOLD, 0.0, "Bands undefined.")
        mid, upper, lower = b
        price = ctx.current_price
        details = {"mid": round(mid, 2), "upper": round(upper, 2), "lower": round(lower, 2)}
        if price <= lower:
            return _finalize(SignalAction.BUY, 0.65, f"Price at/below lower band ({lower:.2f}) — oversold.", ctx, details)
        if price >= upper:
            return _finalize(SignalAction.SELL, 0.65, f"Price at/above upper band ({upper:.2f}) — overbought.", ctx, details)
        return _finalize(SignalAction.HOLD, 0.3, "Price within the bands.", ctx, details)


class ZScoreReversionStrategy(Strategy):
    name = "Z-score reversion (mean-revert)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        period = int(self.config.get("period", 20))
        threshold = float(self.config.get("threshold", 2.0))
        guard = _need(ctx, period + 1)
        if guard:
            return guard
        z = ind.zscore(ctx.closes, period)
        if z is None:
            return StrategyDecision(SignalAction.HOLD, 0.0, "Z-score undefined.")
        details = {"zscore": round(z, 2), "threshold": threshold}
        conf = min(abs(z) / (threshold * 2), 1.0)
        if z <= -threshold:
            return _finalize(SignalAction.BUY, conf, f"Z={z:.2f} ≤ -{threshold} — stretched below mean.", ctx, details)
        if z >= threshold:
            return _finalize(SignalAction.SELL, conf, f"Z={z:.2f} ≥ {threshold} — stretched above mean.", ctx, details)
        return _finalize(SignalAction.HOLD, 0.3, f"Z={z:.2f} within band.", ctx, details)


class MomentumStrategy(Strategy):
    name = "Momentum (rate of change)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        period = int(self.config.get("period", 10))
        threshold = float(self.config.get("threshold", 2.0))  # percent
        guard = _need(ctx, period + 1)
        if guard:
            return guard
        r = ind.roc(ctx.closes, period)
        if r is None:
            return StrategyDecision(SignalAction.HOLD, 0.0, "ROC undefined.")
        details = {"roc_pct": round(r, 2), "threshold": threshold}
        conf = min(abs(r) / (threshold * 2), 1.0)
        if r >= threshold:
            return _finalize(SignalAction.BUY, conf, f"Momentum +{r:.2f}% over {period} bars.", ctx, details)
        if r <= -threshold:
            return _finalize(SignalAction.SELL, conf, f"Momentum {r:.2f}% over {period} bars.", ctx, details)
        return _finalize(SignalAction.HOLD, 0.3, f"Momentum {r:.2f}% below threshold.", ctx, details)


class ADXTrendStrategy(Strategy):
    name = "ADX trend filter (DI cross)"

    def decide(self, ctx: StrategyContext) -> StrategyDecision:
        period = int(self.config.get("period", 14))
        adx_min = float(self.config.get("adx_min", 25.0))
        guard = _need(ctx, 2 * period + 1)
        if guard:
            return guard
        res = ind.adx(ctx.highs, ctx.lows, ctx.closes, period)
        if res is None:
            return StrategyDecision(SignalAction.HOLD, 0.0, "ADX undefined.")
        adx_val, plus_di, minus_di = res
        details = {"adx": round(adx_val, 1), "plus_di": round(plus_di, 1), "minus_di": round(minus_di, 1)}
        conf = min(adx_val / 50.0, 1.0)
        if adx_val < adx_min:
            return _finalize(SignalAction.HOLD, 0.2, f"Weak trend (ADX {adx_val:.0f} < {adx_min:.0f}).", ctx, details)
        if plus_di > minus_di:
            return _finalize(SignalAction.BUY, conf, f"Strong uptrend (ADX {adx_val:.0f}, +DI>-DI).", ctx, details)
        return _finalize(SignalAction.SELL, conf, f"Strong downtrend (ADX {adx_val:.0f}, -DI>+DI).", ctx, details)
