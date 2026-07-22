"""Public market-data endpoints (candles + ticker) used by charts/config UI."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..enums import ExchangeId
from ..exchanges import get_adapter
from ..schemas import CandleOut

router = APIRouter(prefix="/api/market", tags=["market"])


# Connection metadata used by the app's setup wizard.
EXCHANGE_META: dict[str, dict] = {
    "kraken": {
        "name": "Kraken",
        "needs_passphrase": False,
        "docs_url": "https://support.kraken.com/hc/en-us/articles/360000919966",
        "sample_symbol": "BTC/USD",
        "permissions": ["Query Funds", "Create & Modify Orders"],
        "tip": "Do NOT enable Withdraw. Consider restricting the key to your IP.",
    },
    "binance": {
        "name": "Binance",
        "needs_passphrase": False,
        "docs_url": "https://www.binance.com/en/support/faq/how-to-create-api-360002502072",
        "sample_symbol": "BTC/USDT",
        "permissions": ["Enable Reading", "Enable Spot & Margin Trading"],
        "tip": "Disable withdrawals on the API key. Use an IP allowlist if possible.",
    },
    "coinbase": {
        "name": "Coinbase",
        "needs_passphrase": False,
        "docs_url": "https://docs.cdp.coinbase.com/advanced-trade/docs/auth",
        "sample_symbol": "BTC/USD",
        "permissions": ["Trade", "View"],
        "key_format": "cdp",
        "tip": (
            "Create a Secret API key and choose the ECDSA algorithm (NOT Ed25519 — "
            "it isn't supported). Paste the key 'name' (organizations/.../apiKeys/...) "
            "as the API key, and the whole 'privateKey' as the API secret. No "
            "passphrase. Grant Trade + View only — never Transfer."
        ),
    },
    "robinhood": {
        "name": "Robinhood",
        "needs_passphrase": False,
        "docs_url": "https://docs.robinhood.com/crypto/trading/",
        "sample_symbol": "BTC/USD",
        "permissions": [],
        "tip": "Live trading isn't supported in this build — Robinhood agents run in paper mode.",
    },
}


@router.get("/exchanges")
def list_exchanges() -> list[dict]:
    result = []
    for e in ExchangeId:
        meta = EXCHANGE_META.get(e.value, {})
        result.append(
            {
                "id": e.value,
                "name": meta.get("name", e.value.capitalize()),
                "supports_live": get_adapter(e).supports_live,
                "needs_passphrase": meta.get("needs_passphrase", False),
                "docs_url": meta.get("docs_url", ""),
                "sample_symbol": meta.get("sample_symbol", "BTC/USD"),
                "permissions": meta.get("permissions", []),
                "tip": meta.get("tip", ""),
                "key_format": meta.get("key_format", "key_secret"),
            }
        )
    return result


@router.get("/candles", response_model=list[CandleOut])
def candles(
    exchange: ExchangeId,
    symbol: str = Query(..., examples=["BTC/USD"]),
    timeframe: str = "1h",
    limit: int = Query(200, ge=10, le=1000),
) -> list[CandleOut]:
    adapter = get_adapter(exchange)
    try:
        rows = adapter.fetch_ohlcv(symbol, timeframe, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data error: {exc}")
    return [CandleOut(**row.__dict__) for row in rows]


@router.get("/tickers")
def tickers(
    exchange: ExchangeId,
    symbols: str = Query(..., description="Comma-separated, e.g. BTC/USD,ETH/USD"),
) -> list[dict]:
    """Batch price + 24h change for a set of symbols (powers the dashboard ticker)."""
    syms = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    if not syms:
        return []
    adapter = get_adapter(exchange)
    try:
        return adapter.fetch_price_tickers(syms)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data error: {exc}")


@router.get("/ticker")
def ticker(exchange: ExchangeId, symbol: str) -> dict:
    adapter = get_adapter(exchange)
    try:
        t = adapter.fetch_ticker(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data error: {exc}")
    return {"symbol": t.symbol, "last": t.last, "bid": t.bid, "ask": t.ask, "timestamp": t.timestamp}
