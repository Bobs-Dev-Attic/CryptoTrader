"""Abstract exchange adapter interface and shared data types."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Candle:
    """A single OHLCV candle. Timestamp is epoch milliseconds (UTC)."""

    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Ticker:
    symbol: str
    last: float
    bid: float = 0.0
    ask: float = 0.0
    timestamp: int = 0


@dataclass
class OrderResult:
    """Result of a submitted order (paper or live)."""

    side: str
    symbol: str
    quantity: float
    price: float
    cost: float
    fee: float = 0.0
    status: str = "filled"
    external_id: str = ""
    note: str = ""
    raw: dict = field(default_factory=dict)


class ExchangeAdapter(abc.ABC):
    """Common surface every exchange integration implements.

    Market-data methods (``fetch_ohlcv``, ``fetch_ticker``) are public and work
    without credentials. Account methods (``fetch_balance``,
    ``create_market_order``) require valid API credentials and are only used for
    LIVE trading.
    """

    #: Whether this adapter can place real orders.
    supports_live: bool = True

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
    ) -> None:
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase

    # --- Market data (public) --------------------------------------------- #
    @abc.abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> list[Candle]:
        """Return recent candles, oldest first."""

    @abc.abstractmethod
    def fetch_ticker(self, symbol: str) -> Ticker:
        """Return the latest ticker for a symbol."""

    def fetch_price_tickers(self, symbols: list[str]) -> list[dict]:
        """Return [{symbol, last, change_pct}] for many symbols.

        Default implementation fetches each symbol individually (no 24h change).
        Adapters with a batch endpoint should override for efficiency.
        """
        out: list[dict] = []
        for s in symbols:
            try:
                t = self.fetch_ticker(s)
                out.append({"symbol": s, "last": t.last, "change_pct": None})
            except Exception:
                continue
        return out

    def fetch_market_stats(self, symbols: list[str]) -> list[dict]:
        """Return [{symbol, last, high, low, change_pct, volume}] for many symbols.

        Used by the volatility scanner. Default implementation fetches each
        symbol individually with no 24h high/low; adapters with a batch endpoint
        should override for speed and richer fields.
        """
        out: list[dict] = []
        for s in symbols:
            try:
                t = self.fetch_ticker(s)
                out.append({
                    "symbol": s, "last": t.last, "high": None, "low": None,
                    "change_pct": None, "volume": None,
                })
            except Exception:
                continue
        return out

    # --- Account (private, live only) ------------------------------------- #
    def fetch_balance(self) -> dict[str, float]:
        """Return free balances keyed by asset. Live adapters override."""
        raise NotImplementedError

    def create_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        """Place a live market order. Live adapters override."""
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support live order execution."
        )
