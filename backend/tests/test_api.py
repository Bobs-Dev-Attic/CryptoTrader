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


def test_portfolio_endpoints_and_equity_snapshots(client, auth_headers, fake_adapter):
    # Create a paper agent and run it so an equity snapshot is recorded.
    payload = {
        "name": "PF agent",
        "exchange": "kraken",
        "symbol": "BTC/USD",
        "strategy_type": "rule_based",
        "strategy_config": {"use_rsi": False},
        "trade_mode": "paper",
        "order_size_quote": 1000.0,
        "paper_balance_quote": 10_000.0,
    }
    agent_id = client.post("/api/agents", json=payload, headers=auth_headers).json()["id"]
    client.post(f"/api/agents/{agent_id}/run", headers=auth_headers)

    # Equity history should have at least one point.
    hist = client.get("/api/portfolio/history", headers=auth_headers)
    assert hist.status_code == 200
    assert len(hist.json()) >= 1
    assert "equity" in hist.json()[0] and "t" in hist.json()[0]

    # Per-agent equity curve.
    eq = client.get(f"/api/agents/{agent_id}/equity", headers=auth_headers)
    assert eq.status_code == 200 and len(eq.json()) >= 1

    # Allocation and stats.
    alloc = client.get("/api/portfolio/allocation", headers=auth_headers)
    assert alloc.status_code == 200
    stats = client.get("/api/portfolio/stats", headers=auth_headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["agents"] >= 1
    # Win-rate fields are present (null until there are closed trades).
    for k in ("win_rate", "wins", "losses", "closed_trades", "avg_win", "avg_loss"):
        assert k in body


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


def test_delete_endpoints_return_204(client, auth_headers):
    # Create then delete an account -> 204 (no body).
    acc = client.post(
        "/api/accounts",
        json={"exchange": "kraken", "label": "temp"},
        headers=auth_headers,
    )
    assert acc.status_code == 201
    acc_id = acc.json()["id"]
    resp = client.delete(f"/api/accounts/{acc_id}", headers=auth_headers)
    assert resp.status_code == 204
    assert resp.content == b""

    # Create then delete an agent -> 204 (no body).
    ag = client.post(
        "/api/agents",
        json={
            "name": "temp",
            "exchange": "kraken",
            "symbol": "BTC/USD",
            "strategy_type": "rule_based",
            "trade_mode": "paper",
        },
        headers=auth_headers,
    )
    assert ag.status_code == 201
    resp = client.delete(f"/api/agents/{ag.json()['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert resp.content == b""


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
