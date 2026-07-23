"""Volatility scanning across a curated universe of liquid coins.

Ranks coins by how volatile they are, using metrics that are cheap to compute
from a single batch ticker call (24h range / 24h move / volume) plus optional
candle-based measures (return volatility, ATR%). Candle metrics fetch OHLCV per
symbol concurrently so a full scan still returns quickly on serverless.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .agents import indicators as ind
from .enums import ExchangeId
from .exchanges import get_adapter

# A hand-picked set of liquid, well-known base assets. The scan tolerates any
# that a given exchange doesn't list (they're simply skipped).
CURATED_BASES = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "AVAX", "LINK", "DOT", "LTC",
    "BCH", "ATOM", "UNI", "ETC", "XLM", "ALGO", "FIL", "APT", "ARB", "OP",
    "NEAR", "INJ", "SUI", "AAVE", "TRX", "MATIC", "SHIB",
]

# Quote currency to pair each base with, per exchange.
_QUOTE = {
    ExchangeId.KRAKEN.value: "USD",
    ExchangeId.COINBASE.value: "USD",
    ExchangeId.ROBINHOOD.value: "USD",
    ExchangeId.BINANCE.value: "USDT",
}

TICKER_METRICS = {"range_24h", "change_24h", "volume"}
CANDLE_METRICS = {"ret_vol", "atr_pct"}
ALL_METRICS = TICKER_METRICS | CANDLE_METRICS


def universe(exchange: str) -> list[str]:
    quote = _QUOTE.get(exchange, "USD")
    return [f"{base}/{quote}" for base in CURATED_BASES]


def _stats(exchange: str) -> dict[str, dict]:
    """Batch 24h stats for the whole universe: {symbol: {last, high, low, change_pct, volume}}."""
    adapter = get_adapter(exchange)
    try:
        rows = adapter.fetch_market_stats(universe(exchange))
    except Exception:
        return {}
    return {r["symbol"]: r for r in rows}


def _ticker_metric(stat: dict, metric: str) -> float | None:
    last = stat.get("last") or 0.0
    if metric == "range_24h":
        hi, lo = stat.get("high"), stat.get("low")
        if hi and lo and last:
            return (hi - lo) / last * 100.0
        return None
    if metric == "change_24h":
        c = stat.get("change_pct")
        return abs(c) if c is not None else None
    if metric == "volume":
        return stat.get("volume")
    return None


def _candle_metric(exchange: str, symbol: str, metric: str) -> float | None:
    """Fetch this symbol's recent candles and compute a candle-based metric.

    A fresh adapter per call keeps ccxt clients from being shared across threads.
    """
    try:
        adapter = get_adapter(exchange)
        candles = adapter.fetch_ohlcv(symbol, "1h", limit=48)
    except Exception:
        return None
    closes = [c.close for c in candles]
    if len(closes) < 15:
        return None
    last = closes[-1]
    if metric == "ret_vol":
        rets = [(b - a) / a for a, b in zip(closes, closes[1:]) if a > 0]
        if len(rets) < 2:
            return None
        mean = sum(rets) / len(rets)
        return (sum((r - mean) ** 2 for r in rets) / len(rets)) ** 0.5 * 100.0
    if metric == "atr_pct":
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        atr = ind.atr(highs, lows, closes, 14)
        if atr is None or last <= 0:
            return None
        return atr / last * 100.0
    return None


def scan(exchange: str, metric: str = "range_24h", limit: int = 25) -> dict:
    """Return the universe ranked by ``metric`` (most volatile first)."""
    if metric not in ALL_METRICS:
        metric = "range_24h"
    stats = _stats(exchange)
    symbols = [s for s in universe(exchange) if s in stats]

    # Candle-based metric values (concurrent OHLCV fetches).
    candle_vals: dict[str, float | None] = {}
    if metric in CANDLE_METRICS and symbols:
        with ThreadPoolExecutor(max_workers=8) as pool:
            candle_vals = dict(
                zip(symbols, pool.map(lambda s: _candle_metric(exchange, s, metric), symbols))
            )

    rows: list[dict] = []
    for s in symbols:
        stat = stats[s]
        row = {
            "symbol": s,
            "base": s.split("/")[0],
            "last": stat.get("last"),
            "range_24h": _ticker_metric(stat, "range_24h"),
            "change_24h": stat.get("change_pct"),
            "volume": stat.get("volume"),
            "ret_vol": None,
            "atr_pct": None,
        }
        if metric in CANDLE_METRICS:
            row[metric] = candle_vals.get(s)
        rows.append(row)

    def sort_key(r: dict) -> float:
        v = r.get(metric)
        if metric == "change_24h" and v is not None:
            v = abs(v)
        return v if isinstance(v, (int, float)) else float("-inf")

    rows.sort(key=sort_key, reverse=True)
    return {"exchange": exchange, "metric": metric, "rows": rows[:limit]}


def symbol_value(exchange: str, symbol: str, metric: str, stats: dict | None = None) -> float | None:
    """Compute one symbol's metric value (used by the alert watcher)."""
    if metric in CANDLE_METRICS:
        return _candle_metric(exchange, symbol, metric)
    stat = (stats or {}).get(symbol)
    if stat is None:
        adapter = get_adapter(exchange)
        try:
            found = adapter.fetch_market_stats([symbol])
            stat = found[0] if found else None
        except Exception:
            stat = None
    if stat is None:
        return None
    if metric == "change_24h":
        c = stat.get("change_pct")
        return abs(c) if c is not None else None
    return _ticker_metric(stat, metric)
