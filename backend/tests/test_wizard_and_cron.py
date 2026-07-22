"""Tests for the credential-validation endpoint and the internal cron tick."""
from app.config import settings


def test_exchanges_expose_wizard_metadata(client):
    resp = client.get("/api/market/exchanges")
    assert resp.status_code == 200
    by_id = {e["id"]: e for e in resp.json()}
    # Coinbase now uses key-pair (CDP) keys — no passphrase.
    assert by_id["coinbase"]["needs_passphrase"] is False
    assert by_id["coinbase"]["key_format"] == "cdp"
    assert by_id["kraken"]["needs_passphrase"] is False
    # Robinhood is paper-only.
    assert by_id["robinhood"]["supports_live"] is False
    assert by_id["kraken"]["docs_url"].startswith("http")


def test_normalize_secret_pkcs8_to_sec1():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    from app.exchanges.ccxt_adapter import normalize_secret

    key = ec.generate_private_key(ec.SECP256R1())
    pkcs8 = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,  # -----BEGIN PRIVATE KEY-----
        serialization.NoEncryption(),
    ).decode()

    # PKCS#8 is rewritten to the SEC1 header ccxt requires.
    assert "BEGIN EC PRIVATE KEY" in normalize_secret(pkcs8)
    # JSON-escaped newlines are also handled.
    out = normalize_secret(pkcs8.replace("\n", "\\n"))
    assert "BEGIN EC PRIVATE KEY" in out and "\\n" not in out
    # Non-PEM secrets (HMAC keys) pass through untouched.
    assert normalize_secret("plain-hmac-secret") == "plain-hmac-secret"

    # A PKCS#8 PEM with its newlines stripped (single-line paste) is repaired.
    mangled = pkcs8.replace("\n", " ")
    assert "BEGIN EC PRIVATE KEY" in normalize_secret(mangled)


def test_ed25519_key_detection():
    import base64

    from app.exchanges.ccxt_adapter import looks_like_ed25519_key

    ed_b64 = base64.b64encode(b"\x01" * 64).decode()  # ~88-char base64, no PEM
    assert looks_like_ed25519_key(ed_b64) is True
    assert looks_like_ed25519_key("-----BEGIN EC PRIVATE KEY-----\nabc\n-----END EC PRIVATE KEY-----") is False
    assert looks_like_ed25519_key("short") is False


def test_validate_coinbase_ed25519_gives_guidance(client, auth_headers):
    import base64

    ed_b64 = base64.b64encode(b"\x02" * 64).decode()
    resp = client.post(
        "/api/accounts/validate",
        json={"exchange": "coinbase", "api_key": "organizations/a/apiKeys/b", "api_secret": ed_b64},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "ecdsa" in body["message"].lower()


def test_batch_tickers_endpoint(client, monkeypatch):
    from app.api import market as market_api

    class FakeTickerAdapter:
        def fetch_price_tickers(self, symbols):
            return [{"symbol": s, "last": 100.0, "change_pct": 1.5} for s in symbols]

    monkeypatch.setattr(market_api, "get_adapter", lambda *a, **k: FakeTickerAdapter())
    resp = client.get("/api/market/tickers?exchange=kraken&symbols=BTC/USD,ETH/USD")
    assert resp.status_code == 200
    data = resp.json()
    assert [d["symbol"] for d in data] == ["BTC/USD", "ETH/USD"]
    assert data[0]["change_pct"] == 1.5


def test_batch_tickers_empty_symbols(client):
    resp = client.get("/api/market/tickers?exchange=kraken&symbols=")
    assert resp.status_code == 200
    assert resp.json() == []


def test_validate_without_keys_allows_paper(client, auth_headers):
    resp = client.post(
        "/api/accounts/validate",
        json={"exchange": "kraken", "api_key": "", "api_secret": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["authenticated"] is False


def test_validate_robinhood_is_paper(client, auth_headers):
    resp = client.post(
        "/api/accounts/validate",
        json={"exchange": "robinhood"},
        headers=auth_headers,
    )
    assert resp.json()["authenticated"] is False
    assert "paper" in resp.json()["message"].lower()


def test_validate_bad_keys_reports_failure(client, auth_headers, monkeypatch):
    # Force the adapter's fetch_balance to raise, simulating bad credentials.
    from app.api import accounts as accounts_api

    class BadAdapter:
        def fetch_balance(self):
            raise ValueError("invalid key")

    monkeypatch.setattr(accounts_api, "get_adapter", lambda *a, **k: BadAdapter())
    resp = client.post(
        "/api/accounts/validate",
        json={"exchange": "kraken", "api_key": "x", "api_secret": "y"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is False


def test_cron_tick_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_cron_secret", "s3cret")
    # Missing secret -> 401.
    assert client.post("/api/internal/tick").status_code == 401
    # Correct bearer -> 200.
    ok = client.post("/api/internal/tick", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
    assert "count" in ok.json()
