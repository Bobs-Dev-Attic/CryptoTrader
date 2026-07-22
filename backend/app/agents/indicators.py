"""Technical indicators implemented in pure Python (no numpy/pandas at call time).

All functions accept a list/sequence of closing prices (oldest first) and return
either a single latest value or a list aligned to the input length (with leading
``None`` where the indicator is not yet defined).
"""
from __future__ import annotations

from collections.abc import Sequence


def sma(values: Sequence[float], period: int) -> float | None:
    """Simple moving average of the most recent ``period`` values."""
    if period <= 0 or len(values) < period:
        return None
    window = values[-period:]
    return sum(window) / period


def ema_series(values: Sequence[float], period: int) -> list[float]:
    """Exponential moving average series (same length as input)."""
    if not values:
        return []
    k = 2 / (period + 1)
    out: list[float] = [float(values[0])]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def ema(values: Sequence[float], period: int) -> float | None:
    if len(values) < period:
        return None
    return ema_series(values, period)[-1]


def rsi(values: Sequence[float], period: int = 14) -> float | None:
    """Relative Strength Index using Wilder's smoothing. Returns 0..100."""
    if len(values) < period + 1:
        return None

    gains = 0.0
    losses = 0.0
    # Seed with the first `period` deltas.
    for i in range(1, period + 1):
        delta = values[i] - values[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period

    # Wilder-smooth the remainder.
    for i in range(period + 1, len(values)):
        delta = values[i] - values[i - 1]
        gain = max(delta, 0.0)
        loss = max(-delta, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def macd(
    values: Sequence[float],
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[float, float, float] | None:
    """Return (macd_line, signal_line, histogram) at the latest point."""
    if len(values) < slow + signal:
        return None
    fast_e = ema_series(values, fast)
    slow_e = ema_series(values, slow)
    macd_line = [f - s for f, s in zip(fast_e, slow_e)]
    signal_line = ema_series(macd_line, signal)
    hist = macd_line[-1] - signal_line[-1]
    return macd_line[-1], signal_line[-1], hist


def stddev(values: Sequence[float], period: int) -> float | None:
    """Population standard deviation of the most recent ``period`` values."""
    if period <= 1 or len(values) < period:
        return None
    window = values[-period:]
    mean = sum(window) / period
    var = sum((v - mean) ** 2 for v in window) / period
    return var ** 0.5


def bollinger(
    values: Sequence[float], period: int = 20, k: float = 2.0
) -> tuple[float, float, float] | None:
    """Return (middle, upper, lower) Bollinger bands at the latest point."""
    mid = sma(values, period)
    sd = stddev(values, period)
    if mid is None or sd is None:
        return None
    return mid, mid + k * sd, mid - k * sd


def zscore(values: Sequence[float], period: int = 20) -> float | None:
    """How many standard deviations the latest value is from its rolling mean."""
    mid = sma(values, period)
    sd = stddev(values, period)
    if mid is None or sd is None or sd == 0:
        return None
    return (values[-1] - mid) / sd


def roc(values: Sequence[float], period: int = 10) -> float | None:
    """Rate of change (percent) over ``period`` bars."""
    if len(values) <= period:
        return None
    past = values[-period - 1]
    if past == 0:
        return None
    return (values[-1] - past) / past * 100.0


def atr(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> float | None:
    """Average True Range (Wilder) over ``period`` bars."""
    n = len(closes)
    if n < period + 1 or len(highs) != n or len(lows) != n:
        return None
    trs: list[float] = []
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    # Wilder smoothing of the true-range series.
    atr_val = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr_val = (atr_val * (period - 1) + tr) / period
    return atr_val


def donchian(
    highs: Sequence[float], lows: Sequence[float], period: int = 20
) -> tuple[float, float] | None:
    """Return (upper, lower) = highest high / lowest low over ``period`` bars.

    Uses the bars *excluding* the current one, so a close beyond the channel is a
    genuine breakout rather than trivially touching its own extreme.
    """
    if len(highs) < period + 1 or len(lows) < period + 1:
        return None
    return max(highs[-period - 1:-1]), min(lows[-period - 1:-1])


def supertrend(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 10,
    multiplier: float = 3.0,
) -> tuple[float, int] | None:
    """Return (supertrend_value, direction) where direction is +1 (up) / -1 (down).

    A simplified SuperTrend: bands are hl2 ± multiplier*ATR, with the usual
    trend-locking so the line only flips when price closes through the opposite band.
    """
    n = len(closes)
    if n < period + 1:
        return None
    direction = 1
    st = 0.0
    prev_upper = prev_lower = None
    for i in range(period, n):
        sub_h = highs[: i + 1]
        sub_l = lows[: i + 1]
        sub_c = closes[: i + 1]
        a = atr(sub_h, sub_l, sub_c, period)
        if a is None:
            continue
        hl2 = (highs[i] + lows[i]) / 2
        basic_upper = hl2 + multiplier * a
        basic_lower = hl2 - multiplier * a
        # Carry the tighter band forward while the trend persists.
        upper = basic_upper if prev_upper is None else (
            basic_upper if basic_upper < prev_upper or closes[i - 1] > prev_upper else prev_upper
        )
        lower = basic_lower if prev_lower is None else (
            basic_lower if basic_lower > prev_lower or closes[i - 1] < prev_lower else prev_lower
        )
        if closes[i] > upper:
            direction = 1
        elif closes[i] < lower:
            direction = -1
        st = lower if direction == 1 else upper
        prev_upper, prev_lower = upper, lower
    return st, direction


def adx(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    period: int = 14,
) -> tuple[float, float, float] | None:
    """Return (adx, plus_di, minus_di) — Wilder's directional movement system."""
    n = len(closes)
    if n < 2 * period or len(highs) != n or len(lows) != n:
        return None
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    trs: list[float] = []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
        trs.append(
            max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
        )

    def _wilder(seq: list[float]) -> list[float]:
        out = [sum(seq[:period])]
        for v in seq[period:]:
            out.append(out[-1] - out[-1] / period + v)
        return out

    tr_s = _wilder(trs)
    plus_s = _wilder(plus_dm)
    minus_s = _wilder(minus_dm)

    dx: list[float] = []
    for tr_v, p_v, m_v in zip(tr_s, plus_s, minus_s):
        if tr_v == 0:
            dx.append(0.0)
            continue
        pdi = 100 * p_v / tr_v
        mdi = 100 * m_v / tr_v
        denom = pdi + mdi
        dx.append(100 * abs(pdi - mdi) / denom if denom else 0.0)

    if len(dx) < period:
        return None
    adx_val = sum(dx[:period]) / period
    for v in dx[period:]:
        adx_val = (adx_val * (period - 1) + v) / period

    tr_last, p_last, m_last = tr_s[-1], plus_s[-1], minus_s[-1]
    plus_di = 100 * p_last / tr_last if tr_last else 0.0
    minus_di = 100 * m_last / tr_last if tr_last else 0.0
    return adx_val, plus_di, minus_di
