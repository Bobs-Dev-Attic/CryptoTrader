# CryptoTrader — Architecture

CryptoTrader lets a user configure **agents** that autonomously evaluate
cryptocurrency markets and place trades — in simulation (paper) or for real —
across Kraken, Binance, Coinbase, and Robinhood. It is inspired by the
[TradingAgents](https://github.com/Bobs-Dev-Attic/TradingAgents) multi-agent
framework, adapting its "analyst → decision → risk → execution" flow into a
product with real exchange connectivity and a cross-platform UI.

## System overview

```
┌───────────────────────────┐        HTTPS / JWT        ┌────────────────────────────┐
│   Expo app (mobile + web)  │  ───────────────────────► │       FastAPI backend       │
│  React Native + RN-Web     │  ◄─────────────────────── │                             │
│  dashboard · agents · keys │                           │  auth · accounts · agents   │
└───────────────────────────┘                           │  market data · scheduler    │
                                                         └──────────────┬──────────────┘
                                                                        │
                                          ┌─────────────────────────────┼──────────────────────────────┐
                                          │                             │                              │
                                   ┌──────▼──────┐              ┌───────▼────────┐             ┌────────▼────────┐
                                   │  Strategies │              │  Exchange layer │             │   Persistence   │
                                   │ rule-based  │              │ ccxt (Kraken,   │             │ SQLite/Postgres │
                                   │ LLM (Claude)│              │ Binance,        │             │ users, agents,  │
                                   └─────────────┘              │ Coinbase),      │             │ signals, trades │
                                                                │ Robinhood,      │             └─────────────────┘
                                                                │ PaperBroker     │
                                                                └─────────────────┘
```

## Core concepts

| Concept | Description |
| --- | --- |
| **User** | Owns accounts and agents; authenticates with email + password (JWT). |
| **ExchangeAccount** | A link to an exchange with API keys **encrypted at rest** (Fernet). Optional for paper agents. |
| **Agent** | A configured strategy on `(exchange, symbol, timeframe)` with a trade mode, order size, and run interval. |
| **Strategy** | Pluggable decision logic. Ships with a rule-based (RSI/MACD/MA) and an LLM (Claude) implementation behind one interface. |
| **Signal** | A recorded decision (BUY/SELL/HOLD + confidence + rationale + indicator snapshot). |
| **Trade** | An executed order (paper or live) with quantity, price, fee. |
| **Position** | The agent's current holdings and simulated cash ledger; tracks realized P&L. |

## The agent pipeline

Mirrors TradingAgents' desk metaphor, compressed for real-time execution:

1. **Data** — fetch recent OHLCV candles from the exchange (public).
2. **Analysis** — indicators (RSI, MACD, moving averages) are computed.
3. **Decision** — the strategy weighs the signals:
   - *Rule-based*: each enabled indicator casts a vote; the aggregate + agreement
     level yields action + confidence.
   - *LLM*: Claude is given the market snapshot and role-plays technical analyst /
     risk manager / portfolio manager, returning a structured JSON decision.
4. **Risk guard rails** — never buy while already long, never sell while flat.
5. **Execution** — paper (simulated ledger) or live (real market order).
6. **Record** — persist the signal and any trade; update the position.

## Trade modes & safety

- **Paper (default)**: `PaperBroker` simulates fills against an in-DB `Ledger`
  with a configurable fee. Uses real market data. No credentials required.
- **Live (opt-in)**: places real orders through the exchange adapter. Guarded at
  create/start time — requires a linked, credentialed, live-capable account.
- **Robinhood**: live execution is a marked extension point (Robinhood Crypto
  isn't in ccxt); Robinhood agents run in paper mode against a public price feed.

## Scheduling

A single APScheduler "tick" (every `MIN_AGENT_INTERVAL_SECONDS`) scans for
`RUNNING` agents whose `interval_seconds` have elapsed and evaluates each one.
Scheduling state lives in the database, so it survives restarts. Agents can also
be evaluated on demand via `POST /api/agents/{id}/run`.

## Technology choices

| Layer | Choice | Why |
| --- | --- | --- |
| App | Expo (React Native + RN-Web) | One codebase for iOS, Android, and web. |
| API | FastAPI + Pydantic v2 | Typed, fast, auto OpenAPI docs. |
| DB | SQLAlchemy 2.0 (SQLite → Postgres) | Simple local dev, production-ready path. |
| Exchanges | ccxt | Unified access to Kraken/Binance/Coinbase. |
| LLM | Anthropic Claude | Multi-analyst decision layer. |
| Auth | JWT + bcrypt | Standard stateless auth. |
| Secrets | Fernet (cryptography) | Symmetric encryption of API keys at rest. |

## Extension points

- **New exchange** — add an `ExchangeAdapter` subclass and register it in
  `factory.py`.
- **New strategy** — subclass `Strategy`, implement `decide()`, register it in
  `agents/registry.py` (it automatically appears in the app's strategy picker).
- **Robinhood live** — implement `create_market_order` in `RobinhoodAdapter`
  using the Robinhood Crypto API (key-pair signed requests).
- **Richer LLM desk** — expand `llm_agent.py` into the full multi-agent debate
  (separate analyst/researcher/trader calls) from TradingAgents.

## Added since the initial design (v0.2 → v0.6)

The diagram above still holds; these modules extend it. See `../CLAUDE.md` for
the full file map and `../TODO.md` / `REVIEW.md` for the current critique.

| Area | Module(s) | What it adds |
| --- | --- | --- |
| More strategies | `agents/technical.py`, `agents/indicators.py` | Donchian, SuperTrend, Bollinger, Z-score, momentum, ADX + OHLC indicators (ATR, Bollinger, ADX, …), each with decision-support metadata in `registry.py`. |
| Risk overlays | `agents/risk.py` (applied in `runner.py`) | Position sizing (fixed / %-equity / ATR-target), stop-loss / take-profit / trailing stop, max-drawdown kill-switch, post-loss cooldown, via `agents.risk_config`. |
| Portfolio | `api/portfolio.py` | Equity history, allocation, stats, and `/optimize` (risk-parity / equal / Sharpe suggestion). |
| Volatility radar | `marketscan.py`, `api/market.py` | Ranks a curated universe by 24h range / move / volume / return-vol / ATR%. |
| Alerts | `api/watchlist.py`, `VolatilityWatch` | Threshold watches evaluated each tick (rising-edge triggered state). |
| Push | `push.py`, `api/push.py`, `mobile/public/sw.js` | Web Push (auto-generated VAPID) + a foreground notifier fallback. |
| Serverless cron | `api/internal.py` | pg_cron `POST /api/internal/tick` runs due agents **and** evaluates alert watches. |
| Schema migrations | `migrations/`, `migrations_runtime.run_migrations` | Alembic, self-applied on startup (serverless has no migration step). New DB upgrades from zero; the pre-Alembic prod DB is adopted in place (backfill + stamp baseline). Add changes via `alembic revision --autogenerate`. |

## Roadmap ideas

- WebSocket push for live position/price updates (replace polling).
- Offline backtesting harness reusing the same `Strategy` interface.
- The security & compliance hardening tracked in `../TODO.md` (P0/P1).
