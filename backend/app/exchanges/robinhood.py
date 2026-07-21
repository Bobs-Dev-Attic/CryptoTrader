"""Robinhood adapter.

Robinhood Crypto is not exposed through ccxt and its official trading API
requires per-account key-pair auth (`robin_stocks` / the Robinhood Crypto REST
API). Live execution is therefore not wired up in this scaffold — it is a
clearly-marked extension point.

For PAPER trading we still need candles to feed the indicators, so market data
falls back to a public reference exchange (Coinbase) for the same symbol. This
keeps paper agents fully functional while making the live gap explicit.
"""
from __future__ import annotations

from .base import Candle, ExchangeAdapter, OrderResult, Ticker
from .ccxt_adapter import CcxtAdapter

# Public exchange used purely as a price reference for Robinhood paper agents.
REFERENCE_EXCHANGE = "coinbase"


class RobinhoodAdapter(ExchangeAdapter):
    supports_live = False

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
    ) -> None:
        super().__init__(api_key, api_secret, api_passphrase)
        # Reference feed for candles/ticker (public, no credentials needed).
        self._reference = CcxtAdapter(REFERENCE_EXCHANGE)

    def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 200
    ) -> list[Candle]:
        return self._reference.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def fetch_ticker(self, symbol: str) -> Ticker:
        return self._reference.fetch_ticker(symbol)

    def create_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        raise NotImplementedError(
            "Live Robinhood execution is not implemented in this scaffold. "
            "Use PAPER mode for Robinhood, or extend RobinhoodAdapter with the "
            "Robinhood Crypto API (key-pair signed requests) to enable live trades."
        )
