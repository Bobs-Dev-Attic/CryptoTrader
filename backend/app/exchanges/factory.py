"""Factory for constructing exchange adapters from an ExchangeId."""
from __future__ import annotations

from ..enums import ExchangeId
from .base import ExchangeAdapter
from .ccxt_adapter import CcxtAdapter
from .robinhood import RobinhoodAdapter


def get_adapter(
    exchange: str | ExchangeId,
    api_key: str = "",
    api_secret: str = "",
    api_passphrase: str = "",
) -> ExchangeAdapter:
    """Return an adapter for the given exchange, wired with optional credentials."""
    ex = ExchangeId(exchange) if not isinstance(exchange, ExchangeId) else exchange

    if ex == ExchangeId.ROBINHOOD:
        return RobinhoodAdapter(api_key, api_secret, api_passphrase)

    # Kraken / Binance / Coinbase all go through ccxt.
    return CcxtAdapter(
        ex.value,
        api_key=api_key,
        api_secret=api_secret,
        api_passphrase=api_passphrase,
    )
