"""Public market-data endpoints (candles + ticker) used by charts/config UI."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..enums import ExchangeId
from ..exchanges import get_adapter
from ..schemas import CandleOut

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/exchanges")
def list_exchanges() -> list[dict]:
    return [
        {"id": e.value, "name": e.value.capitalize(), "supports_live": get_adapter(e).supports_live}
        for e in ExchangeId
    ]


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


@router.get("/ticker")
def ticker(exchange: ExchangeId, symbol: str) -> dict:
    adapter = get_adapter(exchange)
    try:
        t = adapter.fetch_ticker(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Market data error: {exc}")
    return {"symbol": t.symbol, "last": t.last, "bid": t.bid, "ask": t.ask, "timestamp": t.timestamp}
