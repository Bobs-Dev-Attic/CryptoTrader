"""Pytest fixtures: isolated temp DB, disabled scheduler, and a fake exchange."""
import os
import tempfile

# Configure the app environment BEFORE importing anything from app.*
_TMP = tempfile.mkdtemp(prefix="cryptotrader-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP}/test.db")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("JWT_SECRET", "test-secret")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.exchanges.base import Candle, ExchangeAdapter, Ticker  # noqa: E402
from app.main import app  # noqa: E402


class FakeAdapter(ExchangeAdapter):
    """Deterministic uptrend feed for tests; supports_live off (paper only)."""

    supports_live = True

    def fetch_ohlcv(self, symbol, timeframe="1h", limit=200):
        closes = [100.0 + i for i in range(80)]
        return [
            Candle(timestamp=i * 3600_000, open=c, high=c + 1, low=c - 1, close=c, volume=1.0)
            for i, c in enumerate(closes)
        ]

    def fetch_ticker(self, symbol):
        return Ticker(symbol=symbol, last=179.0)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fake_adapter(monkeypatch):
    from app.agents import runner

    monkeypatch.setattr(runner, "get_adapter", lambda *a, **k: FakeAdapter())
    return FakeAdapter()


@pytest.fixture
def auth_headers(client):
    import uuid

    email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(
        "/api/auth/register", json={"email": email, "password": "password123"}
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
