"""ccxt-backed adapter for Kraken, Binance, and Coinbase."""
from __future__ import annotations

from .base import Candle, ExchangeAdapter, OrderResult, Ticker

# Map our ExchangeId values to ccxt exchange class names.
CCXT_EXCHANGE_MAP: dict[str, str] = {
    "kraken": "kraken",
    "binance": "binance",
    "coinbase": "coinbase",
}


class CcxtAdapter(ExchangeAdapter):
    """Wraps a ccxt exchange instance.

    ccxt is imported lazily so the rest of the app (and the test suite) does not
    hard-depend on network access or the ccxt package being installed.
    """

    supports_live = True

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
        sandbox: bool = False,
    ) -> None:
        super().__init__(api_key, api_secret, api_passphrase)
        self.exchange_id = exchange_id
        self.sandbox = sandbox
        self._client = None  # lazily constructed

    # ------------------------------------------------------------------ #
    @property
    def client(self):
        if self._client is None:
            import ccxt  # local import: heavy, network-oriented dependency

            if self.exchange_id not in CCXT_EXCHANGE_MAP:
                raise ValueError(f"Unsupported ccxt exchange: {self.exchange_id}")
            klass = getattr(ccxt, CCXT_EXCHANGE_MAP[self.exchange_id])
            params: dict = {"enableRateLimit": True}
            if self.api_key:
                params["apiKey"] = self.api_key
            if self.api_secret:
                params["secret"] = self.api_secret
            if self.api_passphrase:
                params["password"] = self.api_passphrase
            client = klass(params)
            if self.sandbox and client.has.get("sandbox"):
                client.set_sandbox_mode(True)
            self._client = client
        return self._client

    # --- Market data --------------------------------------------------- #
    def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 200
    ) -> list[Candle]:
        rows = self.client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return [
            Candle(
                timestamp=int(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
            )
            for r in rows
        ]

    def fetch_ticker(self, symbol: str) -> Ticker:
        t = self.client.fetch_ticker(symbol)
        return Ticker(
            symbol=symbol,
            last=float(t.get("last") or t.get("close") or 0.0),
            bid=float(t.get("bid") or 0.0),
            ask=float(t.get("ask") or 0.0),
            timestamp=int(t.get("timestamp") or 0),
        )

    # --- Account (live) ------------------------------------------------ #
    def fetch_balance(self) -> dict[str, float]:
        bal = self.client.fetch_balance()
        free = bal.get("free", {})
        return {k: float(v) for k, v in free.items() if v}

    def create_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        order = self.client.create_order(symbol, "market", side, quantity)
        filled = float(order.get("filled") or quantity)
        price = float(order.get("average") or order.get("price") or 0.0)
        cost = float(order.get("cost") or filled * price)
        fee = 0.0
        fee_obj = order.get("fee") or {}
        if isinstance(fee_obj, dict):
            fee = float(fee_obj.get("cost") or 0.0)
        return OrderResult(
            side=side,
            symbol=symbol,
            quantity=filled,
            price=price,
            cost=cost,
            fee=fee,
            status=str(order.get("status") or "filled"),
            external_id=str(order.get("id") or ""),
            raw=order,
        )
