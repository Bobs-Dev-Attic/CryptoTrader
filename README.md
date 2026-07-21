# CryptoTrader

Configure AI-driven **agents** to trade cryptocurrency across **Kraken,
Binance, Coinbase, and Robinhood** — from one app that runs on **web, iOS, and
Android**.

Inspired by the multi-agent
[TradingAgents](https://github.com/Bobs-Dev-Attic/TradingAgents) framework,
CryptoTrader turns that "analyst → decision → risk → execution" idea into a real
product: a FastAPI backend that connects to live exchanges plus an Expo
(React Native + web) client for configuring and monitoring agents.

> ⚠️ **Trading involves real financial risk.** Agents default to **paper
> (simulated) trading**. Live execution is strictly opt-in per agent and
> requires you to link exchange API keys. Nothing here is financial advice —
> use at your own risk and start in paper mode.

## Features

- 🤖 **Pluggable agents** — each agent runs a strategy on an
  `(exchange, symbol, timeframe)`:
  - **Rule-based**: RSI mean-reversion + MACD crossover + moving-average
    crossover, combined by a configurable voting scheme.
  - **LLM (Claude)**: a "trading desk" that weighs technical, risk, and
    portfolio perspectives and returns a structured decision.
- 📝 **Paper trading by default** with a simulated ledger, fees, and P&L — using
  real market data. Flip an agent to **live** when you're ready.
- 🔐 **Encrypted API keys** — exchange secrets are stored encrypted (Fernet) and
  never returned to the client.
- 🧭 **Setup wizard** — a guided flow walks you through connecting each exchange:
  pick the platform, follow per-exchange key instructions (with the right
  permissions), enter credentials, and **test the connection** before saving.
- 📊 **Transparency** — every evaluation records a signal (with the indicator
  snapshot / LLM rationale) and every fill records a trade.
- ⏱️ **Scheduler** — running agents are evaluated automatically on their
  interval; you can also "run once" on demand.
- 📱 **One codebase, everywhere** — Expo app targets web + iOS + Android.

## Repository layout

```
backend/     FastAPI service (agents, exchanges, execution, API)  — see backend/README.md
mobile/      Expo app (React Native + web client)                 — see mobile/README.md
docs/        Architecture overview                                 — see docs/ARCHITECTURE.md
```

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit JWT_SECRET, ENCRYPTION_KEY, ANTHROPIC_API_KEY
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. App

```bash
cd mobile
npm install
cp .env.example .env          # point EXPO_PUBLIC_API_URL at the backend
npm run web                   # or: npm run ios / npm run android / npm start
```

### 3. Try it (paper mode, no exchange keys needed)

1. Register an account in the app.
2. Create an agent: pick an exchange (e.g. Kraken), symbol `BTC/USD`, the
   rule-based strategy, and **paper** mode.
3. Open the agent and tap **Run once** — you'll see a signal and, if it's a BUY,
   a simulated trade and position. Tap **Start** to let the scheduler run it.

## How it works

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full picture. In short:

```
fetch candles → compute indicators → strategy decides (BUY/SELL/HOLD)
    → record signal → execute (paper ledger or live order) → record trade → update position
```

## Deployment

Deploys as a **single Vercel project** (repo root) that serves the Expo web app
and the FastAPI backend at `/api/*` from one origin, backed by Supabase Postgres,
with git auto-deploy on every push to `main`. No second project, no API-URL or
CORS config. See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the one remaining
step (environment variables).

## Tech stack

FastAPI · SQLAlchemy · ccxt · Anthropic Claude · APScheduler / Vercel Cron ·
JWT + bcrypt · Fernet encryption · Expo / React Native / react-native-web ·
TypeScript · Vercel · Supabase Postgres.

## Status & safety notes

- This is a functional **foundation**, not a turnkey money-printer. Validate
  strategies in paper mode (and ideally backtesting) before ever going live.
- Robinhood **live** execution is a marked extension point (Robinhood Crypto
  isn't available through ccxt); Robinhood agents run in paper mode.
- Live trading is only as safe as your exchange API-key permissions — scope keys
  to trading only, never withdrawals, and consider IP allowlists.

## License

See repository owner. Provided as-is, without warranty.
