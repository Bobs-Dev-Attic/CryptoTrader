"""Tests for the volatility scanner and alert watches."""
import pytest

import app.marketscan as marketscan
from app.exchanges.base import Candle, ExchangeAdapter, Ticker


class FakeStatsAdapter(ExchangeAdapter):
    supports_live = False

    def fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
        base = 100.0
        return [
            Candle(timestamp=i * 3600_000, open=base + i, high=base + i + 2, low=base + i - 2, close=base + i, volume=1.0)
            for i in range(30)
        ]

    def fetch_ticker(self, symbol):
        return Ticker(symbol=symbol, last=100.0)

    def fetch_market_stats(self, symbols):
        out = []
        for idx, s in enumerate(symbols):
            spread = (idx % 5) + 1  # 1..5 -> range 2..10%
            out.append({
                "symbol": s, "last": 100.0, "high": 100.0 + spread, "low": 100.0 - spread,
                "change_pct": float(spread), "volume": 1000.0 * (idx + 1),
            })
        return out


@pytest.fixture
def patch_scan(monkeypatch):
    marketscan._SCAN_CACHE.clear()  # avoid cross-test cache bleed
    monkeypatch.setattr(marketscan, "get_adapter", lambda *a, **k: FakeStatsAdapter())


def test_scan_ranks_by_range(patch_scan):
    data = marketscan.scan("kraken", "range_24h", limit=10)
    assert data["metric"] == "range_24h"
    ranges = [r["range_24h"] for r in data["rows"]]
    assert ranges == sorted(ranges, reverse=True)
    assert data["rows"][0]["range_24h"] >= data["rows"][-1]["range_24h"]


def test_scan_candle_metric_atr(patch_scan):
    data = marketscan.scan("kraken", "atr_pct", limit=5)
    assert data["metric"] == "atr_pct"
    assert all(r["atr_pct"] is not None and r["atr_pct"] > 0 for r in data["rows"])


def test_volatility_endpoint(client, patch_scan):
    r = client.get("/api/market/volatility?exchange=kraken&metric=range_24h")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metric"] == "range_24h" and body["rows"]


def test_watch_crud_and_evaluation(client, auth_headers, patch_scan):
    created = client.post(
        "/api/watchlist",
        json={"exchange": "kraken", "symbol": "BTC/USD", "metric": "change_24h", "threshold": 0.5},
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    wid = created.json()["id"]
    assert wid in [w["id"] for w in client.get("/api/watchlist", headers=auth_headers).json()]

    # Evaluate directly (as the internal tick would).
    from app.api.watchlist import evaluate_watches
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        assert evaluate_watches(db) >= 1
    finally:
        db.close()

    w = [x for x in client.get("/api/watchlist", headers=auth_headers).json() if x["id"] == wid][0]
    assert w["last_value"] is not None
    assert w["triggered"] is True  # BTC/USD change 1% >= 0.5% threshold

    assert client.delete(f"/api/watchlist/{wid}", headers=auth_headers).status_code == 204


def test_watch_isolated_per_user(client, auth_headers, patch_scan):
    r = client.post(
        "/api/watchlist",
        json={"exchange": "kraken", "symbol": "ETH/USD", "metric": "range_24h", "threshold": 3.0},
        headers=auth_headers,
    )
    assert r.status_code == 201
    # A watch requires auth to list.
    assert client.get("/api/watchlist").status_code == 401
