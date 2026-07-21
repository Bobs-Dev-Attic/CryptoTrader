"""End-to-end API tests for the paper-trading happy path."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_strategies_are_listed(client):
    resp = client.get("/api/agents/strategies")
    assert resp.status_code == 200
    types = {s["type"] for s in resp.json()}
    assert {"rule_based", "llm"} <= types


def test_auth_required_for_agents(client):
    assert client.get("/api/agents").status_code == 401


def test_create_and_run_paper_agent(client, auth_headers, fake_adapter):
    # Create a paper agent (rule-based, RSI disabled so uptrend => BUY).
    payload = {
        "name": "BTC momentum",
        "exchange": "kraken",
        "symbol": "BTC/USD",
        "strategy_type": "rule_based",
        "strategy_config": {"use_rsi": False},
        "trade_mode": "paper",
        "order_size_quote": 1000.0,
        "paper_balance_quote": 10_000.0,
    }
    resp = client.post("/api/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    agent_id = resp.json()["id"]

    # Run one evaluation -> should BUY on the uptrend feed.
    resp = client.post(f"/api/agents/{agent_id}/run", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    signal = resp.json()
    assert signal["action"] == "buy"

    # Detail should now show a position and a trade.
    resp = client.get(f"/api/agents/{agent_id}", headers=auth_headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["position"]["quantity"] > 0
    assert len(detail["recent_trades"]) == 1
    assert detail["recent_trades"][0]["side"] == "buy"


def test_live_agent_requires_account(client, auth_headers):
    payload = {
        "name": "Live no account",
        "exchange": "kraken",
        "symbol": "BTC/USD",
        "strategy_type": "rule_based",
        "trade_mode": "live",
    }
    resp = client.post("/api/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 400
    assert "account" in resp.json()["detail"].lower()


def test_account_secrets_not_exposed(client, auth_headers):
    payload = {
        "exchange": "coinbase",
        "label": "my coinbase",
        "api_key": "PUBLICKEY",
        "api_secret": "SUPERSECRET",
    }
    resp = client.post("/api/accounts", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "SUPERSECRET" not in str(body)
    assert body["has_credentials"] is True
