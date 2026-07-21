# CryptoTrader — Backend (FastAPI)

REST API that stores users, encrypted exchange credentials, and trading
**agents**, evaluates each agent's strategy on a schedule, and routes decisions
to a **paper** (simulated) or **live** execution path across Kraken, Binance,
Coinbase, and Robinhood.

## Quick start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit secrets
uvicorn app.main:app --reload --port 8000
```

Open the interactive API docs at http://localhost:8000/docs.

## Configuration

All settings come from environment variables / `.env` (see `.env.example`).
Important ones:

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET` | Signs auth tokens. **Change in production.** |
| `ENCRYPTION_KEY` | Fernet key encrypting exchange API keys at rest. Generate with the command in `.env.example`. Falls back to a key derived from `JWT_SECRET` in dev. |
| `ANTHROPIC_API_KEY` | Enables the LLM strategy. Without it, LLM agents safely return HOLD. |
| `DATABASE_URL` | SQLite by default; Postgres supported. |
| `SCHEDULER_ENABLED` | Turns the background agent runner on/off. |

## Architecture

```
app/
  main.py            # FastAPI app, CORS, lifespan (init DB + scheduler)
  config.py          # pydantic-settings
  database.py        # SQLAlchemy engine/session/Base
  models.py          # User, ExchangeAccount, Agent, Position, Signal, Trade
  schemas.py         # Pydantic request/response models
  security.py        # bcrypt hashing, JWT, Fernet credential encryption
  enums.py           # shared enums
  scheduler.py       # APScheduler tick that evaluates due agents

  exchanges/         # execution + market data
    base.py          # ExchangeAdapter ABC + Candle/Ticker/OrderResult
    ccxt_adapter.py  # Kraken / Binance / Coinbase via ccxt
    robinhood.py     # Robinhood adapter (paper feed; live is an extension point)
    paper.py         # PaperBroker + Ledger (pure, unit-tested)
    factory.py       # exchange -> adapter

  agents/            # the "brains"
    base.py          # Strategy ABC, StrategyContext, StrategyDecision
    indicators.py    # SMA / EMA / RSI / MACD (pure Python)
    rule_based.py    # RSI + MACD + MA-crossover voting strategy
    llm_agent.py     # Claude multi-analyst strategy (graceful fallback)
    registry.py      # StrategyType -> Strategy
    runner.py        # evaluate -> record Signal -> execute -> record Trade

  api/               # routers: auth, accounts, agents, market
```

### How an agent runs

1. The scheduler (or `POST /api/agents/{id}/run`) calls `run_agent_once`.
2. The exchange adapter fetches recent OHLCV candles.
3. The configured `Strategy.decide()` returns BUY / SELL / HOLD + confidence.
4. A `Signal` is recorded for transparency.
5. On BUY/SELL, execution runs in the agent's `trade_mode`:
   - **paper** → `PaperBroker` mutates the agent's simulated `Ledger`.
   - **live** → the adapter places a real market order (requires linked keys).
6. A `Trade` is recorded and the `Position` updated.

### Safety model

- New agents default to **paper**. Live mode is validated at create/start time:
  it requires a linked, credentialed, live-capable exchange account.
- Robinhood live execution is intentionally **not** wired up (no ccxt support);
  Robinhood agents run in paper mode using a public reference price feed.
- API secrets are encrypted with Fernet and never returned by the API.

## Tests

```bash
source .venv/bin/activate
pytest -q
```

Covers indicators, the paper broker ledger math, both strategy types, and the
API happy path (register → create paper agent → run → verify position/trade).
The exchange network layer is stubbed in tests via a fake adapter.
